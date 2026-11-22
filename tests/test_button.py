import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from button import ButtonTracker


class ButtonTrackerTest(unittest.TestCase):
    def test_instant_single_click_default(self):
        b = ButtonTracker()
        self.assertIsNone(b.update(False, 0))
        self.assertIsNone(b.update(True, 100))
        self.assertIsNone(b.update(True, 150))     # stable pressed
        self.assertIsNone(b.update(False, 220))
        self.assertEqual(b.update(False, 270), "click")   # immediate on release
        self.assertIsNone(b.update(False, 600))

    def test_single_click_after_double_window(self):
        b = ButtonTracker(debounce_ms=40, dbl_ms=400, long_ms=3500)
        self.assertIsNone(b.update(False, 0))
        self.assertIsNone(b.update(True, 100))
        self.assertIsNone(b.update(True, 150))     # stable pressed
        self.assertIsNone(b.update(False, 220))
        self.assertIsNone(b.update(False, 270))    # stable released -> pending 1
        self.assertIsNone(b.update(False, 600))    # pencere henüz dolmadı
        self.assertEqual(b.update(False, 680), "click")
        self.assertIsNone(b.update(False, 1000))

    def test_double_click_fires_immediately_on_second_release(self):
        b = ButtonTracker(debounce_ms=40, dbl_ms=400, long_ms=3500)
        b.update(False, 0)
        # 1. tık
        b.update(True, 100)
        b.update(True, 150)
        b.update(False, 200)
        b.update(False, 250)
        # 2. tık pencere içinde
        b.update(True, 350)
        b.update(True, 400)
        b.update(False, 450)
        self.assertEqual(b.update(False, 500), "double")
        self.assertIsNone(b.update(False, 1000))

    def test_bounce_ignored(self):
        b = ButtonTracker(debounce_ms=40, dbl_ms=400)
        b.update(False, 0)
        b.update(True, 100)
        b.update(False, 120)    # 20 ms parazit
        self.assertIsNone(b.update(False, 700))

    def test_long_and_factory_press(self):
        b = ButtonTracker(debounce_ms=40, dbl_ms=400, long_ms=3500, factory_ms=9000)
        b.update(False, 0)
        b.update(True, 100)
        b.update(True, 150)     # stable pressed @ 150
        self.assertIsNone(b.update(True, 3500))
        self.assertEqual(b.update(True, 3700), "long")
        self.assertIsNone(b.update(True, 5000))
        self.assertEqual(b.update(True, 9200), "factory")
        # Bırakınca fazladan click üretmemeli
        b.update(False, 9300)
        self.assertIsNone(b.update(False, 9400))
        self.assertIsNone(b.update(False, 10000))


if __name__ == "__main__":
    unittest.main()
