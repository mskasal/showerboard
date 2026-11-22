# Kalıcı ayar yönetimi: defaults -> config.py (varsa) -> config.json.
# Web portalı ayarları config.json'a atomik olarak yazar (güç kesintisinde bozulmaz).

import json
import os

CONFIG_FILE = "config.json"
TMP_FILE = "config.tmp"

DEFAULTS = {
    "LANG": "en",
    "WIFI_SSID": "",
    "WIFI_PASSWORD": "",
    "ADDRESS": "",
    "STOP_ID": "",
    "STOP_NAME": "",
    "STOP_NAME_HINT": "",
    "PRODUCTS": {
        "suburban": True,
        "subway": False,
        "tram": False,
        "bus": False,
        "ferry": False,
        "express": False,
        "regional": False,
    },
    "DIRECTIONS": [],
    "DIRECT_LINES": [],
    "SHOW_DIRECTION": True,
    "YURUME_DK": None,
    "HAZIRLIK_DK": 5,
    "LAT": 52.5200,
    "LON": 13.4050,
    "RAIN_MIN_PCT": 20,
    # Uyku modu: SLEEP_ENABLED=False ise cihaz 7/24 aktif kalır.
    # SLEEP_START / SLEEP_END Berlin saatidir (gece yarısı geçişi desteklenir, ör. 23:00-06:30 veya 10:00-06:00).
    "SLEEP_ENABLED": True,
    "SLEEP_START": "10:00",
    "SLEEP_END": "06:00",
    "ACTIVE_DAYS": [0, 1, 2, 3, 4, 5, 6],
    # Geriye uyumluluk: eski config.py ACTIVE_HOURS tanımlıysa ve config.json yoksa kullanılır.
    "ACTIVE_HOURS": None,
    "TRANSIT_REFRESH_S": 120,
    "WEATHER_REFRESH_S": 900,
    "MAX_DATA_AGE_S": 180,
    "MAX_REALTIME_AGE_S": 300,
    "TRANSIT_RESULTS": 10,
    "TRANSIT_DURATION_MIN": 45,
    "NTP_REFRESH_S": 3600,
    "NTP_HOST": "pool.ntp.org",
    "EPD_VERSION": "V4B",
    "REFRESH_MIN": 3,           # önerilen: 3 dk (180 sn, 3 renkli e-Paper ömrü için)
    "ROTATION": 0,
    "EPD_Y_OFFSET": 6,
    "FULL_REFRESH_EVERY": 10,
    "LOW_POWER": False,
    "NO_DEEPSLEEP": False,
    "MANUAL_WAKE_MIN": 30,
    "BUTTON_PIN": 15,
    "BATTERY": True,
    "VSYS_DIODE_DROP_V": 0.0,
}

# config.json'a kaydedilmesine izin verilen anahtarlar
USER_KEYS = (
    "LANG", "WIFI_SSID", "WIFI_PASSWORD", "ADDRESS", "STOP_ID", "STOP_NAME",
    "STOP_NAME_HINT", "PRODUCTS", "DIRECTIONS", "DIRECT_LINES",
    "SHOW_DIRECTION", "YURUME_DK", "HAZIRLIK_DK", "LAT", "LON",
    "RAIN_MIN_PCT", "SLEEP_ENABLED", "SLEEP_START", "SLEEP_END",
    "ACTIVE_DAYS", "MANUAL_WAKE_MIN", "ROTATION", "EPD_VERSION",
    "REFRESH_MIN",
)


def _copy_val(v):
    if isinstance(v, dict):
        return dict((k, _copy_val(val)) for k, val in v.items())
    if isinstance(v, list):
        return [_copy_val(x) for x in v]
    return v


def defaults():
    return _copy_val(DEFAULTS)


def _migrate_active_hours(cfg, ah):
    # Eski ACTIVE_HOURS = {0: [("06:00", "10:00")], ...} yapısından
    # SLEEP_START/SLEEP_END/ACTIVE_DAYS çıkarır (uyumluysa).
    if not isinstance(ah, dict):
        return
    days = []
    first = None
    for d in range(7):
        wins = ah.get(d) or ah.get(str(d)) or []
        if wins:
            days.append(d)
            if first is None and len(wins[0]) == 2:
                first = wins[0]
    if first:
        cfg["SLEEP_ENABLED"] = True
        cfg["SLEEP_END"] = first[0]
        cfg["SLEEP_START"] = first[1]
        cfg["ACTIVE_DAYS"] = days


def _load_py_module(cfg):
    try:
        import config as py_cfg
    except ImportError:
        return
    for k in DEFAULTS:
        if hasattr(py_cfg, k):
            val = getattr(py_cfg, k)
            if k == "PRODUCTS" and isinstance(val, dict):
                p = _copy_val(DEFAULTS["PRODUCTS"])
                p.update(val)
                cfg[k] = p
            elif k == "BUTTON_PIN" and val is None:
                # Eski config.py'de BUTTON_PIN=None olabilir; varsayılan GP15 korunsun
                continue
            else:
                cfg[k] = _copy_val(val)
    if getattr(py_cfg, "ACTIVE_HOURS", None) is not None and not hasattr(py_cfg, "SLEEP_START"):
        _migrate_active_hours(cfg, py_cfg.ACTIVE_HOURS)
    if not cfg.get("STOP_NAME") and cfg.get("STOP_NAME_HINT"):
        cfg["STOP_NAME"] = cfg["STOP_NAME_HINT"]


def load(path=CONFIG_FILE, use_py=True):
    cfg = defaults()
    if use_py:
        _load_py_module(cfg)
    try:
        with open(path, "r") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = None
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k not in DEFAULTS:
                continue
            if k == "PRODUCTS" and isinstance(v, dict):
                p = _copy_val(DEFAULTS["PRODUCTS"])
                for pk in p:
                    if pk in v:
                        p[pk] = bool(v[pk])
                cfg[k] = p
            else:
                cfg[k] = v
        # JSON kaydedildiyse artık yeni uyku ayarları geçerli (eski ACTIVE_HOURS ezmesin)
        if "SLEEP_ENABLED" in raw or "SLEEP_START" in raw or "SLEEP_END" in raw:
            cfg["ACTIVE_HOURS"] = None
    return cfg


def save(cfg, path=CONFIG_FILE):
    # Sadece JSON uyumlu ayarları atomik olarak yaz
    data = {}
    for k in USER_KEYS:
        if k in cfg:
            data[k] = cfg[k]
    tmp = path + ".tmp" if path != CONFIG_FILE else TMP_FILE
    with open(tmp, "w") as f:
        json.dump(data, f)
    try:
        os.rename(tmp, path)
    except OSError:
        try:
            os.remove(path)
        except OSError:
            pass
        os.rename(tmp, path)


def reset(path=CONFIG_FILE, state_path="state.json"):
    for p in (path, TMP_FILE, state_path):
        try:
            os.remove(p)
        except OSError:
            pass


def valid_hhmm(s):
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        return False
    try:
        h = int(s[:2])
        m = int(s[3:])
    except ValueError:
        return False
    return 0 <= h <= 23 and 0 <= m <= 59


def needs_setup(cfg):
    if not cfg.get("WIFI_SSID"):
        return True
    if not cfg.get("STOP_ID"):
        return True
    w = cfg.get("YURUME_DK")
    if w is None or isinstance(w, bool) or not isinstance(w, int) or w < 0 or w > 60:
        return True
    return False


def public_view(cfg):
    # Web arayüzüne gönderilecek güvenli görünüm (Wi-Fi şifresi düz metin dönmez)
    out = {}
    for k in USER_KEYS:
        if k == "WIFI_PASSWORD":
            out["HAS_WIFI_PASSWORD"] = bool(cfg.get("WIFI_PASSWORD"))
        elif k in cfg:
            out[k] = cfg[k]
    return out
