"""analytics_pull.py の純粋関数(month_range)の回帰テスト。

APIは叩かない。credentials()は環境変数が無いと失敗するので、ここではテストしない。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analytics_pull as pull  # noqa: E402


class TestMonthRange(unittest.TestCase):
    def test_gou_suffix(self):
        self.assertEqual(pull.month_range("2026年08月号"), ("2026-08-01", "2026-08-31"))

    def test_without_gou_suffix(self):
        self.assertEqual(pull.month_range("2026年8月"), ("2026-08-01", "2026-08-31"))

    def test_last_day_follows_the_calendar(self):
        self.assertEqual(pull.month_range("2026年02月号"), ("2026-02-01", "2026-02-28"))
        self.assertEqual(pull.month_range("2024年02月号"), ("2024-02-01", "2024-02-29"))
        self.assertEqual(pull.month_range("2026年04月号"), ("2026-04-01", "2026-04-30"))

    def test_unparseable_label_raises(self):
        with self.assertRaises(ValueError):
            pull.month_range("8月")


if __name__ == "__main__":
    unittest.main()
