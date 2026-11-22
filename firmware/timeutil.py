# Zaman yardımcıları: NTP, Berlin saat dilimi (CET/CEST), ISO 8601 ayrıştırma.
# Tüm iç hesaplar UTC Unix zamanı (1970 epoch, saniye) ile yapılır.
# Bu modül hem MicroPython'da hem CPython'da (testler) çalışır.

import time

_MDAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
WEEKDAYS_TR = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y, m):
    if m == 2 and is_leap(y):
        return 29
    return _MDAYS[m - 1]


def days_from_civil(y, m, d):
    # 1970-01-01'den bu yana gün sayısı (Howard Hinnant algoritması)
    if m <= 2:
        y -= 1
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    mp = (m + 9) % 12
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y += 1
    return y, m, d


def to_epoch(y, mo, d, h=0, mi=0, s=0):
    return days_from_civil(y, mo, d) * 86400 + h * 3600 + mi * 60 + s


def weekday(days):
    # 0 = Pazartesi (1970-01-01 Perşembe idi)
    return (days + 3) % 7


def last_sunday(y, m):
    d = days_in_month(y, m)
    days = days_from_civil(y, m, d)
    return d - (weekday(days) - 6) % 7


def berlin_offset(utc):
    # CEST: Mart'ın son Pazar'ı 01:00 UTC -> Ekim'in son Pazar'ı 01:00 UTC
    y = civil_from_days(utc // 86400)[0]
    start = to_epoch(y, 3, last_sunday(y, 3), 1)
    end = to_epoch(y, 10, last_sunday(y, 10), 1)
    return 7200 if start <= utc < end else 3600


def berlin(utc):
    # (yıl, ay, gün, saat, dakika, saniye, haftanın_günü) Berlin yerel saati
    t = utc + berlin_offset(utc)
    days = t // 86400
    y, m, d = civil_from_days(days)
    s = t % 86400
    return y, m, d, s // 3600, (s // 60) % 60, s % 60, weekday(days)


def berlin_to_utc(y, m, d, h, mi):
    # Yerel saati UTC'ye çevir. Geçiş anlarındaki belirsiz/olmayan saatler
    # için makul sonuç verir (aktif saatler sabah olduğu için önemsiz).
    local = to_epoch(y, m, d, h, mi)
    utc = local - 3600
    if berlin_offset(utc) == 7200:
        utc = local - 7200
    return utc


def hhmm(utc):
    t = berlin(utc)
    return "%02d:%02d" % (t[3], t[4])


def parse_iso(s):
    # "2026-10-25T07:42:00+01:00", "...Z", kesirli saniyeler -> UTC epoch.
    # Hatalı girdide ValueError.
    if not s or len(s) < 19 or s[4] != "-" or s[10] != "T":
        raise ValueError("ISO zaman değil: %r" % (s,))
    y = int(s[0:4])
    mo = int(s[5:7])
    d = int(s[8:10])
    h = int(s[11:13])
    mi = int(s[14:16])
    sec = int(s[17:19])
    rest = s[19:]
    if rest.startswith("."):
        i = 1
        while i < len(rest) and rest[i].isdigit():
            i += 1
        rest = rest[i:]
    if rest in ("Z", "z", ""):
        if rest == "":
            raise ValueError("saat dilimi yok: %r" % (s,))
        off = 0
    elif len(rest) == 6 and rest[0] in "+-" and rest[3] == ":":
        off = int(rest[1:3]) * 3600 + int(rest[4:6]) * 60
        if rest[0] == "-":
            off = -off
    else:
        raise ValueError("saat dilimi anlaşılmadı: %r" % (s,))
    if not (1 <= mo <= 12 and 1 <= d <= days_in_month(y, mo) and h < 24 and mi < 60 and sec < 61):
        raise ValueError("geçersiz tarih: %r" % (s,))
    return to_epoch(y, mo, d, h, mi, sec) - off


def now():
    # Platformun epoch'undan bağımsız UTC epoch
    t = time.gmtime()
    return to_epoch(t[0], t[1], t[2], t[3], t[4], t[5])


def clock_valid():
    # NTP yapılmamış RTC 2021 gibi eski bir tarihte başlar
    return time.gmtime()[0] >= 2025


def sync_ntp(host="pool.ntp.org", tries=3, feed=None):
    import ntptime
    ntptime.host = host
    ntptime.timeout = 2
    for i in range(tries):
        if feed:
            feed()
        try:
            ntptime.settime()
            return True
        except Exception as e:
            print("NTP hata:", e)
            time.sleep(1)
    return False


def iso_utc(utc):
    y, m, d = civil_from_days(utc // 86400)
    s = utc % 86400
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, s // 3600, (s // 60) % 60, s % 60)
