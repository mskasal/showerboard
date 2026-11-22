# Kalan süre hesabı, tren seçimi, aktif saat hesabı.
# Donanımdan bağımsız saf fonksiyonlar; CPython'da test edilir.

import timeutil

URGENT_S = 120  # 0-2 dk arası: "ÇIK!"


def slim_departure(d):
    # BVG/VBB yanıtındaki tek kalkışı küçük bir dict'e indirger.
    # İptal edilen ya da zamanı olmayan seferler için None döner.
    if d.get("cancelled"):
        return None
    when = d.get("when")
    if not when:
        return None
    line = d.get("line") or {}
    planned = d.get("plannedWhen")
    return {
        "line": line.get("name") or "?",
        "when": timeutil.parse_iso(when),
        "planned": timeutil.parse_iso(planned) if planned else None,
        # delay: saniye; None = canlı veri yok (sadece tarifeli saat)
        "delay": d.get("delay"),
        "direction": d.get("direction") or "",
    }


def direction_ok(direction, directions):
    if not directions:
        return True
    dl = direction.lower()
    for want in directions:
        if want.lower() in dl:
            return True
    return False


def leave_seconds(dep, now, walk_min, prep_min):
    # kalan = kalkış - şimdi - yürüme - hazırlık
    return dep - now - (walk_min + prep_min) * 60


def _delay_min(delay):
    if delay is None:
        return None
    if delay >= 0:
        return (delay + 30) // 60
    return -((-delay + 30) // 60)


def _row(dep, now, valid_until, walk_min, prep_min, direct_lines):
    left_now = leave_seconds(dep["when"], now, walk_min, prep_min)
    # Ekrandaki sayı bir sonraki yenilemeye kadar doğru kalmalı: en kötü
    # an (valid_until) için hesapla ve aşağı yuvarla.
    left_end = leave_seconds(dep["when"], valid_until, walk_min, prep_min)
    delay = dep["delay"]
    return {
        "line": dep["line"],
        "when": dep["when"],
        "delay_min": _delay_min(delay),
        "realtime": delay is not None,
        "direct": (not direct_lines) or (dep["line"] in direct_lines),
        "direction": dep["direction"],
        "urgent": left_now < URGENT_S,
        "minutes": max(0, left_end // 60),
        "missed": False,
    }


def select_rows(deps, now, valid_until, walk_min, prep_min, direct_lines, directions=()):
    # Yakalanabilir: kalkışa en az yürüme süresi kadar var. Hazırlığa vakit
    # kalmadıysa satır ÇIK! olur (kalan < URGENT_S).
    # Yetişilemeyen (yürüme süresinden az kalan) ama henüz kalkmamış tren varsa:
    #   satır 1: o tren ("GEÇ"; birden çoksa direkt hatların en geç kalkanı),
    #   satır 2: yakalanabilecek ilk tren (aşağıdaki kurala göre).
    # Yoksa:
    #   satır 1: yakalanabilecek ilk direkt tren,
    #   satır 2: ondan önce kalkan aktarmalı (ör. S75) varsa o, yoksa sonraki tren.
    # Direkt tren yoksa: yakalanabilecek ilk iki tren.
    ok, missed = [], []
    for d in deps:
        if d is None or not direction_ok(d["direction"], directions):
            continue
        if leave_seconds(d["when"], now, walk_min, 0) >= 0:
            ok.append(d)
        elif d["when"] > now:
            missed.append(d)
    ok.sort(key=lambda d: d["when"])
    rows = _pick(ok, direct_lines)
    rows = [_row(d, now, valid_until, walk_min, prep_min, direct_lines) for d in rows]
    if missed:
        missed.sort(key=lambda d: (d["line"] in direct_lines, d["when"]))
        m = _row(missed[-1], now, valid_until, walk_min, prep_min, direct_lines)
        m["urgent"], m["minutes"], m["missed"] = False, 0, True
        rows = [m] + rows[:1]
    return rows


def _pick(ok, direct_lines):
    first = None
    for d in ok:
        if d["line"] in direct_lines:
            first = d
            break
    if first is None:
        picked = ok[:2]
    else:
        before = [d for d in ok if d["when"] < first["when"]]
        if before:
            picked = [first, before[0]]
        else:
            after = [d for d in ok if d is not first]
            picked = [first] + after[:1]
    return picked


def transit_view(now, valid_until, cfg, deps, fetch_ok, data_time, rt_time=None):
    # Ekranın ikinci seviyesi için durum: "ok", "nodata", "stale", "none".
    # deps: slim_departure listesi; data_time: son başarılı çekme zamanı (UTC).
    if not fetch_ok or data_time is None:
        return {"status": "nodata", "rows": []}
    if valid_until - data_time > cfg["MAX_DATA_AGE_S"]:
        return {"status": "stale", "rows": [], "since": data_time}
    if rt_time is not None and valid_until - rt_time > cfg["MAX_REALTIME_AGE_S"]:
        return {"status": "stale", "rows": [], "since": rt_time}
    rows = select_rows(deps, now, valid_until, cfg["YURUME_DK"], cfg["HAZIRLIK_DK"],
                       cfg["DIRECT_LINES"], cfg["DIRECTIONS"])
    if not rows:
        return {"status": "none", "rows": []}
    return {"status": "ok", "rows": rows}


def _hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def is_active(utc, active_hours):
    # active_hours: {0: [("06:30", "09:00")], ...}  0 = Pazartesi
    t = timeutil.berlin(utc)
    mins = t[3] * 60 + t[4]
    for start, end in active_hours.get(t[6], ()):
        if _hm(start) <= mins < _hm(end):
            return True
    return False


def active_end(utc, active_hours):
    # İçinde bulunulan aktif aralığın bitişi (UTC), aktif değilse None
    t = timeutil.berlin(utc)
    mins = t[3] * 60 + t[4]
    for start, end in active_hours.get(t[6], ()):
        if _hm(start) <= mins < _hm(end):
            e = _hm(end)
            return timeutil.berlin_to_utc(t[0], t[1], t[2], e // 60, e % 60)
    return None


def next_active_start(utc, active_hours):
    # utc'den sonraki ilk aktif başlangıç (UTC). 8 gün içinde yoksa None.
    t = timeutil.berlin(utc)
    base = timeutil.days_from_civil(t[0], t[1], t[2])
    for i in range(8):
        y, m, d = timeutil.civil_from_days(base + i)
        wd = timeutil.weekday(base + i)
        for start, _ in sorted(active_hours.get(wd, ())):
            s = _hm(start)
            u = timeutil.berlin_to_utc(y, m, d, s // 60, s % 60)
            if u > utc:
                return u
    return None


def build_active_hours(cfg):
    # SLEEP_ENABLED/SLEEP_START/SLEEP_END/ACTIVE_DAYS ayarından ACTIVE_HOURS üretir.
    # Eski config.py ACTIVE_HOURS doğrudan verilmişse geriye dönük onu kullanır.
    legacy = cfg.get("ACTIVE_HOURS")
    if isinstance(legacy, dict) and legacy:
        out = {}
        for d in range(7):
            out[d] = legacy.get(d) or legacy.get(str(d)) or []
        return out
    sleep_start = cfg.get("SLEEP_START") or "10:00"
    sleep_end = cfg.get("SLEEP_END") or "06:00"
    active_days = cfg.get("ACTIVE_DAYS")
    if active_days is None:
        active_days = [0, 1, 2, 3, 4, 5, 6]
    day_set = set(int(d) for d in active_days)
    s = _hm(sleep_start)
    e = _hm(sleep_end)
    ah = {}
    for d in range(7):
        if d not in day_set:
            ah[d] = []
        elif s == e:
            ah[d] = [("00:00", "24:00")]
        elif s > e:
            # Gece yarısını geçen uyku (ör. 10:00-06:00 veya 23:00-06:30):
            # aktif pencere [sleep_end, sleep_start)
            ah[d] = [(sleep_end, sleep_start)]
        else:
            # Gündüz uykusu (ör. 10:00-18:00):
            # aktif pencereler [00:00, sleep_start) ve [sleep_end, 24:00)
            wins = []
            if s > 0:
                wins.append(("00:00", sleep_start))
            if e < 1440:
                wins.append((sleep_end, "24:00"))
            ah[d] = wins
    return ah


def schedule_status(utc, cfg):
    # (aktif_mi, sinir_utc) döner:
    # - Uyku kapalıysa: (True, None) -> 7/24 aktif
    # - Uyku açık ve aktif aralıktaysa: (True, bitis_utc)
    # - Uyku açık ve uyku saatindeyse: (False, sonraki_uyanis_utc_veya_None)
    if not cfg.get("SLEEP_ENABLED", True):
        return True, None
    ah = build_active_hours(cfg)
    end = active_end(utc, ah)
    if end is not None:
        # 24:00 bitişi ertesi gün 00:00 ile kesintisiz devam ediyorsa birleştir
        for _ in range(7):
            nxt = active_end(end, ah)
            if nxt is None or nxt <= end:
                break
            end = nxt
        else:
            return True, None
        return True, end
    return False, next_active_start(utc, ah)


def walk_minutes_from_meters(meters):
    # Şehir içi gerçek yürüme mesafesi ~1.3x kuş uçuşu, ~80 m/dk ortalama hız
    if meters is None or meters < 0:
        return 1
    m = (int(meters) * 13 + 400) // 800
    return max(1, min(60, m))


def battery_percent(v):
    # LiPo dinlenme gerilimi -> yaklaşık yüzde (doğrusal parçalı)
    table = ((4.20, 100), (4.10, 90), (4.00, 80), (3.90, 65), (3.80, 50),
             (3.70, 30), (3.60, 15), (3.50, 7), (3.40, 3), (3.30, 0))
    if v >= table[0][0]:
        return 100
    for i in range(1, len(table)):
        v1, p1 = table[i]
        if v >= v1:
            v0, p0 = table[i - 1]
            return int(p1 + (p0 - p1) * (v - v1) / (v0 - v1) + 0.5)
    return 0


def check_config(cfg):
    # Hata metni döner; sorun yoksa None
    w = cfg.get("YURUME_DK")
    if w is None or not isinstance(w, int) or w < 0 or w > 60:
        return "YURUME_DK ayarla"
    if not isinstance(cfg.get("HAZIRLIK_DK"), int) or cfg["HAZIRLIK_DK"] < 0:
        return "HAZIRLIK_DK hatalı"
    if not cfg.get("WIFI_SSID"):
        return "WIFI_SSID ayarla"
    if not cfg.get("STOP_ID"):
        return "STOP_ID ayarla"
    return None
