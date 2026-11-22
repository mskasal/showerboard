import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import config_store
import portal
import transit
import wifi


POST_HDRS = {"host": "192.168.4.1", "origin": "http://192.168.4.1", "x-requested-with": "showerboard"}
GET_HDRS = {"host": "192.168.4.1"}


class FakeWifi:
    def __init__(self, ip=None, ok=True):
        self._ip = ip
        self._ok = ok

    def sta_ip(self):
        return self._ip

    def scan(self):
        return [{"ssid": "EvAgi", "rssi": -55, "open": False}]

    def connect_status(self, ssid, pw, timeout_s=15, keep_active_on_fail=False):
        if self._ok and pw != "yanlis":
            self._ip = "192.168.1.42"
            return True, self._ip
        self._ip = None
        return False, "Wi-Fi şifresi hatalı"


class FakeTransit:
    def __init__(self, oom=False):
        self.oom = oom

    def search_address(self, q):
        if self.oom:
            raise MemoryError()
        return [{"address": "Alexanderplatz 1, Berlin", "lat": 52.5200, "lon": 13.4050}]

    def nearby_stops(self, lat, lon):
        if self.oom:
            raise MemoryError()
        return [{
            "id": "900100003",
            "name": "S+U Alexanderplatz",
            "distance": 580,
            "walk_min": 9,
            "products": {"suburban": True, "subway": False, "bus": True, "tram": False},
        }]


class FakeStore:
    def __init__(self):
        self.saved = None
        self.was_reset = False

    def public_view(self, cfg):
        return config_store.public_view(cfg)

    def save(self, cfg):
        self.saved = dict(cfg)

    def reset(self):
        self.was_reset = True


class PortalTest(unittest.TestCase):
    def test_dns_reply_and_safety(self):
        # Minimal DNS query for "captive.apple.com"
        q = (
            b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
            b"\x07captive\x05apple\x03com\x00\x00\x01\x00\x01"
        )
        rep = portal.build_dns_reply(q, "192.168.4.1")
        self.assertEqual(rep[:2], b"\x12\x34")
        self.assertEqual(rep[-4:], bytes([192, 168, 4, 1]))
        # DNS response packets (QR=1) must be ignored
        resp_pkt = b"\x12\x34\x81\x80" + q[4:]
        self.assertIsNone(portal.build_dns_reply(resp_pkt, "192.168.4.1"))

    def test_url_decode_and_query(self):
        q = portal.parse_query("q=Sch%C3%B6nhauser+Allee+3%2C+Berlin&n=5")
        self.assertEqual(q["q"], "Schönhauser Allee 3, Berlin")
        self.assertEqual(q["n"], "5")

    def test_captive_redirect(self):
        app = portal.PortalApp(config_store.defaults(), "192.168.4.1",
                               wifi_mod=FakeWifi(), transit_mod=FakeTransit(), store_mod=FakeStore())
        st, _, _, hdrs, _ = app.handle("GET", "/hotspot-detect.html", b"")
        self.assertEqual(st, 302)
        self.assertIn(("Location", "http://192.168.4.1/"), hdrs)

    def test_wifi_address_nearby_and_save_flow(self):
        fw = FakeWifi()
        fs = FakeStore()
        app = portal.PortalApp(config_store.defaults(), "192.168.4.1",
                               wifi_mod=fw, transit_mod=FakeTransit(), store_mod=fs,
                               batt={"v": 3.98, "pct": 87, "usb": False})
        # State includes battery
        st, _, body, _, _ = app.handle("GET", "/api/state", b"", GET_HDRS)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body)["battery"]["pct"], 87)
        # Wi-Fi connect
        st, _, body, _, _ = app.handle(
            "POST", "/api/wifi", json.dumps({"ssid": "EvAgi", "password": "dogru"}).encode(), POST_HDRS
        )
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(body)["ok"])
        # Address search
        st, _, body, _, _ = app.handle("GET", "/api/address?q=Alexanderplatz+1", b"", GET_HDRS)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body)["results"][0]["lat"], 52.5200)
        # Nearby stops
        st, _, body, _, _ = app.handle("GET", "/api/nearby?lat=52.5200&lon=13.4050", b"", GET_HDRS)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(body)["stops"][0]["id"], "900100003")
        # Save (blank password preserves previous password, LANG persists)
        payload = {
            "LANG": "tr",
            "WIFI_SSID": "EvAgi",
            "WIFI_PASSWORD": "",
            "ADDRESS": "Alexanderplatz 1, Berlin",
            "STOP_ID": "900100003",
            "STOP_NAME": "S+U Alexanderplatz",
            "PRODUCTS": {"suburban": True, "subway": False, "bus": True, "tram": False},
            "YURUME_DK": 9,
            "HAZIRLIK_DK": 5,
            "SLEEP_ENABLED": True,
            "SLEEP_START": "23:00",
            "SLEEP_END": "06:30",
            "ACTIVE_DAYS": [0, 1, 2, 3, 4],
            "ROTATION": 0,
            "EPD_VERSION": "V4B",
            "REFRESH_MIN": 5,
        }
        st, _, body, _, _ = app.handle("POST", "/api/save", json.dumps(payload).encode(), POST_HDRS)
        self.assertEqual(st, 200)
        self.assertEqual(app.done, "saved")
        self.assertEqual(fs.saved["LANG"], "tr")
        self.assertEqual(fs.saved["WIFI_PASSWORD"], "dogru")
        self.assertEqual(fs.saved["SLEEP_START"], "23:00")
        self.assertEqual(fs.saved["ACTIVE_DAYS"], [0, 1, 2, 3, 4])
        self.assertEqual(fs.saved["REFRESH_MIN"], 5)

    def test_oom_triggers_lan_fallback(self):
        fw = FakeWifi(ip="192.168.1.42")
        app = portal.PortalApp(config_store.defaults(), "192.168.4.1", ap_mode=True,
                               wifi_mod=fw, transit_mod=FakeTransit(oom=True), store_mod=FakeStore())
        st, _, body, _, _ = app.handle("GET", "/api/address?q=Berlin", b"", GET_HDRS)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(body)["lan_fallback"])
        self.assertEqual(app.done, "lan_fallback")

    def test_csrf_and_dns_rebinding_blocked(self):
        app = portal.PortalApp(config_store.defaults(), "192.168.4.1",
                               wifi_mod=FakeWifi(), transit_mod=FakeTransit(), store_mod=FakeStore())
        # Missing X-Requested-With on POST
        st, _, _, _, _ = app.handle("POST", "/api/reset", b"", {"host": "192.168.4.1"})
        self.assertEqual(st, 403)
        # Evil Origin on POST
        st, _, _, _, _ = app.handle("POST", "/api/reset", b"", {
            "host": "192.168.4.1", "origin": "https://evil.example", "x-requested-with": "showerboard",
        })
        self.assertEqual(st, 403)
        # DNS rebinding via Host header
        st, _, _, _, _ = app.handle("GET", "/api/state", b"", {"host": "evil.example"})
        self.assertEqual(st, 403)

    def test_input_validation_hardening(self):
        base = config_store.defaults()
        good = {
            "LANG": "de",
            "WIFI_SSID": "HomeNet",
            "STOP_ID": "900100003",
            "YURUME_DK": 8,
            "HAZIRLIK_DK": 5,
            "PRODUCTS": {"suburban": True},
        }
        ok, res = portal.validate_and_apply(base, good)
        self.assertTrue(ok)
        self.assertEqual(res["LANG"], "de")

        # Path traversal in STOP_ID rejected
        bad = dict(good, STOP_ID="../admin?x=1")
        self.assertFalse(portal.validate_and_apply(base, bad)[0])
        self.assertFalse(transit.is_valid_stop_id("../admin"))

        # Non-int ROTATION rejected cleanly without raising
        bad = dict(good, ROTATION="abc")
        self.assertFalse(portal.validate_and_apply(base, bad)[0])

        # Boolean rejected for YURUME_DK
        bad = dict(good, YURUME_DK=True)
        self.assertFalse(portal.validate_and_apply(base, bad)[0])

        # NaN / out-of-range LAT/LON rejected
        self.assertFalse(portal.validate_and_apply(base, dict(good, LAT="nan"))[0])
        self.assertFalse(portal.validate_and_apply(base, dict(good, LAT=95.0))[0])
        self.assertFalse(portal.validate_and_apply(base, dict(good, LON=200.0))[0])

        # Unsupported language rejected
        self.assertFalse(portal.validate_and_apply(base, dict(good, LANG="xx"))[0])

        # Oversized SSID rejected
        self.assertFalse(portal.validate_and_apply(base, dict(good, WIFI_SSID="A" * 33))[0])

    def test_nearby_rejects_nan_and_out_of_range(self):
        app = portal.PortalApp(config_store.defaults(), "192.168.4.1",
                               wifi_mod=FakeWifi(ip="192.168.1.42"), transit_mod=FakeTransit(), store_mod=FakeStore())
        for qs in ("lat=nan&lon=13.4", "lat=inf&lon=13.4", "lat=91&lon=13.4", "lat=52&lon=-181"):
            st, _, _, _, _ = app.handle("GET", "/api/nearby?" + qs, b"", GET_HDRS)
            self.assertEqual(st, 400)

    def test_ap_password_and_wifi_http_hardening(self):
        pw = portal._gen_ap_password()
        self.assertEqual(len(pw), 8)
        for ch in pw:
            self.assertIn(ch, portal._AP_PW_CHARS)
        self.assertIsNone(wifi._expected_size(b"HTTP/1.1 200 OK\r\nContent-Length: -5\r\n\r\n"))
        self.assertIsNone(wifi._expected_size(b"HTTP/1.1 200 OK\r\nContent-Length: nope\r\n\r\n"))
        with self.assertRaises(ValueError):
            wifi.http_get("https://example.com/a\r\nX-Inject: 1")


if __name__ == "__main__":
    unittest.main()
