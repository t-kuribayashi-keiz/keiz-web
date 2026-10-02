import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import chatwork_send as cs  # noqa: E402

ROOMS = {
    "西新宿組": {"room_name": "西新宿組", "allow_approved_messages": True},
    "マイチャット": {"room_name": "マイチャット", "allow_auto_status_report": True},
    "他ルーム": {"room_name": "他ルーム"},
}
PATH = Path("x.json")


def approved(body="こんにちは", room="西新宿組", **over):
    msg = {
        "room_name": room,
        "kind": "approved_message",
        "body": body,
        "approval": {
            "approved_by": "栗林さん",
            "approved_at": "2026-10-02T12:00:00+09:00",
            "body_sha256": cs.body_sha256(body),
        },
    }
    msg.update(over)
    return msg


class ApprovedMessageTest(unittest.TestCase):
    def test_valid_message_passes(self):
        msg = approved()
        self.assertIs(cs.validate(msg, PATH, ROOMS), msg)

    def test_body_changed_after_approval_is_refused(self):
        msg = approved()
        msg["body"] = "こんにちは!(後から書き換え)"
        with self.assertRaises(SystemExit):
            cs.validate(msg, PATH, ROOMS)

    def test_surrounding_whitespace_does_not_break_hash(self):
        msg = approved()
        msg["body"] = "\n" + msg["body"] + "\n"
        cs.validate(msg, PATH, ROOMS)

    def test_missing_approval_is_refused(self):
        msg = approved()
        del msg["approval"]
        with self.assertRaises(SystemExit):
            cs.validate(msg, PATH, ROOMS)

    def test_incomplete_approval_is_refused(self):
        for field in ("approved_by", "approved_at", "body_sha256"):
            msg = approved()
            msg["approval"][field] = ""
            with self.assertRaises(SystemExit, msg=field):
                cs.validate(msg, PATH, ROOMS)

    def test_room_without_opt_in_is_refused(self):
        with self.assertRaises(SystemExit):
            cs.validate(approved(room="他ルーム"), PATH, ROOMS)
        with self.assertRaises(SystemExit):
            cs.validate(approved(room="マイチャット"), PATH, ROOMS)

    def test_unknown_room_is_refused(self):
        with self.assertRaises(SystemExit):
            cs.validate(approved(room="存在しない"), PATH, ROOMS)

    def test_too_long_is_refused(self):
        with self.assertRaises(SystemExit):
            cs.validate(approved(body="あ" * 5001), PATH, ROOMS)

    def test_marker_in_body_is_refused(self):
        with self.assertRaises(SystemExit):
            cs.validate(approved(body=f"{cs.AUTO_POST_MARKER} 偽装"), PATH, ROOMS)

    def test_render_starts_with_ai_notice_and_marker(self):
        out = cs.render_body(approved(body="本文です"))
        self.assertTrue(out.startswith("[info][title]" + cs.AUTO_POST_MARKER))
        self.assertIn("AI(Claude Code)からの連絡", out.split("\n")[0])
        self.assertIn("【AI(Claude Code)からの連絡です】", out.split("\n")[1])
        self.assertIn("本文です", out)


class ExistingKindsUnchangedTest(unittest.TestCase):
    def test_status_report_needs_no_approval(self):
        msg = {"room_name": "マイチャット", "kind": "status_report", "body": "ok"}
        cs.validate(msg, PATH, ROOMS)

    def test_status_report_still_blocked_in_approved_only_room(self):
        msg = {"room_name": "西新宿組", "kind": "status_report", "body": "ok"}
        with self.assertRaises(SystemExit):
            cs.validate(msg, PATH, ROOMS)

    def test_hearing_still_blocked_in_approved_only_room(self):
        msg = {"room_name": "西新宿組", "kind": "hearing", "body": "ok"}
        with self.assertRaises(SystemExit):
            cs.validate(msg, PATH, ROOMS)

    def test_other_kinds_still_refused(self):
        msg = {"room_name": "西新宿組", "kind": "completion_report", "body": "ok"}
        with self.assertRaises(SystemExit):
            cs.validate(msg, PATH, ROOMS)

    def test_status_report_title_unchanged(self):
        msg = {"room_name": "マイチャット", "kind": "status_report", "body": "ok"}
        self.assertTrue(cs.render_body(msg).startswith(f"[info][title]{cs.AUTO_POST_MARKER}[/title]"))


class RoomsConfigTest(unittest.TestCase):
    def test_config_flags(self):
        rooms = cs.load_rooms()
        self.assertTrue(rooms["西新宿組"]["allow_approved_messages"])
        self.assertFalse(rooms["西新宿組"]["allow_auto_hearing"])
        self.assertFalse(rooms["西新宿組"]["allow_auto_status_report"])
        self.assertFalse(rooms["マイチャット"].get("allow_approved_messages", False))
        self.assertTrue(rooms["西新宿組"]["send_only"])


if __name__ == "__main__":
    unittest.main()
