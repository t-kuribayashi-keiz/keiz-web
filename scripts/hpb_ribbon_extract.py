#!/usr/bin/env python3
"""HPBリボンデータ(店舗別のHPB分析PDF)から、月号ごとのKPIを抽出する。

「リボンデータ」= HotPepper Beautyが店舗単位で出す23ページ超のPDFレポート。
パスワード付きZIPで配布され、中の各PDFにも共通パスワードが掛かっている。1枚に
予約数・売上・PV/CVR/ACR(自社/エリア平均/比較サロン)・性別/年代などが14か月分入っている。

このモジュールの責務は2つ:
  1. decrypt  … ZIP展開済みのPDF群を、バッチID(SL…)ごとの共通パスワードで復号する
  2. extract  … 復号済みPDFから、対象月号(既定=最新の完了月)のKPI行を作る

抽出した行は scripts/hpb_master_writer.py が「HPB_145店舗_KPI一括集計結果」のMasterへ書く。
ここではシートに触れない(ネットワーク不要・テスト可能)。純粋関数(parse_summary_kpis /
series_completed_value)は tests/test_hpb_ribbon_extract.py がPDFテキストのfixtureで検証する。

なぜサマリページを正とするか:
  時系列ページ(PV推移/CVR推移/ACR推移)は末尾2列が『当月号(進行中)』『翌月号』で、
  完了しているのは末尾から2列目。サマリページ(自サロンTOP PV 等)は"最新の完了月"の
  スナップショットで、ここの3値=完了月のPV/CVR/ACR。両者は実データで一致する。
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys

# --- 抽出の純粋関数 (シート・PDFライブラリに依存しない。fixtureでテストする) --------------

_NUMLINE = re.compile(r"^-?[\d,]+\.?\d*%?$")
_DASHLINE = re.compile(r"^-\s*%?$")   # 空データ月のプレースホルダ「- %」「-%」「-」


def clean_number(s):
    """「1,036」「62.5%」→ "1036" "62.5"。空・ダッシュは None。"""
    if s is None:
        return None
    s = s.replace(",", "").replace("%", "").replace("¥", "").strip()
    return s if s not in ("", "-", "–", "—") else None


def nums_after(text, label, count):
    """`label` の直後から最大 `count` 個の数値トークンを拾う。サマリの3値抽出に使う。"""
    i = text.find(label)
    if i < 0:
        return []
    return re.findall(r"-?[\d,]+\.?\d*%?", text[i + len(label):])[:count]


def series_completed_value(lines, label_exact, completed_index=-2):
    """時系列の行を、ラベル行の直後の『連続する数値/ダッシュ行』として読み、完了月の値を返す。

    「- %」(空データ月)は列としては数えるが値は None にする。そうしないと、開店直後で
    先頭が全部『- %』の店舗で列がずれ、当月号(末尾)の値を拾ってしまう。
    戻り値は (値or None, 読めた列数)。列数は健全性チェック(概ね14)に使う。
    """
    for i, line in enumerate(lines):
        if line.strip() == label_exact:
            vals = []
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if _NUMLINE.match(s):
                    vals.append(s)
                elif _DASHLINE.match(s):
                    vals.append(None)
                else:
                    break
            if len(vals) >= abs(completed_index):
                return vals[completed_index], len(vals)
            return None, len(vals)
    return None, 0


def parse_summary_kpis(summary_text):
    """サマリページのテキストから PV/CVR/ACR(自社・エリア平均)と予約数を取り出す。

    レイアウト: 「自サロンTOP PV」→ 自社/エリア平均/比較 の順に3値。CVR/ACRも同じ。
    予約数は「前月予約数」直後がALL、「新規予約\nリピート予約」直後が新規。
    """
    pv = nums_after(summary_text, "自サロンTOP PV", 3)
    cvr = nums_after(summary_text, "自サロンCVR", 3)
    acr = nums_after(summary_text, "自サロンACR", 3)
    all_m = re.search(r"前月予約数\n([\d,]+)", summary_text)
    new_m = re.search(r"新規予約\nリピート予約\n([\d,]+)", summary_text)
    return {
        "自社PV": clean_number(pv[0]) if len(pv) > 0 else None,
        "エリア平均PV": clean_number(pv[1]) if len(pv) > 1 else None,
        "自社CVR": clean_number(cvr[0]) if len(cvr) > 0 else None,
        "エリア平均CVR": clean_number(cvr[1]) if len(cvr) > 1 else None,
        "自社ACR": clean_number(acr[0]) if len(acr) > 0 else None,
        "エリア平均ACR": clean_number(acr[1]) if len(acr) > 1 else None,
        "新規予約数実績": clean_number(new_m.group(1)) if new_m else None,
        "集客数_ribbon_ALL": clean_number(all_m.group(1)) if all_m else None,
    }


def store_name_from_filename(basename):
    """『【冠】◯◯整体院_20260902_120814.pdf』→ 冠つきのHPB店舗名。"""
    return re.sub(r"_\d{8}_\d{6}\.pdf$", "", basename)


# --- PDF入出力 (pymupdf / pikepdf に依存。CLIから呼ぶ) --------------------------------------

def load_passwords():
    """バッチID部分文字列 → パスワード の辞書を環境変数から読む。中身はログに出さない。"""
    raw = os.environ.get("HPB_RIBBON_PASSWORDS", "").strip()
    if not raw:
        return {}
    # ファイルパスでもJSONでも受ける
    if os.path.exists(raw):
        with open(raw, encoding="utf-8") as fh:
            raw = fh.read()
    return json.loads(raw)


def password_for(path, passwords):
    for batch_id, pw in passwords.items():
        if batch_id in path:
            return pw
    return None


def decrypt_dir(src_root, dst_root, passwords):
    """src_root配下のPDFを、パスに含まれるバッチIDのパスワードで復号し dst_root へ複製。"""
    import pikepdf
    ok = skip = fail = 0
    errors = []
    for dp, _dn, fn in os.walk(src_root):
        for f in sorted(fn):
            if not f.lower().endswith(".pdf"):
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(dst) and os.path.getsize(dst) > 1000:
                skip += 1
                continue
            pw = password_for(src, passwords)
            if pw is None:
                fail += 1
                errors.append((f, "パスワード未定義(バッチID不一致)"))
                continue
            try:
                with pikepdf.open(src, password=pw) as pdf:
                    pdf.save(dst)
                ok += 1
            except Exception as exc:  # noqa: BLE001 - 何が失敗しても店舗名付きで残す
                fail += 1
                errors.append((f, type(exc).__name__))
    return {"decrypted": ok, "skipped": skip, "failed": fail, "errors": errors}


def extract_pdf(path, completed_index=-2):
    """1店舗のPDFから対象月号のKPIを抽出。院名はP3の掲載状況(最寄駅の直後)から取る。"""
    import pymupdf
    doc = pymupdf.open(path)
    page0 = doc[0].get_text()
    page2 = doc[2].get_text() if doc.page_count > 2 else ""
    summary = ""
    for idx in (3, 4, 2, 5):
        if idx < doc.page_count:
            t = doc[idx].get_text()
            if "自サロンTOP PV" in t and "自サロンCVR" in t:
                summary = t
                break
    if not summary:
        for pi in range(doc.page_count):
            t = doc[pi].get_text()
            if "自サロンTOP PV" in t and "自サロンCVR" in t:
                summary = t
                break
    doc.close()

    lines = page0.split("\n")
    m = re.search(r"最寄駅\n(.+?)\n", page2)
    row = {
        "HPB店舗名": store_name_from_filename(os.path.basename(path)),
        "院名": m.group(1).strip() if m else "",
    }
    row.update(parse_summary_kpis(summary))
    fem, months = series_completed_value(lines, "女性率", completed_index)
    row["女性率"] = clean_number(fem)
    row["_months"] = months
    for label, key in (("20代未満", "20代未満比率"), ("20代", "20代比率"),
                       ("30代", "30代比率"), ("40代", "40代比率"), ("50代以上", "50代以上比率")):
        val, _ = series_completed_value(lines, label, completed_index)
        row[key] = clean_number(val)
    return row


def validate_row(row, age_tol=(90, 110)):
    problems = []
    for k in ("自社PV", "エリア平均PV", "自社CVR", "エリア平均CVR", "自社ACR",
              "エリア平均ACR", "新規予約数実績", "女性率"):
        if row.get(k) in (None, ""):
            problems.append("欠損:" + k)
    if row.get("_months") not in (14, 13, 15):
        problems.append(f"月数={row.get('_months')}")
    ages = [row.get(k) for k in ("20代未満比率", "20代比率", "30代比率", "40代比率", "50代以上比率")]
    if all(a is not None for a in ages):
        s = sum(float(a) for a in ages)
        if not (age_tol[0] <= s <= age_tol[1]):
            problems.append(f"年代合計={s:.0f}")
    else:
        problems.append("年代欠損")
    # 全欠損は開店直後(全"-")の可能性が高い。区別できるよう印をつける。
    if all(row.get(k) in (None, "") for k in ("自社PV", "自社CVR", "自社ACR")):
        problems = ["空データ(開店直後の可能性)"]
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="HPBリボンPDFの復号とKPI抽出")
    ap.add_argument("--src", required=True, help="ZIP展開済みのルート(バッチIDのフォルダを含む)")
    ap.add_argument("--decrypted", help="復号PDFの出力先。省略時は <src>/解除済み")
    ap.add_argument("--month", default="", help="出力する年月号ラベル(例 2026年08月号)。省略時は空欄")
    ap.add_argument("--completed-index", type=int, default=-2,
                    help="時系列で完了月とみなす列(既定 -2 = 末尾から2列目)")
    ap.add_argument("--out", default="", help="抽出結果CSVの出力先。省略時は標準出力に要約のみ")
    ap.add_argument("--skip-decrypt", action="store_true", help="復号を飛ばして既存の復号PDFを使う")
    args = ap.parse_args(argv)

    dst = args.decrypted or os.path.join(args.src, "解除済み")
    if not args.skip_decrypt:
        passwords = load_passwords()
        if not passwords:
            print("[警告] HPB_RIBBON_PASSWORDS が未設定。復号せず既存PDFを使う。", file=sys.stderr)
        else:
            report = decrypt_dir(args.src, dst, passwords)
            print(f"復号: 新規{report['decrypted']} / スキップ{report['skipped']} / "
                  f"失敗{report['failed']}", file=sys.stderr)
            for name, why in report["errors"]:
                print(f"  復号失敗 {name}: {why}", file=sys.stderr)

    files = sorted(glob.glob(os.path.join(dst, "**", "*.pdf"), recursive=True))
    rows = []
    issues = []
    for path in files:
        try:
            row = extract_pdf(path, args.completed_index)
        except Exception as exc:  # noqa: BLE001
            issues.append((os.path.basename(path), "抽出例外 " + type(exc).__name__))
            continue
        if args.month:
            row["年月号"] = args.month
        problems = validate_row(row)
        if problems:
            issues.append((row.get("院名") or row["HPB店舗名"], ";".join(problems)))
        rows.append(row)

    print(f"抽出: {len(rows)}店舗 / 要確認 {len(issues)}件", file=sys.stderr)
    for name, why in issues:
        print(f"  要確認 {name}: {why}", file=sys.stderr)

    if args.out:
        cols = ["HPB店舗名", "院名", "年月号", "自社PV", "エリア平均PV", "自社CVR",
                "エリア平均CVR", "自社ACR", "エリア平均ACR", "新規予約数実績", "女性率",
                "20代未満比率", "20代比率", "30代比率", "40代比率", "50代以上比率",
                "集客数_ribbon_ALL", "_months"]
        with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in rows:
                w.writerow([row.get(c, "") for c in cols])
        print(f"書き出し: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
