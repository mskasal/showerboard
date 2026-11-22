# On-device UI translations (EN / TR / DE).
# Every character used here is present in fonts/mid.bin and fonts/small.bin.

SUPPORTED = ("en", "tr", "de")
DEFAULT = "en"

_WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "tr": ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"),
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
}

_STRINGS = {
    "en": {
        "urgent": "GO!",
        "missed": "LATE",
        "min_unit": "m",
        "transfer": "XFR",
        "planned": "SCH",
        "stale_title": "Stale data",
        "stale_detail": "Last data ",
        "none_title": "No trains",
        "none_detail": "No catchable departures",
        "nodata_title": "No data",
        "nodata_detail": "BVG/VBB unreachable",
        "nowifi_title": "No Wi-Fi",
        "nowifi_detail": "No connection",
        "ntp_title": "Clock error",
        "btn_setup_2m": "Button: Setup  (2 min)",
        "bad_stop_title": "Invalid stop",
        "sleep_title": "Sleep",
        "wake_prefix": "Wake: ",
        "no_active_title": "No active hours",
        "no_active_detail": "Press button for setup",
        "setup_title": "Setup",
        "qr_step1": "1. Scan QR",
        "qr_step2": "2. Page opens",
        "qr_close": "Press: Close",
        "qr_lan_ok": "Home Wi-Fi OK",
        "qr_lan_hint": "Pick stop, save",
        "err_prefix": "Error: ",
        "restarting": "Restarting...",
    },
    "tr": {
        "urgent": "ÇIK!",
        "missed": "GEÇ",
        "min_unit": "dk",
        "transfer": "AKT.",
        "planned": "PLAN",
        "stale_title": "Veri eski",
        "stale_detail": "Son veri ",
        "none_title": "Tren yok",
        "none_detail": "Yakalanabilecek kalkış yok",
        "nodata_title": "Veri yok",
        "nodata_detail": "BVG/VBB'ye ulaşılamadı",
        "nowifi_title": "Bağlantı yok",
        "nowifi_detail": "Bağlantı yok",
        "ntp_title": "Saat alınamadı",
        "btn_setup_2m": "Buton: Ayarlar  (2 dk)",
        "bad_stop_title": "Durak ID hatalı",
        "sleep_title": "Uyku",
        "wake_prefix": "Uyanış: ",
        "no_active_title": "Aktif saat yok",
        "no_active_detail": "Ayarlar için butona bas",
        "setup_title": "Ayarlar",
        "qr_step1": "1. QR okut",
        "qr_step2": "2. Sayfa açılır",
        "qr_close": "Bas: Kapat",
        "qr_lan_ok": "Ev Wi-Fi bağlı",
        "qr_lan_hint": "Adres/durak seç",
        "err_prefix": "Hata: ",
        "restarting": "Yeniden başlıyor...",
    },
    "de": {
        "urgent": "LOS!",
        "missed": "SPÄT",
        "min_unit": "m",
        "transfer": "UMST",
        "planned": "PLAN",
        "stale_title": "Alte Daten",
        "stale_detail": "Stand ",
        "none_title": "Keine Züge",
        "none_detail": "Keine Abfahrt erreichbar",
        "nodata_title": "Keine Daten",
        "nodata_detail": "BVG/VBB nicht erreichbar",
        "nowifi_title": "Kein WLAN",
        "nowifi_detail": "Keine Verbindung",
        "ntp_title": "Uhrzeit-Fehler",
        "btn_setup_2m": "Taste: Setup  (2 Min)",
        "bad_stop_title": "Halt ungültig",
        "sleep_title": "Ruhe",
        "wake_prefix": "Wecken: ",
        "no_active_title": "Keine Aktivzeit",
        "no_active_detail": "Taste für Setup drücken",
        "setup_title": "Setup",
        "qr_step1": "1. QR scannen",
        "qr_step2": "2. Seite öffnet",
        "qr_close": "Taste: Zu",
        "qr_lan_ok": "Heim-WLAN OK",
        "qr_lan_hint": "Halt wählen",
        "err_prefix": "Fehler: ",
        "restarting": "Neustart...",
    },
}


def norm(lang):
    if isinstance(lang, str):
        code = lang.strip().lower()[:2]
        if code in _STRINGS:
            return code
    return DEFAULT


def t(lang, key):
    return _STRINGS[norm(lang)][key]


def weekdays(lang):
    return _WEEKDAYS[norm(lang)]
