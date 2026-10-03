#!/usr/bin/env python3
"""hpb_slot_check.py の毎日実行の結果(✕の店舗一覧)を、Chatworkの送信キューに積む。

このスクリプト自身はChatworkに投稿しない(トークンを持たない設計、
functions/chatwork-integration/CLAUDE.md参照)。data/chatwork-outbox/ にJSONを書き出すだけで、
実際の送信は同じワークフロー内で後続する scripts/chatwork_send.py が行う。

使い方:
  python scripts/notify_hpb_slot_check.py --status success --summary slot_summary.json
  python scripts/notify_hpb_slot_check.py --status failure --log run.log
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTBOX_DIR = REPO_ROOT / "data" / "chatwork-outbox"
ROOM_NAME = "マイチャット"
MAX_SHOPS_SHOWN = 30
LOG_TAIL_CHARS = 800


def build_success_body(summary: dict) -> str:
    ng = summary.get("ng_shops", [])
    lines = [
        "【HPB予約枠チェック 日次自動実行】",
        f"対象期間: {summary.get('window', '')}",
        f"○{summary.get('ok', 0)}店 / ✕{summary.get('ng', 0)}店 / ?{summary.get('unknown', 0)}店",
    ]
    if ng:
        lines += ["", "✕になった店舗(SalonBoard側の確認推奨):"]
        for s in ng[:MAX_SHOPS_SHOWN]:
            lines.append(f"・{s['name']}")
        if len(ng) > MAX_SHOPS_SHOWN:
            lines.append(f"...ほか{len(ng) - MAX_SHOPS_SHOWN}店")
    else:
        lines += ["", "✕の店舗はありませんでした。"]
    return "\n".join(lines)


def build_failure_body(log_path: Path | None) -> str:
    lines = [
        "【HPB予約枠チェック 日次自動実行】",
        "",
        "⚠️ 実行中にエラーが発生し、シートへの書き込みは完了していません。",
    ]
    if log_path and log_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-LOG_TAIL_CHARS:]
        lines += ["", "直近のログ:", tail.strip()]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=["success", "failure"], required=True)
    parser.add_argument("--summary", default=None)
    parser.add_argument("--log", default=None)
    args = parser.parse_args()

    if args.status == "success":
        sp = Path(args.summary) if args.summary else None
        if not sp or not sp.exists():
            body = build_failure_body(Path(args.log) if args.log else None)
        else:
            body = build_success_body(json.loads(sp.read_text(encoding="utf-8")))
    else:
        body = build_failure_body(Path(args.log) if args.log else None)

    message = {"room_name": ROOM_NAME, "kind": "status_report", "body": body}
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUTBOX_DIR / f"hpb-slot-check_{ts}_{uuid.uuid4().hex[:8]}.json"
    out_path.write_text(json.dumps(message, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"queued: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
