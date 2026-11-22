import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import display


def logical(s, x, y):
    return s.fb.pixel(x, y)


def physical(s, x, y):
    # Sürücü tamponunda (x, y) pikseli (MONO_VLSB, 250x128)
    return 1 if s.out[(y >> 3) * display.W + x] & (1 << (y & 7)) else 0


class TransformTest(unittest.TestCase):
    def setUp(self):
        self.s = display.Screen(rotation=0, y_offset=6)
        self.s.fb.fill(display.WHITE)
        for x, y in ((0, 0), (249, 0), (0, 121), (249, 121), (100, 50), (7, 63)):
            self.s.fb.pixel(x, y, display.BLACK)

    def test_rotation_0(self):
        self.s._transform()
        for x in range(display.W):
            for y in range(display.H):
                self.assertEqual(physical(self.s, x, y + 6), logical(self.s, x, y))
        for y in range(6):
            self.assertEqual(physical(self.s, 3, y), 1)   # görünmeyen satırlar beyaz

    def test_rotation_180(self):
        self.s.rotation = 180
        self.s._transform()
        for x in range(display.W):
            for y in range(display.H):
                self.assertEqual(physical(self.s, 249 - x, 121 - y + 6), logical(self.s, x, y))

    def test_offset_0(self):
        self.s.y_offset = 0
        self.s._transform()
        self.assertEqual(physical(self.s, 0, 121), 0)
        self.assertEqual(physical(self.s, 0, 122), 1)


class RenderTest(unittest.TestCase):
    def test_render_smoke(self):
        s = display.Screen()
        s.render_message(None, "Veri yok", "detay")
        s.render_sleep(None)
        self.assertTrue(s.show())
        self.assertFalse(s.show())     # değişiklik yoksa yenileme yok

    def test_qr_and_multilang_and_long_line_badge(self):
        import qr
        for lang in ("en", "tr", "de"):
            s = display.Screen(lang=lang)
            s.render_qr(qr.encode("http://192.168.4.1/"), "Setup", ["1. Scan QR", "192.168.4.1"])
            self.assertTrue(s.show())
            s.render_sleep(1792996800, {"pct": 50, "usb": False})
            self.assertTrue(s.show())
            # 4 karakterli otobüs hattı çökmeden çizilmeli
            s.render_main(None, {"status": "ok", "rows": [{
                "line": "194E", "when": 1792996800, "delay_min": 0, "realtime": True,
                "direct": True, "direction": "Hermannplatz", "urgent": False, "minutes": 5, "missed": False
            }]})
            self.assertTrue(s.show())


class FlakyEPD:
    # İlk `fails` Display_Base çağrısında BUSY zaman aşımı taklidi yapar
    def __init__(self, fails):
        self.fails = fails
        self.inits = 0
        self.hard_resets = 0
        self.shown = 0

    def init(self):
        self.inits += 1

    def prepare(self):
        self.init()

    def hard_reset(self):
        self.hard_resets += 1
        self.init()

    def Display_Base(self, buf):
        if self.fails:
            self.fails -= 1
            raise OSError("e-Paper BUSY zaman aşımı")
        self.shown += 1

    def displayPartial(self, buf):
        self.Display_Base(buf)


class BusyRetryTest(unittest.TestCase):
    def test_retry_after_busy_timeout(self):
        epd = FlakyEPD(1)
        s = display.Screen(epd)
        s.render_message(None, "a")
        self.assertTrue(s.show())
        self.assertEqual((epd.inits, epd.shown), (2, 1))

    def test_hard_reset_after_second_failure(self):
        epd = FlakyEPD(2)
        s = display.Screen(epd)
        s.render_message(None, "a")
        self.assertTrue(s.show())
        self.assertEqual((epd.hard_resets, epd.shown, s.fail_streak), (1, 1, 0))

    def test_skip_after_all_steps_fail_and_recover(self):
        epd = FlakyEPD(3)
        s = display.Screen(epd)
        s.render_message(None, "a")
        self.assertFalse(s.show())       # çökmez, güncelleme atlanır
        self.assertTrue(s.need_full)
        self.assertEqual(s.fail_streak, 1)
        self.assertTrue(s.show())        # aynı içerik bir sonraki dakikada yeniden denenir
        self.assertEqual((epd.shown, s.fail_streak), (1, 0))


class CornerTest(unittest.TestCase):
    def test_status_corner_fits_right_edge(self):
        s = display.Screen()
        s.render_message(None, "x", None, {"pct": 100, "usb": False})
        right = max(x for x in range(display.W) for y in range(30, 50) if s.fb.pixel(x, y) == 0)
        self.assertGreaterEqual(right, display.W - 8)    # sağa yaslı
        self.assertLess(right, display.W)


if __name__ == "__main__":
    unittest.main()
