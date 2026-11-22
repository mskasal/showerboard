import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import timeutil as tu

try:
    from zoneinfo import ZoneInfo
    BERLIN = ZoneInfo("Europe/Berlin")
except Exception:
    BERLIN = None


def utc(*a):
    return int(datetime(*a, tzinfo=timezone.utc).timestamp())


class CivilTest(unittest.TestCase):
    def test_epoch_matches_datetime(self):
        d = datetime(1999, 12, 25, tzinfo=timezone.utc)
        for _ in range(0, 15000, 7):
            e = int(d.timestamp())
            self.assertEqual(tu.to_epoch(d.year, d.month, d.day, d.hour), e)
            self.assertEqual(tu.civil_from_days(e // 86400), (d.year, d.month, d.day))
            self.assertEqual(tu.weekday(e // 86400), d.weekday())
            d += timedelta(days=7, hours=5)

    def test_last_sunday(self):
        self.assertEqual(tu.last_sunday(2026, 3), 29)
        self.assertEqual(tu.last_sunday(2026, 10), 25)
        self.assertEqual(tu.last_sunday(2027, 3), 28)
        self.assertEqual(tu.last_sunday(2027, 10), 31)
        self.assertEqual(tu.last_sunday(2024, 3), 31)


class DstTest(unittest.TestCase):
    def test_spring_forward_2026(self):
        self.assertEqual(tu.berlin_offset(utc(2026, 3, 29, 0, 59, 59)), 3600)
        self.assertEqual(tu.berlin_offset(utc(2026, 3, 29, 1, 0, 0)), 7200)
        self.assertEqual(tu.hhmm(utc(2026, 3, 29, 0, 59)), "01:59")
        self.assertEqual(tu.hhmm(utc(2026, 3, 29, 1, 0)), "03:00")

    def test_fall_back_2026(self):
        # 25 Ekim 2026: 03:00 CEST -> 02:00 CET
        self.assertEqual(tu.berlin_offset(utc(2026, 10, 25, 0, 59, 59)), 7200)
        self.assertEqual(tu.berlin_offset(utc(2026, 10, 25, 1, 0, 0)), 3600)
        self.assertEqual(tu.hhmm(utc(2026, 10, 25, 0, 30)), "02:30")
        self.assertEqual(tu.hhmm(utc(2026, 10, 25, 1, 30)), "02:30")

    def test_morning_after_change(self):
        self.assertEqual(tu.hhmm(utc(2026, 10, 26, 6, 31)), "07:31")   # CET
        self.assertEqual(tu.hhmm(utc(2026, 10, 23, 5, 31)), "07:31")   # CEST

    @unittest.skipIf(BERLIN is None, "zoneinfo yok")
    def test_hourly_against_zoneinfo(self):
        t = utc(2024, 1, 1)
        end = utc(2028, 1, 1)
        while t < end:
            ref = datetime.fromtimestamp(t, BERLIN)
            b = tu.berlin(t)
            self.assertEqual(b[:5], (ref.year, ref.month, ref.day, ref.hour, ref.minute), t)
            self.assertEqual(b[6], ref.weekday())
            t += 3600 + 60 * 7

    def test_berlin_to_utc(self):
        self.assertEqual(tu.berlin_to_utc(2026, 10, 26, 6, 30), utc(2026, 10, 26, 5, 30))
        self.assertEqual(tu.berlin_to_utc(2026, 7, 1, 6, 30), utc(2026, 7, 1, 4, 30))
        self.assertEqual(tu.berlin_to_utc(2026, 3, 30, 6, 30), utc(2026, 3, 30, 4, 30))


class IsoTest(unittest.TestCase):
    def test_offsets(self):
        self.assertEqual(tu.parse_iso("2026-10-25T07:42:00+01:00"), utc(2026, 10, 25, 6, 42))
        self.assertEqual(tu.parse_iso("2026-07-01T07:42:00+02:00"), utc(2026, 7, 1, 5, 42))
        self.assertEqual(tu.parse_iso("2026-07-01T05:42:00Z"), utc(2026, 7, 1, 5, 42))
        self.assertEqual(tu.parse_iso("2026-07-01T05:42:00.123Z"), utc(2026, 7, 1, 5, 42))
        self.assertEqual(tu.parse_iso("2026-01-01T00:10:00+01:00"), utc(2025, 12, 31, 23, 10))

    def test_dst_boundary_same_instant(self):
        # Geri alma gecesi aynı yerel saat iki farklı ofsetle
        a = tu.parse_iso("2026-10-25T02:30:00+02:00")
        b = tu.parse_iso("2026-10-25T02:30:00+01:00")
        self.assertEqual(b - a, 3600)

    def test_invalid(self):
        for s in ("", None, "2026-10-25 07:42:00+01:00", "2026-10-25T07:42:00",
                  "2026-13-01T00:00:00Z", "2026-10-25T07:42:00+0100", "garbage"):
            with self.assertRaises(ValueError):
                tu.parse_iso(s)

    def test_iso_utc_roundtrip(self):
        t = utc(2026, 10, 25, 6, 42, 5)
        self.assertEqual(tu.iso_utc(t), "2026-10-25T06:42:05Z")
        self.assertEqual(tu.parse_iso(tu.iso_utc(t)), t)


if __name__ == "__main__":
    unittest.main()
