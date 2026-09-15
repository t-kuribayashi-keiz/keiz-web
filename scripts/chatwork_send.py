#!/usr/bin/env python3
"""Deliver queued Chatwork messages that Claude wrote, then clear them from the queue.

Claude cannot call Chatwork itself — the token lives in GitHub Secrets and only reaches GitHub
Actions — so Claude writes a message into data/chatwork-outbox/ and this script, running in
Actions, posts it. See .claude/skills/chatwork-integration/SKILL.md.

Two message kinds may be sent without a per-message approval (see ALLOWED_KINDS/KIND_CONFIG):
"hearing" (gathering information needed to act on a request) and "status_report" (a scheduled
automation reporting whether it ran, e.g. hpb-review-blog-check's monthly job). Each kind is
gated per-room by its own flag in data/chatwork-rooms.json, so opting a room into one doesn't
opt it into the other.

Every delivered message carries a visible "Claudeによる自動確認" header, for two reasons: the
token belongs to a real person's account, so without it the recipient would think that person
wrote the message; and the watcher uses the same string to skip Claude's own posts instead of
re-detecting them.

Exit codes:
  0  ran fine (delivered nothing, or delivered everything queued)
  1  configuration or API problem
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.chatwork.com/v2"
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "data" / "chatwork-rooms.json"
OUTBOX_DIR = REPO_ROOT / "data" / "chatwork-outbox"

# Prefixed to every auto-sent message. The watcher skips messages containing this string, so
# changing it means changing AUTO_POST_MARKER in chatwork_watcher.py at the same time.
AUTO_POST_MARKER = "Claudeによる自動確認"

# Only these kinds may be delivered without a per-message approval from the user. "hearing" is
# a question gathering information needed to act; "status_report" is a scheduled automation
# (GitHub Actions cron job) reporting whether it ran and what it did, to a room the user has
# specifically opted in for that purpose (data/chatwork-rooms.json's allow_auto_status_report).
# Anything else that commits to work, reports on a business decision, or answers a business
# question is not covered by either standing permission.
ALLOWED_KINDS = {"hearing", "status_report"}

# kind -> (room permission flag required, max body length, message framing under the header)
KIND_CONFIG = {
    "hearing": {
        "permission_flag": "allow_auto_hearing",
        "max_body_chars": 1500,
        "intro": (
            "ご依頼の対応にあたって確認させてください。"
            "この確認は自動送信で、回答いただいた内容は担当者が確認のうえ着手します。"
        ),
    },
    "status_report": {
        "permission_flag": "allow_auto_status_report",
        "max_body_chars": 3000,
        "intro": "定期実行(GitHub Actions)からの自動レポートです。返信は不要です。",
    },
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def api_post(path: str, token: str, fields: dict[str, str]) -> dict:
    url = f"{API_BASE}{path}"
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "X-ChatWorkToken": token,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        if error.code == 401:
            fail("Chatwork returned 401. Update the CHATWORK_API_TOKEN secret.")
        if error.code == 403:
            fail(f"Chatwork returned 403 for {path}: the account cannot post to that room.")
        fail(f"Chatwork API {error.code} for {path}: {detail}")
    except urllib.error.URLError as error:
        fail(f"Could not reach the Chatwork API for {path}: {error.reason}")


def api_get(path: str, token: str):
    request = urllib.request.Request(f"{API_BASE}{path}", headers={"X-ChatWorkToken": token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401:
            fail("Chatwork returned 401. Update the CHATWORK_API_TOKEN secret.")
        fail(f"Chatwork API {error.code} for {path}")
    except urllib.error.URLError as error:
        fail(f"Could not reach the Chatwork API for {path}: {error.reason}")


def load_rooms() -> dict[str, dict]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {room["room_name"].strip(): room for room in config.get("rooms", [])}


def resolve_room_id(room_name: str, token: str) -> int:
    rooms = api_get("/rooms", token) or []
    matches = [r["room_id"] for r in rooms if str(r.get("name", "")).strip() == room_name]
    if not matches:
        fail(f"Room {room_name!r} is not visible to this token — is the account still a member?")
    if len(matches) > 1:
        fail(f"Room name {room_name!r} matched {len(matches)} rooms; cannot pick one safely.")
    return matches[0]


def render_body(message: dict) -> str:
    """Wrap the message so the recipient can see it was sent automatically, not typed by hand."""
    body = message["body"].strip()
    reply_to = message.get("in_reply_to_message_id")
    intro = KIND_CONFIG[message["kind"]]["intro"]
    lines = [
        f"[info][title]{AUTO_POST_MARKER}[/title]",
        intro,
        "",
        body,
        "[/info]",
    ]
    if reply_to:
        # A plain reference, not Chatwork's [rp] tag: [rp] needs the replier's own account id,
        # which is the token owner's, and would render as if they had hit reply themselves.
        lines.insert(0, "")
    return "\n".join(lines).strip()


def validate(message: dict, path: Path, rooms: dict[str, dict]) -> dict:
    for field in ("room_name", "kind", "body"):
        if not str(message.get(field, "")).strip():
            fail(f"{path.name}: missing required field {field!r}")

    kind = message["kind"]
    if kind not in ALLOWED_KINDS:
        fail(
            f"{path.name}: kind {kind!r} may not be sent automatically "
            f"(allowed: {sorted(ALLOWED_KINDS)}). Anything beyond gathering information needs "
            f"the user's approval for that specific message."
        )

    room_name = message["room_name"].strip()
    room = rooms.get(room_name)
    if room is None:
        fail(f"{path.name}: room {room_name!r} is not in data/chatwork-rooms.json")

    config = KIND_CONFIG[kind]
    permission_flag = config["permission_flag"]
    if not room.get(permission_flag):
        fail(
            f"{path.name}: room {room_name!r} does not have {permission_flag} set, so a "
            f"{kind!r} message may not be posted to it automatically."
        )

    max_chars = config["max_body_chars"]
    if len(message["body"]) > max_chars:
        fail(
            f"{path.name}: body is {len(message['body'])} characters (limit {max_chars} for "
            f"kind {kind!r}). Ask for what is needed in one consolidated message."
        )

    if AUTO_POST_MARKER in message["body"]:
        fail(f"{path.name}: body must not contain the auto-post marker itself.")

    return message


def main() -> int:
    token = os.environ.get("CHATWORK_API_TOKEN", "").strip()
    if not token:
        fail("CHATWORK_API_TOKEN is not set.")

    if not OUTBOX_DIR.exists():
        print("no outbox directory; nothing to send", file=sys.stderr)
        return 0

    queued = sorted(path for path in OUTBOX_DIR.glob("*.json"))
    if not queued:
        print("outbox empty", file=sys.stderr)
        return 0

    rooms = load_rooms()
    sent = 0
    for path in queued:
        try:
            message = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            fail(f"{path.name}: not valid JSON ({error})")

        validate(message, path, rooms)
        room_id = resolve_room_id(message["room_name"].strip(), token)
        result = api_post(
            f"/rooms/{room_id}/messages", token, {"body": render_body(message)}
        )
        print(
            f"sent {path.name} to {message['room_name']} "
            f"(message_id={result.get('message_id')})",
            file=sys.stderr,
        )
        # Delivered messages are removed so a re-run can't double-post. The Issue thread and
        # Chatwork itself are the record of what was asked.
        path.unlink()
        sent += 1

    print(f"delivered={sent}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
