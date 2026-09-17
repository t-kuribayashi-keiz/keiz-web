#!/usr/bin/env python3
"""MEO順位チェック(Googleマップのローカルパック順位)を無料で取得するプロトタイプ。

背景・設計判断は functions/meo-internal/CLAUDE.md を参照。要点:
- 公式Places APIは消費者向けマップの並び順と一致しないため不採用
- MVPは自前のPlaywrightスクレイピングで無料に構築する方針(2026-09-17、栗林さん確認)。
  本番規模(全ブランド・高頻度)に拡張する際は有料SERP API(DataForSEO等)への切り替えを
  再検討すること。ここでのスクレイピングはあくまでMVP/パイロット規模を想定している
- 2026-09-17に以下2キーワードで実地検証済み:
  - 「ピラティス 戸越銀座」→ LUNA Pilates Studio 戸越銀座店が1位/7件中で検出
  - 「整骨院 船橋」→ スクロールで24件まで読み込めることを確認(ページネーション動作OK)

Googleマップを検索キーワード(エリア名を含める想定。例:「整骨院 船橋」)だけで開き、
検索結果パネル(role=feed)内の店舗カードを上から順に読み取ることで順位とする。
緯度経度による地点指定はしていない(店舗マスタにlat/lngが無いため。GBP公式API
承認後にBusiness Information APIから取得する計画。上記CLAUDE.md参照)。

注意: Googleの検索結果ページの構造は変わりうる。動かなくなったらまず
`div[role="feed"] a[href*="/maps/place/"]` セレクタが有効かをブラウザで確認すること。
"""
import argparse
import json
import sys
from urllib.parse import quote

from playwright.sync_api import sync_playwright

MAX_RESULTS = 20


def check_rank(keyword: str, target_name_fragment: str, headless: bool = True) -> dict:
    """Googleマップでkeywordを検索し、店舗名にtarget_name_fragmentを含む結果の順位を返す。"""
    url = f"https://www.google.com/maps/search/{quote(keyword)}?hl=ja"
    result = {"keyword": keyword, "url": url, "listings": [], "target_rank": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        try:
            page.wait_for_selector('div[role="feed"]', timeout=10000)
        except Exception:
            pass

        feed = page.locator('div[role="feed"]')
        seen = set()
        stagnant_rounds = 0
        while len(seen) < MAX_RESULTS and stagnant_rounds < 3:
            cards = page.locator('div[role="feed"] a[href*="/maps/place/"]')
            before = len(seen)
            for i in range(cards.count()):
                href = cards.nth(i).get_attribute("href") or ""
                if href:
                    seen.add(href)
            stagnant_rounds = stagnant_rounds + 1 if len(seen) == before else 0
            try:
                feed.hover()
                page.mouse.wheel(0, 2000)
            except Exception:
                break
            page.wait_for_timeout(1200)

        cards = page.locator('div[role="feed"] a[href*="/maps/place/"]')
        added = set()
        rank = 0
        for i in range(cards.count()):
            href = cards.nth(i).get_attribute("href") or ""
            if not href or href in added:
                continue
            added.add(href)
            rank += 1
            name = cards.nth(i).get_attribute("aria-label") or ""
            result["listings"].append({"rank": rank, "name": name, "href": href})
            if target_name_fragment in name:
                result["target_rank"] = rank

        browser.close()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword", help="検索キーワード(エリア名を含める。例: 整骨院 船橋)")
    parser.add_argument("target", help="自店舗名に含まれる文字列(順位特定用の部分一致)")
    parser.add_argument("--out", default="meo_rank_check_result.json", help="結果の出力先JSONパス")
    parser.add_argument("--headed", action="store_true", help="ブラウザを表示して実行(デバッグ用)")
    args = parser.parse_args()

    out = check_rank(args.keyword, args.target, headless=not args.headed)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"total_listings={len(out['listings'])} target_rank={out['target_rank']}")
    print(f"saved to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
