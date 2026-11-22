import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import config_store


class ConfigStoreTest(unittest.TestCase):
    def test_save_and_load_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.json")
            cfg = config_store.defaults()
            cfg["WIFI_SSID"] = "EvAgi"
            cfg["WIFI_PASSWORD"] = "gizli123"
            cfg["STOP_ID"] = "900100003"
            cfg["STOP_NAME"] = "S+U Alexanderplatz"
            cfg["YURUME_DK"] = 8
            cfg["SLEEP_ENABLED"] = False
            cfg["SLEEP_START"] = "23:00"
            cfg["SLEEP_END"] = "06:30"
            config_store.save(cfg, path=p)
            loaded = config_store.load(path=p, use_py=False)
            self.assertEqual(loaded["WIFI_SSID"], "EvAgi")
            self.assertEqual(loaded["WIFI_PASSWORD"], "gizli123")
            self.assertEqual(loaded["YURUME_DK"], 8)
            self.assertFalse(loaded["SLEEP_ENABLED"])
            self.assertEqual(loaded["SLEEP_START"], "23:00")
            self.assertEqual(loaded["SLEEP_END"], "06:30")
            self.assertFalse(config_store.needs_setup(loaded))

    def test_public_view_hides_password(self):
        cfg = config_store.defaults()
        cfg["WIFI_PASSWORD"] = "cokgizli"
        pub = config_store.public_view(cfg)
        self.assertNotIn("WIFI_PASSWORD", pub)
        self.assertTrue(pub["HAS_WIFI_PASSWORD"])

    def test_needs_setup(self):
        cfg = config_store.defaults()
        self.assertTrue(config_store.needs_setup(cfg))
        cfg["WIFI_SSID"] = "Net"
        cfg["STOP_ID"] = "900100003"
        self.assertTrue(config_store.needs_setup(cfg))   # YURUME_DK hala None
        cfg["YURUME_DK"] = True
        self.assertTrue(config_store.needs_setup(cfg))   # bool kabul edilmemeli
        cfg["YURUME_DK"] = 9
        self.assertFalse(config_store.needs_setup(cfg))

    def test_button_pin_not_user_writable(self):
        self.assertNotIn("BUTTON_PIN", config_store.USER_KEYS)
        self.assertIn("LANG", config_store.USER_KEYS)

    def test_valid_hhmm(self):
        self.assertTrue(config_store.valid_hhmm("00:00"))
        self.assertTrue(config_store.valid_hhmm("23:59"))
        self.assertFalse(config_store.valid_hhmm("24:00"))
        self.assertFalse(config_store.valid_hhmm("7:00"))
        self.assertFalse(config_store.valid_hhmm("xx:yy"))


if __name__ == "__main__":
    unittest.main()
