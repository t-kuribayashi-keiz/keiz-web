#!/usr/bin/env python3
"""hpb_review_blog_check.py の月次自動実行の結果を、Chatworkの送信キューに積む。

このスクリプト自身はChatworkに投稿しない(トークンを持たない設計、
functions/chatwork-integration/CLAUDE.md参照)。data/chatwork-outbox/ にJSONを書き出すだけで、
実際の送信は同じワークフロー内で後続する scripts/chatwork_send.py が行う。

kind は "status_report" 固定。対象ルーム(data/chatwork-rooms.json)は
allow_auto_status_report: true が付いている必要がある。

使い方:
  python scripts/notify_hpb_review_blog_check.py --month 202609 --status success --csv hpb_review_blog_202609.csv
  python scripts/notify_hpb_review_blog_check.py --month 202609 --status failure --log run.log
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTBOX_DIR = REPO_ROOT / "data" / "chatwork-outbox"
ROOM_NAME = "マイチャット"
MAX_ERROR_NAMES_SHOWN = 10
LOG_TAIL_CHARS = 800


def build_success_body(month: str, csv_path: Path) -> str:
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    errors = [r for r in rows if r.get("error")]
    ok = total - len(errors)

    lines = [
        f"【HPB口コミ・ブログ 月次自動集計】{month[:4]}年{int(month[4:])}月分",
        "",
        f"対象院数: {total}院 / 正常取得: {ok}院 / 取得エラー: {len(errors)}院",
        "スプレッドシート「口コミブログチェック表」への書き込みも完了しました。",
    ]
    if errors:
        lines.append("")
        lines.append("取得エラーになった院(掲載終了などの可能性、確認推奨):")
        for r in errors[:MAX_ERROR_NAMES_SHOWN]:
            lines.append(f"・{r['name']}: {r.get('error', '')[:80]}")
        if len(errors) > MAX_ERROR_NAMES_SHOWN:
            lines.append(f"...ほか{len(errors) - MAX_ERROR_NAMES_SHOWN}院")
    return "\n".join(lines)


def build_failure_body(month: str, log_path: Path | None) -> str:
    lines = [
        f"【HPB口コミ・ブログ 月次自動集計】{month[:4]}年{int(month[4:])}月分",
        "",
        "⚠️ 実行中にエラーが発生し、スプレッドシートへの書き込みは完了していません。",
    ]
    if log_path and log_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-LOG_TAIL_CHARS:]
        lines.append("")
        lines.append("直近のログ:")
        lines.append(tail.strip())
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="対象月 YYYYMM")
    parser.add_argument("--status", choices=["success", "failure"], required=True)
    parser.add_argument("--csv", default=None, help="--status success のときのCSVパス")
    parser.add_argument("--log", default=None, help="--status failure のときのログファイルパス")
    args = parser.parse_args()

    if args.status == "success":
        if not args.csv:
            print("エラー: --status success には --csv が必要です", file=sys.stderr)
            return 1
        body = build_success_body(args.month, Path(args.csv))
    else:
        body = build_failure_body(args.month, Path(args.log) if args.log else None)

    message = {
        "room_name": ROOM_NAME,
        "kind": "status_report",
        "body": body,
    }

    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUTBOX_DIR / f"hpb-review-blog-check_{ts}_{uuid.uuid4().hex[:8]}.json"
    out_path.write_text(json.dumps(message, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"queued: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
