import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import logic
import timeutil as tu

CFG = {"YURUME_DK": 7, "HAZIRLIK_DK": 5, "DIRECT_LINES": ["S5", "S7"], "DIRECTIONS": [],
       "MAX_DATA_AGE_S": 180, "MAX_REALTIME_AGE_S": 300, "WIFI_SSID": "x", "STOP_ID": "900100003"}
# Pazartesi 26.10.2026 07:31:00 Berlin (CET, UTC+1)
NOW = tu.to_epoch(2026, 10, 26, 6, 31, 0)
VALID = NOW + 60


def raw(line, planned, when=None, delay=0, direction="S Westkreuz (Berlin)", cancelled=False):
    # API'deki gibi bir kalkış nesnesi (yerel saat, +01:00)
    d = {"line": {"name": line}, "plannedWhen": "2026-10-26T%s:00+01:00" % planned,
         "when": None if cancelled else "2026-10-26T%s:00+01:00" % (when or planned),
         "delay": None if cancelled else delay, "direction": direction}
    if cancelled:
        d["cancelled"] = True
    return d


def slim(*a, **k):
    return logic.slim_departure(raw(*a, **k))


class SlimTest(unittest.TestCase):
    def test_uses_realtime_when(self):
        d = slim("S5", "07:45", when="07:48", delay=180)
        self.assertEqual(d["when"], tu.to_epoch(2026, 10, 26, 6, 48))
        self.assertEqual(d["planned"], tu.to_epoch(2026, 10, 26, 6, 45))

    def test_cancelled_skipped(self):
        self.assertIsNone(slim("S5", "07:45", cancelled=True))
        r = raw("S5", "07:45")
        r["cancelled"] = True        # "when" dolu olsa bile
        self.assertIsNone(logic.slim_departure(r))

    def test_no_realtime(self):
        d = slim("S7", "07:50", delay=None)
        rows = logic.select_rows([d], NOW, VALID, 7, 5, ["S5", "S7"])
        self.assertFalse(rows[0]["realtime"])
        self.assertIsNone(rows[0]["delay_min"])


class LeaveTest(unittest.TestCase):
    def test_formula(self):
        dep = NOW + 20 * 60
        self.assertEqual(logic.leave_seconds(dep, NOW, 7, 5), 8 * 60)

    def test_delay_extends_time(self):
        # Planlı 07:45 ama 3 dk rötar: kalan rötarlı zamana göre
        deps = [slim("S5", "07:45", when="07:48", delay=180)]
        r = logic.select_rows(deps, NOW, VALID, 7, 5, ["S5", "S7"])[0]
        # 07:48 - 07:31 - 12 = 5 dk; bir sonraki yenilemeye kadar geçerli olan 4
        self.assertEqual(r["minutes"], 4)
        self.assertEqual(r["delay_min"], 3)
        self.assertFalse(r["urgent"])

    def test_minutes_never_overstate(self):
        # Ekrandaki sayı, gösterildiği süre boyunca hiç fazla olmamalı
        dep = NOW + 17 * 60 + 30
        d = {"line": "S5", "when": dep, "planned": dep, "delay": 0, "direction": ""}
        for now in range(NOW, NOW + 60):
            valid = (now // 60 + 1) * 60
            r = logic.select_rows([d], now, valid, 7, 5, ["S5"])[0]
            for t in range(now, valid + 1):
                self.assertGreaterEqual(logic.leave_seconds(dep, t, 7, 5), r["minutes"] * 60)

    def test_urgent_window(self):
        for left, urgent in ((0, True), (59, True), (119, True), (120, False)):
            dep = NOW + 12 * 60 + left
            d = {"line": "S5", "when": dep, "planned": dep, "delay": 0, "direction": ""}
            r = logic.select_rows([d], NOW, VALID, 7, 5, ["S5"])
            self.assertEqual(r[0]["urgent"], urgent, left)

    def test_no_time_to_prepare_is_urgent(self):
        # 7 dk yürüme + 5 dk hazırlık; 10 dk kaldı: hazırlığa vakit yok ama yetişilir
        dep = NOW + 10 * 60
        d = {"line": "S5", "when": dep, "planned": dep, "delay": 0, "direction": ""}
        r = logic.select_rows([d], NOW, VALID, 7, 5, ["S5"])
        self.assertEqual((r[0]["missed"], r[0]["urgent"], r[0]["minutes"]), (False, True, 0))

    def test_missed_train_kept_until_departure(self):
        dep = NOW + 7 * 60 - 1
        d = {"line": "S5", "when": dep, "planned": dep, "delay": 0, "direction": ""}
        r = logic.select_rows([d], NOW, VALID, 7, 5, ["S5"])
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0]["missed"])
        self.assertFalse(r[0]["urgent"])

    def test_departed_train_dropped(self):
        d = {"line": "S5", "when": NOW - 1, "planned": NOW - 1, "delay": 0, "direction": ""}
        self.assertEqual(logic.select_rows([d], NOW, VALID, 7, 5, ["S5"]), [])


class SelectTest(unittest.TestCase):
    def lines(self, deps, directions=()):
        return [(r["line"], tu.hhmm(r["when"]))
                for r in logic.select_rows(deps, NOW, VALID, 7, 5, ["S5", "S7"], directions)]

    def test_direct_first_s75_before_second(self):
        deps = [slim("S75", "07:44"), slim("S5", "07:47"), slim("S7", "07:57")]
        self.assertEqual(self.lines(deps), [("S5", "07:47"), ("S75", "07:44")])

    def test_direct_then_next(self):
        deps = [slim("S5", "07:47"), slim("S75", "07:50"), slim("S7", "07:57")]
        self.assertEqual(self.lines(deps), [("S5", "07:47"), ("S75", "07:50")])

    def test_only_s75(self):
        deps = [slim("S75", "07:44"), slim("S75", "07:54")]
        self.assertEqual(self.lines(deps), [("S75", "07:44"), ("S75", "07:54")])

    def test_unsorted_input_and_cancel(self):
        deps = [slim("S7", "07:57"), slim("S5", "07:47", cancelled=True), slim("S5", "07:50")]
        self.assertEqual(self.lines(deps), [("S5", "07:50"), ("S7", "07:57")])

    def test_delay_reorders(self):
        # S5 07:45 +8 -> 07:53, S7 07:50 zamanında: ilk yakalanabilir direkt S7
        deps = [slim("S5", "07:45", when="07:53", delay=480), slim("S7", "07:50")]
        self.assertEqual(self.lines(deps), [("S7", "07:50"), ("S5", "07:53")])

    def test_missed_then_catchable(self):
        # 07:31'de, 7 dk yürüme: 07:37 S5 kaçtı, 07:44 S75 ve 07:47 S7 yakalanabilir
        deps = [slim("S5", "07:37"), slim("S75", "07:44"), slim("S7", "07:47")]
        rows = logic.select_rows(deps, NOW, VALID, 7, 5, ["S5", "S7"])
        self.assertEqual([(r["line"], r["missed"]) for r in rows], [("S5", True), ("S7", False)])

    def test_missed_prefers_latest_direct(self):
        deps = [slim("S7", "07:33"), slim("S5", "07:35"), slim("S75", "07:37"),
                slim("S7", "07:47")]
        self.assertEqual(self.lines(deps), [("S5", "07:35"), ("S7", "07:47")])

    def test_direction_filter(self):
        deps = [slim("S5", "07:47", direction="S Strausberg Nord"),
                slim("S5", "07:49", direction="S Westkreuz (Berlin)")]
        self.assertEqual(self.lines(deps, ["Westkreuz"]), [("S5", "07:49")])
        self.assertEqual(len(self.lines(deps)), 2)


class ViewTest(unittest.TestCase):
    def deps(self):
        return [slim("S5", "07:50")]

    def test_ok(self):
        v = logic.transit_view(NOW, VALID, CFG, self.deps(), True, NOW - 30)
        self.assertEqual(v["status"], "ok")

    def test_fetch_failed_shows_nodata(self):
        v = logic.transit_view(NOW, VALID, CFG, self.deps(), False, NOW - 30)
        self.assertEqual(v, {"status": "nodata", "rows": []})

    def test_stale(self):
        v = logic.transit_view(NOW, VALID, CFG, self.deps(), True, VALID - 181)
        self.assertEqual(v["status"], "stale")
        self.assertEqual(v["rows"], [])
        v = logic.transit_view(NOW, VALID, CFG, self.deps(), True, VALID - 180)
        self.assertEqual(v["status"], "ok")

    def test_realtime_stale(self):
        v = logic.transit_view(NOW, VALID, CFG, self.deps(), True, NOW, rt_time=VALID - 301)
        self.assertEqual(v["status"], "stale")

    def test_none(self):
        v = logic.transit_view(NOW, VALID, CFG, [], True, NOW)
        self.assertEqual(v["status"], "none")


class ActiveHoursTest(unittest.TestCase):
    AH = {0: [("06:30", "09:00")], 1: [("06:30", "09:00")], 2: [("06:30", "09:00")],
          3: [("06:30", "09:00")], 4: [("06:30", "09:00")], 5: [], 6: []}

    def test_active(self):
        self.assertTrue(logic.is_active(NOW, self.AH))
        self.assertEqual(logic.active_end(NOW, self.AH), tu.berlin_to_utc(2026, 10, 26, 9, 0))
        self.assertFalse(logic.is_active(tu.berlin_to_utc(2026, 10, 26, 9, 0), self.AH))
        self.assertFalse(logic.is_active(tu.berlin_to_utc(2026, 10, 26, 6, 29), self.AH))

    def test_next_start_over_weekend_and_dst(self):
        # Cuma 23.10.2026 09:30 (CEST) -> Pazartesi 26.10 06:30 (CET)
        fri = tu.berlin_to_utc(2026, 10, 23, 9, 30)
        self.assertEqual(logic.next_active_start(fri, self.AH), tu.to_epoch(2026, 10, 26, 5, 30))
        # Cuma 23.10 06:00 -> aynı gün 06:30 CEST
        self.assertEqual(logic.next_active_start(tu.berlin_to_utc(2026, 10, 23, 6, 0), self.AH),
                         tu.to_epoch(2026, 10, 23, 4, 30))

    def test_no_hours(self):
        self.assertIsNone(logic.next_active_start(NOW, {}))


class MiscTest(unittest.TestCase):
    def test_check_config(self):
        self.assertIsNone(logic.check_config(CFG))
        bad = dict(CFG, YURUME_DK=None)
        self.assertEqual(logic.check_config(bad), "YURUME_DK ayarla")
        self.assertEqual(logic.check_config(dict(CFG, YURUME_DK="7")), "YURUME_DK ayarla")

    def test_battery(self):
        self.assertEqual(logic.battery_percent(4.25), 100)
        self.assertEqual(logic.battery_percent(3.80), 50)
        self.assertEqual(logic.battery_percent(3.75), 40)
        self.assertEqual(logic.battery_percent(3.0), 0)

    def test_empty_direct_lines_marks_all_direct(self):
        deps = [slim("M41", "07:47"), slim("194", "07:50")]
        rows = logic.select_rows(deps, NOW, VALID, 7, 5, [])
        self.assertTrue(all(r["direct"] for r in rows))

    def test_walk_minutes_from_meters(self):
        self.assertEqual(logic.walk_minutes_from_meters(0), 1)
        self.assertEqual(logic.walk_minutes_from_meters(500), 8)
        self.assertEqual(logic.walk_minutes_from_meters(800), 13)

    def test_schedule_sleep_disabled(self):
        cfg = {"SLEEP_ENABLED": False, "SLEEP_START": "10:00", "SLEEP_END": "06:00", "ACTIVE_DAYS": [0]}
        self.assertEqual(logic.schedule_status(NOW, cfg), (True, None))

    def test_schedule_overnight_sleep(self):
        # 23:00 - 06:30 uyku, her gün aktif
        cfg = {"SLEEP_ENABLED": True, "SLEEP_START": "23:00", "SLEEP_END": "06:30",
               "ACTIVE_DAYS": [0, 1, 2, 3, 4, 5, 6]}
        act, end = logic.schedule_status(NOW, cfg)  # Pzt 07:31 -> aktif, 23:00'e kadar
        self.assertTrue(act)
        self.assertEqual(end, tu.berlin_to_utc(2026, 10, 26, 23, 0))
        act, wake = logic.schedule_status(tu.berlin_to_utc(2026, 10, 26, 23, 30), cfg)
        self.assertFalse(act)
        self.assertEqual(wake, tu.berlin_to_utc(2026, 10, 27, 6, 30))

    def test_schedule_daytime_sleep_wraps_midnight(self):
        # 10:00 - 18:00 gündüz uykusu: 22:00'de aktif olmalı ve ertesi gün 10:00'a kadar sürmeli
        cfg = {"SLEEP_ENABLED": True, "SLEEP_START": "10:00", "SLEEP_END": "18:00",
               "ACTIVE_DAYS": [0, 1, 2, 3, 4, 5, 6]}
        act, end = logic.schedule_status(tu.berlin_to_utc(2026, 10, 26, 22, 0), cfg)
        self.assertTrue(act)
        self.assertEqual(end, tu.berlin_to_utc(2026, 10, 27, 10, 0))
        act, wake = logic.schedule_status(tu.berlin_to_utc(2026, 10, 26, 12, 0), cfg)
        self.assertFalse(act)
        self.assertEqual(wake, tu.berlin_to_utc(2026, 10, 26, 18, 0))


if __name__ == "__main__":
    unittest.main()
