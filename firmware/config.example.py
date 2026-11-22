# showerboard ayarları.
# Bu dosyayı config.py adıyla kopyala, değerleri doldur ve Pico'ya yükle:
#   cp config.example.py config.py
# config.py .gitignore'da: Wi-Fi şifren repoya gitmez.

# --- Dil / Language ("en", "tr", "de") ---
LANG = "en"

# --- Wi-Fi (2.4 GHz; Pico W 5 GHz desteklemez) ---
WIFI_SSID = ""
WIFI_PASSWORD = ""

# --- Durak: S+U Alexanderplatz (örnek) ---
# Başka durak için: python3 tools/find_stop.py "Alexanderplatz"
STOP_ID = "900100003"
STOP_NAME_HINT = "Alexanderplatz"   # ilk açılışta durak adı bununla doğrulanır

# Sadece S-Bahn
PRODUCTS = {
    "suburban": True,
    "subway": False,
    "tram": False,
    "bus": False,
    "ferry": False,
    "express": False,
    "regional": False,
}

# Yön filtresi: boş liste = her iki yön. API'nin "direction" alanında geçen
# bir parça yaz, ör. ["Westkreuz", "Spandau", "Potsdam", "Warschauer"].
# (Yön adlarını görmek için: python3 tools/find_stop.py --departures 900100003)
DIRECTIONS = []

# Direkt giden hatlar. Diğerleri (ör. S75) "AKT." (aktarmalı) etiketiyle
# gösterilir ve ilk sıraya sadece direkt tren yoksa gelir.
DIRECT_LINES = ["S5", "S7"]

# Yön filtresi boşken satırlarda kısaltılmış yön adı göster
SHOW_DIRECTION = True

# --- Süreler (dakika) ---
# ZORUNLU: Evden perona yürüme süresi (dakika).
# Boş (None) bırakılırsa cihaz ilk kurulum (QR/portal) modunda açılır.
# Not: MicroPython değişken adlarında Türkçe karakter kabul etmez (YÜRÜME_DK yerine YURUME_DK).
YURUME_DK = None

# Duştan çıkıp giyinme süresi
HAZIRLIK_DK = 5

# --- Hava durumu (Open-Meteo) ---
LAT = 52.5200
LON = 13.4050
RAIN_MIN_PCT = 20          # yağış olasılığı bunun altındaysa gösterme

# --- Aktif saatler (Berlin saati) ---
# 0 = Pazartesi ... 6 = Pazar. Gün başına birden çok aralık olabilir.
ACTIVE_HOURS = {
    0: [("06:30", "09:00")],
    1: [("06:30", "09:00")],
    2: [("06:30", "09:00")],
    3: [("06:30", "09:00")],
    4: [("06:30", "09:00")],
    5: [],
    6: [],
}

# --- Yenileme ve veri tazeliği (saniye) ---
TRANSIT_REFRESH_S = 120     # kalkış verisini bu sıklıkta çek
WEATHER_REFRESH_S = 900     # hava durumu
MAX_DATA_AGE_S = 180        # son başarılı kalkış verisi bundan eskiyse "Veri eski"
MAX_REALTIME_AGE_S = 300    # API'nin canlı veri zaman damgası bundan eskiyse "Veri eski"
TRANSIT_RESULTS = 10        # tek istekte en fazla kalkış (RAM için küçük tut)
TRANSIT_DURATION_MIN = 45   # kaç dakikalık kalkış penceresi istensin
NTP_REFRESH_S = 3600
NTP_HOST = "pool.ntp.org"

# --- Ekran ---
EPD_VERSION = "V4"          # kartın etiketi: "V3" ya da "V4"; kırmızılı 2.13-B V4 için "V4B"
ROTATION = 0                # 0 ya da 180
EPD_Y_OFFSET = 6            # görüntü üstten/alttan kesiliyorsa 0 dene
FULL_REFRESH_EVERY = 10     # her N kısmi yenilemede bir tam yenileme

# --- Güç ---
LOW_POWER = False           # True: aktif saatlerde dakikalar arasında lightsleep.
                            # Pico W'da önerilmez: Wi-Fi kullanıldıktan sonra lightsleep
                            # erken dönüyor ya da takılabiliyor (ekran donar). USB seri
                            # log da kesilir. Gece uykusu (deepsleep) bundan etkilenmez.
NO_DEEPSLEEP = False        # True: uyku saatlerinde deepsleep yerine normal bekleme (hata ayıklama)
MANUAL_WAKE_MIN = 15        # aktif saat dışında butonla/RESET ile uyanınca kaç dk çalışsın
BUTTON_PIN = None           # isteğe bağlı uyandırma butonu, ör. 15 (GP15 ile GND arası)

# --- Pil ---
BATTERY = True              # VSYS gerilimini ölç ve göster
VSYS_DIODE_DROP_V = 0.0     # pil ile VSYS arasında diyot varsa düşümü (ör. 0.25)
