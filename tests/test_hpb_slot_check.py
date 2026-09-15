#!/usr/bin/env python3
"""hpb_slot_check.pyのうち、ネットワーク/認証を使わずに検証できる部分のテスト。

judge_occupancy_rateの閾値やAM/PM境界を間違えると、K/L列が静かに間違った値で
埋まる(見た目は普通の○/✕なので気づきにくい)。ここで固定しておく。
"""

import datetime
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import hpb_slot_check as slot_check  # noqa: E402


class TestParseTime(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slot_check.parse_time("09:30"), 9 * 60 + 30)
        self.assertEqual(slot_check.parse_time("13:00"), 13 * 60)

    def test_fullwidth_colon(self):
        self.assertEqual(slot_check.parse_time("09：30"), 9 * 60 + 30)

    def test_empty_or_invalid(self):
        self.assertIsNone(slot_check.parse_time(""))
        self.assertIsNone(slot_check.parse_time(None))
        self.assertIsNone(slot_check.parse_time("不明"))


class TestIsWeekendOrHoliday(unittest.TestCase):
    def test_weekday(self):
        # 2026-09-03は木曜
        self.assertFalse(slot_check.is_weekend_or_holiday(datetime.datetime(2026, 9, 3)))

    def test_weekend(self):
        # 2026-09-05は土曜
        self.assertTrue(slot_check.is_weekend_or_holiday(datetime.datetime(2026, 9, 5)))

    def test_holiday(self):
        # 2026-09-22は秋分の日(祝)
        self.assertTrue(slot_check.is_weekend_or_holiday(datetime.datetime(2026, 9, 22)))


class TestJudgeOccupancyRate(unittest.TestCase):
    AM_START, AM_END = 9 * 60, 13 * 60

    def test_no_slots_returns_dash(self):
        self.assertEqual(
            slot_check.judge_occupancy_rate([], self.AM_START, self.AM_END, None, None, True), "-"
        )

    def test_all_ok_returns_maru(self):
        slots = [{"time": "09:00", "status": "○"}, {"time": "10:00", "status": "◎"}]
        self.assertEqual(
            slot_check.judge_occupancy_rate(slots, self.AM_START, self.AM_END, None, None, True), "○"
        )

    def test_majority_ng_returns_batsu(self):
        slots = [
            {"time": "09:00", "status": "×"},
            {"time": "10:00", "status": "×"},
            {"time": "11:00", "status": "○"},
        ]
        self.assertEqual(
            slot_check.judge_occupancy_rate(slots, self.AM_START, self.AM_END, None, None, True), "✕"
        )

    def test_pm_slot_excluded_from_am_window(self):
        # 13:00以降はPM側なので、is_am=Trueのときは対象外 -> 判定材料なし
        slots = [{"time": "14:00", "status": "×"}]
        self.assertEqual(
            slot_check.judge_occupancy_rate(slots, self.AM_START, self.AM_END, None, None, True), "-"
        )

    def test_break_time_excluded(self):
        # 12:00-13:00が休憩なら、その枠は判定に含めない
        slots = [{"time": "12:30", "status": "×"}, {"time": "09:00", "status": "○"}]
        result = slot_check.judge_occupancy_rate(
            slots, self.AM_START, self.AM_END, 12 * 60, 13 * 60, True
        )
        self.assertEqual(result, "○")

    def test_tel_counts_as_ng(self):
        slots = [{"time": "09:00", "status": "TEL"}]
        self.assertEqual(
            slot_check.judge_occupancy_rate(slots, self.AM_START, self.AM_END, None, None, True), "✕"
        )


if __name__ == "__main__":
    unittest.main()
