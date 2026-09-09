#!/usr/bin/env python3
"""HotPepper Beautyの公開サロンページから、月次の口コミ・ブログ実績を自動集計する。

「口コミブログチェック表」(スプレッドシートID: 1cmYMBJb5do2MsdO43-RS2uD22vEbNJHoPYMZ3hvqEvA)を
毎月月初に前月分手動で数えている作業を自動化するためのスクリプト。2026-09-07、わかば整骨院
(H000475060)を対象に手動集計と突き合わせて検証済み(口コミ総数・★5数・写真あり ブログ数の
3項目とも完全一致)。

集計する3項目:
  - review_total: 対象月に投稿された口コミの総数
  - review_5star: そのうち「総合」が★5のもの
  - blog_photo_count: 対象月のブログのうち、本文サムネイルに実写真が付いているものの数
    (「写真有りだけ数える」というシート側のルール。サムネイル画像のsrcに"IMG_BLOG_ORG"を
    含むかどうかで判定する。カテゴリアイコンのみの投稿はここに含まれない)

対象院と店舗ID(storeId)の対応表は data/hpb-review-blog-ids.json。2026-09-09時点で165院、
全て決着済み(163院は個別のHPB店舗ページで直接計測、残り2院は業態切り替えにより既に別院に
統合済み。詳細は同ファイルの _coverage_comment / merged_into_ahaki_sibling を参照)。
未収録院を追加する手順は同ファイルの _how_to_add_comment を参照。院名の表記ゆれ
(整骨院/接骨院/整体院違いが同じ拠点名で複数院に分かれているケース)は自動突き合わせが誤爆
しやすいので、追加時は必ずスクレイプ結果を手動集計値と突き合わせて確認すること
(2026-09-07に実際に5院分の誤割り当てが発生した。詳細は
.claude/skills/hpb-review-blog-check/references/id-matching-pitfalls.md)。

HPBの店舗ページが「掲載エラー」(掲載終了)になっている場合は例外を送出する。呼び出し側で
catchしてCSVのerror列に記録される想定(黙って0件と扱うと、本当に活動が無い月なのか掲載終了
なのか区別できなくなるため)。

**既定はレポート出力のみ(--mode report)。** スプレッドシートへの書き込みは --mode apply を
明示した場合のみ行う(hpb_slot_check.pyと同じ方針)。apply には環境変数 GCP_KPI_WRITER_KEY
(サービスアカウントJSON全文)が必要。書き込み前に、対象スプレッドシートをそのサービス
アカウントに編集者共有しておくこと。

使い方:
  python scripts/hpb_review_blog_check.py --month 202608 --mode report --out report.csv
  python scripts/hpb_review_blog_check.py --month 202608 --mode apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import datetime
import json
import os
import re
import sys
from pathlib import Path

SHEET_ID = "1cmYMBJb5do2MsdO43-RS2uD22vEbNJHoPYMZ3hvqEvA"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
IDS_FILE = Path(__file__).resolve().parent.parent / "data" / "hpb-review-blog-ids.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def fail(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def month_tab_name(year: int, month: int) -> str:
    """対象月のタブ名を組み立てる(例: 2026年8月 -> '2608月分')。"""
    return f"{year % 100:02d}{month:02d}月分"


def load_clinic_ids(ids_file: Path) -> dict[str, str]:
    with open(ids_file, encoding="utf-8") as f:
        data = json.load(f)
    return {name: info["store_id"] for name, info in data["clinics"].items()}


async def check_not_delisted(page, store_id: str) -> None:
    """店舗ページが「掲載エラー」(掲載終了)になっていないか確認する。なっていれば例外を送出。"""
    resp = await page.goto(f"https://beauty.hotpepper.jp/kr/sln{store_id}/", wait_until="domcontentloaded", timeout=30000)
    title = await page.title()
    if (resp is not None and resp.status >= 400) or "掲載エラー" in title:
        raise RuntimeError(f"店舗ページが掲載エラー(掲載終了)になっています: {store_id}")


async def fetch_review_counts(page, store_id: str, year: int, month: int) -> tuple[int, int]:
    """対象月の口コミ総数と★5件数を返す。ページを新しい順にたどり、対象月より前の
    口コミしか無いページに着いたら打ち切る(サロンPick Upで1件だけ順序が前後することが
    あるため、各口コミは個別に日付判定し、ページ単位の打ち切りだけ保守的に行う)。
    """
    total = 0
    star5 = 0
    page_num = 1
    while True:
        url = (
            f"https://beauty.hotpepper.jp/kr/sln{store_id}/review/"
            if page_num == 1
            else f"https://beauty.hotpepper.jp/kr/sln{store_id}/review/PN{page_num}.html"
        )
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if resp is None or resp.status >= 400:
            break

        items = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('li.reportCassette, li.reportDetailCassette')).map(li => {
                const dateP = li.querySelector('p.fs10.fgGray');
                const dateMatch = dateP ? dateP.textContent.match(/(\\d{4})\\/(\\d{1,2})\\/(\\d{1,2})/) : null;
                const scoreEl = li.querySelector('.judgeList .fgPurple4');
                return {
                    year: dateMatch ? parseInt(dateMatch[1]) : null,
                    month: dateMatch ? parseInt(dateMatch[2]) : null,
                    score: scoreEl ? parseInt(scoreEl.textContent.trim()) : null,
                };
            })
            """
        )
        if not items:
            break

        in_month = [it for it in items if it["year"] == year and it["month"] == month]
        total += len(in_month)
        star5 += sum(1 for it in in_month if it["score"] == 5)

        # このページの口コミが全て対象月より前(=対象月より古い)なら、以降のページは
        # さらに古いので打ち切ってよい。ページの中に対象月または対象月より新しいものが
        # 1件でもあれば、次ページも対象月の口コミが残っている可能性があるので継続する。
        def is_older(it):
            if it["year"] is None:
                return True
            return (it["year"], it["month"]) < (year, month)

        if items and all(is_older(it) for it in items):
            break

        # 次ページの有無を確認
        has_next = await page.evaluate(
            """
            () => !!Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '次の30件')
            """
        )
        if not has_next:
            break
        page_num += 1
        if page_num > 30:  # 異常系の安全弁
            break

    return total, star5


async def fetch_blog_photo_count(page, store_id: str, year: int, month: int) -> tuple[int, int]:
    """対象月のブログ総数と、写真付き(IMG_BLOG_ORGサムネイルあり)件数を返す。"""
    yyyymm = f"{year}{month:02d}"
    total = 0
    with_photo = 0
    page_num = 1
    while True:
        url = (
            f"https://beauty.hotpepper.jp/kr/sln{store_id}/blog/{yyyymm}/"
            if page_num == 1
            else f"https://beauty.hotpepper.jp/kr/sln{store_id}/blog/{yyyymm}/PN{page_num}.html"
        )
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if resp is None or resp.status >= 400:
            break

        items = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('li.blogListCassette')).map(li => {
                const hasPhoto = Array.from(li.querySelectorAll('img')).some(im => im.src.includes('IMG_BLOG_ORG'));
                return { hasPhoto };
            })
            """
        )
        if not items:
            break
        total += len(items)
        with_photo += sum(1 for it in items if it["hasPhoto"])

        has_next = await page.evaluate(
            """
            () => !!Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === '次へ')
            """
        )
        if not has_next:
            break
        page_num += 1
        if page_num > 100:  # 異常系の安全弁(投稿頻度が高い院で足りなくなったら引き上げる)
            break

    return total, with_photo


async def run(clinics: dict[str, str], year: int, month: int, limit: int | None):
    from playwright.async_api import async_playwright

    names = list(clinics.items())
    if limit:
        names = names[:limit]

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 1200})
        page = await context.new_page()

        for i, (name, store_id) in enumerate(names):
            print(f"🔍 集計中 ({i + 1}/{len(names)}): {name} ({store_id})", flush=True)
            try:
                await check_not_delisted(page, store_id)
                review_total, review_5star = await fetch_review_counts(page, store_id, year, month)
                blog_total, blog_photo = await fetch_blog_photo_count(page, store_id, year, month)
                results.append(
                    {
                        "name": name,
                        "store_id": store_id,
                        "review_total": review_total,
                        "review_5star": review_5star,
                        "blog_total_raw": blog_total,
                        "blog_photo_count": blog_photo,
                        "error": "",
                    }
                )
            except Exception as e:  # noqa: BLE001 - 1院の失敗で全体を止めない
                print(f"  ⚠️ 失敗: {e}", file=sys.stderr)
                results.append(
                    {
                        "name": name,
                        "store_id": store_id,
                        "review_total": None,
                        "review_5star": None,
                        "blog_total_raw": None,
                        "blog_photo_count": None,
                        "error": str(e),
                    }
                )

        await browser.close()
    return results


def write_csv(results: list[dict], out_path: Path) -> None:
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "store_id", "review_total", "review_5star", "blog_total_raw", "blog_photo_count", "error"],
        )
        writer.writeheader()
        writer.writerows(results)


def build_spreadsheet():
    raw = os.environ.get("GCP_KPI_WRITER_KEY", "").strip()
    if not raw:
        fail(
            "GCP_KPI_WRITER_KEY が未設定です。書き込み用サービスアカウントのJSON全文を"
            "環境変数で渡してください。事前に対象スプレッドシートをそのサービスアカウントに"
            "編集者共有しておく必要があります。"
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        fail("GCP_KPI_WRITER_KEY がJSONとして読めません(値の中身は表示しません)。")

    try:
        import gspread
        from google.oauth2 import service_account
    except ImportError:
        fail("gspread / google-auth が必要です: pip install gspread google-auth")

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def apply_to_sheet(results: list[dict], year: int, month: int, tab_override: str | None = None) -> None:
    """対象タブのG/H/I列(口コミ投稿総数・★5の口コミ数・ブログ数)に書き込む。
    列A(院名)が一致する行だけを対象にする。列が用意されていないセクション
    (2026-09-07時点ではアンビション担当セクション)の院は書き込み対象外。

    tab_override: 通常は対象月から自動計算したタブ名(例: 202608 -> "2608月分")に書き込むが、
    テスト目的で複製したタブなど、別のタブ名を明示的に指定したい場合に使う
    (本番タブを書き換えずに --mode apply の疎通確認をしたいときなど)。
    """
    import unicodedata

    tab_name = tab_override or month_tab_name(year, month)
    spreadsheet = build_spreadsheet()
    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except Exception:
        fail(f"タブ「{tab_name}」が見つかりません。対象月のタブが存在するか確認してください。")

    all_values = worksheet.get_all_values()
    name_to_row = {}
    for row_idx, row in enumerate(all_values, start=1):
        if not row:
            continue
        cell = unicodedata.normalize("NFC", row[0].strip())
        if cell:
            name_to_row[cell] = row_idx

    by_name = {unicodedata.normalize("NFC", r["name"]): r for r in results}

    updates = []
    skipped = []
    for name, r in by_name.items():
        row_idx = name_to_row.get(name)
        if not row_idx:
            skipped.append(name)
            continue
        if r["error"]:
            continue
        updates.append(
            {
                "range": f"G{row_idx}:I{row_idx}",
                "values": [[r["review_total"], r["review_5star"], r["blog_photo_count"]]],
            }
        )

    if updates:
        worksheet.batch_update(updates)
    print(f"✅ {len(updates)}件を書き込みました(タブ「{tab_name}」)。")
    if skipped:
        print(f"⚠️ シート上に該当行が見つからず書き込めなかった院: {len(skipped)}件")
        for name in skipped:
            print(f"  - {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="対象月 YYYYMM 形式 (例: 202608)")
    parser.add_argument("--mode", choices=["report", "apply"], default="report")
    parser.add_argument("--ids-file", default=str(IDS_FILE))
    parser.add_argument("--out", default=None, help="report モード時のCSV出力先")
    parser.add_argument("--limit", type=int, default=None, help="テスト用: 先頭N院だけ処理")
    parser.add_argument(
        "--tab",
        default=None,
        help="apply時の書き込み先タブ名を明示指定(省略時は対象月から自動計算)。"
        "本番タブを書き換えずに疎通確認したい場合、複製したタブ名を指定する。",
    )
    args = parser.parse_args()

    m = re.match(r"^(\d{4})(\d{2})$", args.month)
    if not m:
        fail("--month は YYYYMM 形式で指定してください(例: 202608)")
    year, month = int(m.group(1)), int(m.group(2))

    clinics = load_clinic_ids(Path(args.ids_file))
    print(f"対象院数: {len(clinics)}院 / 対象月: {year}年{month}月")

    results = asyncio.run(run(clinics, year, month, args.limit))

    out_path = Path(args.out) if args.out else Path(f"hpb_review_blog_{args.month}.csv")
    write_csv(results, out_path)
    print(f"📄 CSVを書き出しました: {out_path}")

    if args.mode == "apply":
        apply_to_sheet(results, year, month, tab_override=args.tab)


if __name__ == "__main__":
    main()
