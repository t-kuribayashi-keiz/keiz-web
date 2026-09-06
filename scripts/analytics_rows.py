#!/usr/bin/env python3
"""GA4とSearch Consoleの応答を、統合ログの行に落とす。

統合ログは `(年月, 店舗, チャネル, 指標, 値)` の1行1レコード。この形にそろえて初めて、
先行指標(順位・流入・CTR)と実績(来店・予約)を突き合わせられる。

**ここはAPIを叩かない。** 応答の辞書を受け取って行に変えるだけなので、鍵なしで試せる。
APIを叩く側は analytics_pull.py。
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
CLINICS_PATH = REPO / "data" / "clinics.json"

# どの店舗ページにも当たらなかったぶんの置き場。**捨てない。**
# トップページ・コラム・採用ページなどが入る。合計が合わなくなったときに、
# 消えたのか元々店舗外なのかを区別できるようにしておく。
OUTSIDE = "(店舗ページ外)"


def store_paths(brand: str, clinics_path: Path = CLINICS_PATH) -> dict[str, str]:
    """ブランドの店舗ページのパス → 店舗名。パスは前後のスラッシュを外した形。"""
    clinics = json.loads(clinics_path.read_text(encoding="utf-8"))["clinics"]
    found = {}
    for clinic in clinics:
        if clinic.get("brand") != brand:
            continue
        path = urlparse(clinic.get("website", "")).path.strip("/")
        if path:
            found[path] = clinic["name"]
    return found


def store_of_page(url: str, paths: dict[str, str]) -> str:
    """ページURLがどの店舗のものかを決める。

    **最長一致で決める。** 前方一致を短いものから採ると、`/tama/` が
    `/tama-plaza/` のような別ページまで拾う。実際に店舗パスは
    `/nakano...` が複数あるので(中野新橋・中野坂上)、ここは効く。

    どの店舗にも当たらないページは捨てずに `(店舗ページ外)` に寄せる。
    """
    segments = urlparse(url).path.strip("/")
    best = ""
    for path in paths:
        if segments == path or segments.startswith(path + "/"):
            if len(path) > len(best):
                best = path
    return paths[best] if best else OUTSIDE


def gsc_rows(month: str, response: dict, paths: dict[str, str]) -> list[dict]:
    """Search Console の searchAnalytics(dimensions=["page"])を行にする。

    店舗ごとに、クリック・表示回数を足し上げる。CTRと平均掲載順位は**足さない** —
    率と順位は表示回数で重みづけしないと意味が壊れるため、ここで再計算する。
    """
    totals: dict[str, dict[str, float]] = {}
    for row in response.get("rows", []):
        keys = row.get("keys") or []
        if not keys:
            continue
        store = store_of_page(keys[0], paths)
        bucket = totals.setdefault(store, {"clicks": 0.0, "impressions": 0.0,
                                           "position_weighted": 0.0})
        clicks = float(row.get("clicks", 0) or 0)
        impressions = float(row.get("impressions", 0) or 0)
        bucket["clicks"] += clicks
        bucket["impressions"] += impressions
        # 平均掲載順位は表示回数で重みづけして合成する。単純平均だと、
        # 表示1回のページと1万回のページが同じ重みになる。
        bucket["position_weighted"] += float(row.get("position", 0) or 0) * impressions

    rows = []
    for store, bucket in sorted(totals.items()):
        impressions = bucket["impressions"]
        rows.append({"month": month, "store": store, "channel": "SEO",
                     "metric": "クリック", "value": bucket["clicks"]})
        rows.append({"month": month, "store": store, "channel": "SEO",
                     "metric": "表示回数", "value": impressions})
        if impressions:
            rows.append({"month": month, "store": store, "channel": "SEO",
                         "metric": "CTR", "value": bucket["clicks"] / impressions})
            rows.append({"month": month, "store": store, "channel": "SEO",
                         "metric": "平均掲載順位",
                         "value": bucket["position_weighted"] / impressions})
    return rows


def ga4_rows(month: str, store: str, response: dict) -> list[dict]:
    """GA4 runReport(ディメンション1つ=チャネル、指標は複数)を行にする。

    ディメンションと指標の名前は応答のヘッダから読む。**問い合わせ側の指定を
    ここに写さない** — 写すと、問い合わせを変えたときに黙ってずれる。
    """
    dimension_headers = [h.get("name") for h in response.get("dimensionHeaders", [])]
    metric_headers = [h.get("name") for h in response.get("metricHeaders", [])]

    rows = []
    for row in response.get("rows", []):
        values = [v.get("value") for v in row.get("dimensionValues", [])]
        channel = values[0] if values and dimension_headers else "(全体)"
        for index, metric in enumerate(row.get("metricValues", [])):
            name = metric_headers[index] if index < len(metric_headers) else f"metric{index}"
            raw = metric.get("value")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                # 数値でない指標は落とす。文字列を数値の列に混ぜない。
                continue
            rows.append({"month": month, "store": store, "channel": channel,
                         "metric": name, "value": value})
    return rows


def to_tsv(rows: list[dict]) -> str:
    """統合ログの行をTSVにする。シートへ貼るのも、差分を見るのもこれで足りる。"""
    lines = ["年月\t店舗\tチャネル\t指標\t値"]
    for row in rows:
        value = row["value"]
        text = f"{value:g}" if isinstance(value, float) else str(value)
        lines.append(f"{row['month']}\t{row['store']}\t{row['channel']}\t"
                     f"{row['metric']}\t{text}")
    return "\n".join(lines) + "\n"
