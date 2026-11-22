# Open-Meteo hava durumu (anahtar gerekmez)

import gc
import json
import wifi

URL = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
       "&current=temperature_2m,weather_code&hourly=precipitation_probability"
       "&forecast_hours=4&timezone=GMT&timeformat=unixtime")


def kind(code):
    # WMO hava kodu -> ikon adı
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return "cloud"


def rain_chance(times, probs, now, hours=2):
    # Saatlik değer bir önceki saati kapsar: [t-1sa, t]. Önümüzdeki
    # `hours` saatle kesişen değerlerin en büyüğü.
    best = None
    for t, p in zip(times, probs):
        if p is None:
            continue
        if t > now and t - 3600 < now + hours * 3600:
            best = p if best is None else max(best, p)
    return best


def fetch(lat, lon, now):
    status, body = wifi.http_get(URL % (lat, lon), max_bytes=8000)
    if status != 200:
        raise OSError("HTTP %d" % status)
    data = json.loads(body)
    del body
    cur = data["current"]
    h = data.get("hourly", {})
    w = {
        "temp": cur["temperature_2m"],
        "kind": kind(int(cur["weather_code"])),
        "rain": rain_chance(h.get("time", []), h.get("precipitation_probability", []), now),
        "time": now,
    }
    del data
    gc.collect()
    return w
