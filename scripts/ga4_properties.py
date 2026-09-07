#!/usr/bin/env python3
"""GA4のプロパティ名を、院マスタの店舗に突き合わせる。

リラックスはGA4プロパティが店舗ごとに分かれている(2026-09-04確認)。プロパティIDを人が
書き写すと、写し間違いがそのまま別店舗の数字になる。そこで Admin API の
`accountSummaries` が返すプロパティ名を、`data/clinics.json` の店舗名に機械的に
突き合わせて対応表を作る。

**認証情報は要らない。** 入力はプロパティ名の一覧(1行1件、または Admin API の
レスポンスJSON)なので、ローカルセッションが報告してきた一覧をそのまま食わせられる。

*このスクリプトは推測しない。* 1つの店舗に2つのプロパティが当たった、どの店舗にも
当たらなかった、といったものは対応表に入れず、未解決として報告する。半端に埋まった
対応表は「取り込めていない店舗」と「数字がゼロの店舗」を区別できなくする。

使い方:

    python3 scripts/ga4_properties.py --brand リラックス --names properties.txt
    python3 scripts/ga4_properties.py --brand リラックス --names summaries.json --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from store_matcher import StoreMatcher, group_of, normalize_store_name  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CLINICS_PATH = REPO / "data" / "clinics.json"

# GA4のプロパティ名によく付く飾り。店舗名の一部ではないので落とす。
# 例: 「リラックス 阿佐ヶ谷店 - GA4」「refresh-relax.com（梅ヶ丘店）」「GA4_浦和店」
PROPERTY_DECORATIONS = (
    r"ga4",
    r"google\s*analytics\s*4?",
    r"universal\s*analytics",
    r"refresh[-\s]?relax(\.com)?",
    r"リフレッシュリラックス",
    r"プロパティ",
    r"property",
)


def clean_property_name(name: str) -> str:
    """プロパティ名から、店舗名でない飾りを落とす。

    落とした結果が空になる場合は落とさない(「GA4」だけのプロパティ名を空にすると、
    どの店舗にも当たらないのではなく全店舗に当たってしまう)。
    """
    text = str(name).strip()
    for pattern in PROPERTY_DECORATIONS:
        stripped = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        if stripped.strip(" 　-_|/（）()[]【】"):
            text = stripped
    # 飾りを抜いた跡の空の括弧を畳む。「梅ヶ丘店（GA4）」→「梅ヶ丘店（ ）」のままだと
    # 対応表のログが読みにくい(照合自体は正規化が括弧を落とすので結果は変わらない)。
    text = re.sub(r"[（(\[【]\s*[）)\]】]", "", text)
    return re.sub(r"\s+", " ", text).strip(" 　-_|/")


def property_names_from(raw: str) -> list[str]:
    """入力を名前の一覧にする。1行1件のテキストでも、Admin APIのJSONでもよい。"""
    text = raw.strip()
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        summaries = data.get("accountSummaries", data) if isinstance(data, dict) else data
        names = []
        for summary in summaries:
            for prop in summary.get("propertySummaries", []) if isinstance(summary, dict) else []:
                names.append(prop.get("displayName", ""))
            if isinstance(summary, dict) and "displayName" in summary and not summary.get(
                "propertySummaries"
            ):
                names.append(summary["displayName"])
        return [name for name in names if name]
    return [line.strip() for line in text.splitlines() if line.strip()]


def property_id_map(raw: str) -> dict[str, str]:
    """Admin APIのJSONなら、プロパティ名→リソース名(properties/123456)も拾う。"""
    text = raw.strip()
    if not (text.startswith("{") or text.startswith("[")):
        return {}
    data = json.loads(text)
    summaries = data.get("accountSummaries", data) if isinstance(data, dict) else data
    found = {}
    for summary in summaries:
        if not isinstance(summary, dict):
            continue
        for prop in summary.get("propertySummaries", []):
            if prop.get("displayName") and prop.get("property"):
                found[prop["displayName"]] = prop["property"]
    return found


def resolve(names: list[str], brand: str, clinics_path: Path = CLINICS_PATH) -> dict:
    """プロパティ名を店舗に突き合わせる。1対1に定まったものだけを対応表に入れる。"""
    matcher = StoreMatcher(str(clinics_path))
    clinics = json.loads(clinics_path.read_text(encoding="utf-8"))["clinics"]
    in_brand = {clinic["name"] for clinic in clinics if clinic["brand"] == brand}
    if not in_brand:
        raise ValueError(f"ブランド『{brand}』の店舗が院マスタにありません。")

    claims: dict[str, list[str]] = {}
    unmatched: list[tuple[str, str]] = []
    other_brand: list[tuple[str, str]] = []

    for name in names:
        cleaned = clean_property_name(name)
        result = matcher.match(cleaned)
        clinic = result["clinic"]
        if clinic is None:
            unmatched.append((name, result["how"]))
            continue
        if clinic["name"] not in in_brand:
            other_brand.append((name, f"{clinic['name']}({group_of(clinic)})"))
            continue
        claims.setdefault(clinic["name"], []).append(name)

    # 同じ店舗に2つ以上のプロパティが当たったら、どちらが正か決められない。両方外す。
    matched = {store: props[0] for store, props in claims.items() if len(props) == 1}
    duplicated = {store: props for store, props in claims.items() if len(props) > 1}
    missing = sorted(in_brand - set(claims))

    return {
        "brand": brand,
        "matched": dict(sorted(matched.items())),
        "duplicated": dict(sorted(duplicated.items())),
        "unmatched": unmatched,
        "other_brand": other_brand,
        "missing": missing,
        "store_count": len(in_brand),
    }


def report(result: dict) -> int:
    print(f"ブランド: {result['brand']}(院マスタ {result['store_count']}店舗)")
    print(f"1対1で決まった: {len(result['matched'])}件\n")
    for store, prop in result["matched"].items():
        mark = "" if normalize_store_name(store) == normalize_store_name(
            clean_property_name(prop)
        ) else "   ← 名前が完全一致ではない。目視で確認すること"
        print(f"  {store:<24} ← {prop!r}{mark}")

    problems = 0
    if result["duplicated"]:
        problems += len(result["duplicated"])
        print("\n**同じ店舗に複数のプロパティが当たった**(どちらが正か決められないので外した):")
        for store, props in result["duplicated"].items():
            print(f"  {store}: {props}")
    if result["unmatched"]:
        problems += len(result["unmatched"])
        print("\n**どの店舗にも当たらなかったプロパティ**:")
        for name, how in result["unmatched"]:
            print(f"  {name!r}({how})")
    if result["other_brand"]:
        print("\n他ブランドの店舗に当たったプロパティ(このブランドの対応表には入れない):")
        for name, where in result["other_brand"]:
            print(f"  {name!r} → {where}")
    if result["missing"]:
        print(f"\nプロパティが見つからなかった店舗 {len(result['missing'])}件:")
        print("  " + "、".join(result["missing"]))

    if problems or result["missing"]:
        print("\n未解決が残っています。**この対応表のまま数字を取り込まないこと。**")
        print("プロパティ名の実物を見て、data/store-name-aliases.json に言い換えを足すか、")
        print("GA4側のプロパティ名を直すかを決めてください。")
        return 1
    print("\n全店舗が1対1で決まりました。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True, help="院マスタのブランド名(例: リラックス)")
    parser.add_argument("--names", required=True,
                        help="プロパティ名の一覧。1行1件のテキスト、またはAdmin APIのJSON")
    parser.add_argument("--write", metavar="PATH", nargs="?", const="",
                        help="対応表をJSONで書き出す(既定: data/<brand>-ga4-properties.json)")
    args = parser.parse_args()

    raw = Path(args.names).read_text(encoding="utf-8")
    names = property_names_from(raw)
    if not names:
        print("ERROR: プロパティ名が1件も読めませんでした。", file=sys.stderr)
        return 1
    print(f"入力: {len(names)}件のプロパティ名\n")

    result = resolve(names, args.brand)
    status = report(result)

    if args.write is not None:
        if status:
            print("\n未解決があるので書き出しませんでした。", file=sys.stderr)
            return status
        ids = property_id_map(raw)
        path = Path(args.write) if args.write else (
            REPO / "data" / f"{args.brand}-ga4-properties.json"
        )
        payload = {
            "_comment": (
                f"{args.brand}のGA4プロパティ対応表。scripts/ga4_properties.py が"
                "プロパティ名と院マスタの店舗名を突き合わせて生成した。"
                "**手で編集しない** — GA4側のプロパティが増減したら作り直す。"
            ),
            "brand": args.brand,
            "properties": {
                store: {"display_name": prop, "property": ids.get(prop, "")}
                for store, prop in result["matched"].items()
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        print(f"\n対応表を書き出しました: {path}")
    return status


if __name__ == "__main__":
    sys.exit(main())
