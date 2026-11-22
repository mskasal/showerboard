# BVG / VBB transport.rest istemcisi (yedek sunucu ile)

import gc
import json
import wifi
import logic
import timeutil

HOSTS = ("https://v6.bvg.transport.rest", "https://v6.vbb.transport.rest")
PRODUCT_KEYS = ("suburban", "subway", "bus", "tram", "regional", "express", "ferry")


class HTTPError(OSError):
    def __init__(self, status):
        super().__init__("HTTP %d" % status)
        self.status = status


def _get_json(path, max_bytes=30000):
    # Sunucuları sırayla dener; hepsi başarısızsa son hatayı fırlatır
    err = None
    for host in HOSTS:
        try:
            status, body = wifi.http_get(host + path, max_bytes=max_bytes)
            if status != 200:
                raise HTTPError(status)
            data = json.loads(body)
            del body
            gc.collect()
            return data
        except Exception as e:
            print("transit:", host, "hata:", repr(e))
            err = e
            gc.collect()
    raise err


def _slim_products(p):
    p = p or {}
    return dict((k, bool(p.get(k))) for k in PRODUCT_KEYS)


def is_valid_stop_id(stop_id):
    if not isinstance(stop_id, str) or not (1 <= len(stop_id) <= 32):
        return False
    for ch in stop_id:
        o = ord(ch)
        ok = (48 <= o <= 57) or (65 <= o <= 90) or (97 <= o <= 122) or ch in (":", "-", "_")
        if not ok:
            return False
    return True


def verify_stop(stop_id, name_hint):
    # (True/False, durak_adı). Ağ hatasında exception fırlatır.
    sid_str = str(stop_id or "").strip()
    if not is_valid_stop_id(sid_str):
        return False, "durak ID geçersiz"
    try:
        data = _get_json("/stops/%s?linesOfStops=false&pretty=false" % wifi.url_encode(sid_str), max_bytes=12000)
    except HTTPError as e:
        if e.status in (400, 404):
            return False, "durak bulunamadı"
        raise
    sid = str(data.get("id", ""))
    name = data.get("name", "")
    ok = sid == str(stop_id) and (not name_hint or name_hint.lower() in name.lower())
    return ok, name


def search_address(query, results=5):
    # Adresten koordinat bulur (Berlin / Brandenburg BVG/VBB)
    q = wifi.url_encode(query.strip())
    data = _get_json(
        "/locations?query=%s&results=%d&addresses=true&stops=false&poi=false&pretty=false" % (q, results),
        max_bytes=16000,
    )
    out = []
    if isinstance(data, list):
        for item in data:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue
            label = item.get("address") or item.get("name") or query
            out.append({"address": label, "lat": round(lat, 6), "lon": round(lon, 6)})
    del data
    gc.collect()
    return out


def nearby_stops(lat, lon, distance=2000, results=30):
    # Koordinata en yakın S-Bahn, U-Bahn, otobüs, tramvay duraklarını mesafesiyle döner.
    # BVG /locations/nearby ürün filtresini yok saydığı için 30 durak çekip
    # her ulaşım türünden en yakınları koruyoruz (otobüsler S/U-Bahn'ı bastırmasın).
    data = _get_json(
        "/locations/nearby?latitude=%s&longitude=%s&distance=%d&results=%d"
        "&stops=true&poi=false&linesOfStops=false&pretty=false" % (lat, lon, distance, results),
        max_bytes=28000,
    )
    all_stops = []
    if isinstance(data, list):
        for s in data:
            if s.get("type") not in ("stop", "station"):
                continue
            sid = str(s.get("id") or "")
            if not sid:
                continue
            dist = s.get("distance")
            dist_i = int(dist) if isinstance(dist, (int, float)) else 0
            all_stops.append({
                "id": sid,
                "name": s.get("name") or sid,
                "distance": dist_i,
                "walk_min": logic.walk_minutes_from_meters(dist_i),
                "products": _slim_products(s.get("products")),
            })
    del data
    # Her ulaşım türünden en yakın 4 durağı mutlaka listeye al
    picked = {}
    for kind in ("suburban", "subway", "tram", "bus"):
        cnt = 0
        for st in all_stops:
            if st["products"].get(kind):
                picked[st["id"]] = st
                cnt += 1
                if cnt >= 4:
                    break
    out = list(picked.values()) if picked else all_stops[:12]
    out.sort(key=lambda x: x["distance"])
    del all_stops
    gc.collect()
    return out


def _query(cfg, now):
    # Şimdiden başla: yetişilemeyen ama henüz kalkmamış tren de gösteriliyor
    q = "when=%s&duration=%d&results=%d&remarks=false&pretty=false&linesOfStops=false&stopovers=false" % (
        timeutil.iso_utc(now), cfg["TRANSIT_DURATION_MIN"], cfg["TRANSIT_RESULTS"])
    for k, v in cfg["PRODUCTS"].items():
        q += "&%s=%s" % (k, "true" if v else "false")
    return q


def fetch_departures(cfg, now):
    # (kalkış_listesi, realtime_güncelleme_zamanı_veya_None)
    sid = str(cfg.get("STOP_ID") or "").strip()
    if not is_valid_stop_id(sid):
        raise ValueError("invalid stop_id")
    data = _get_json("/stops/%s/departures?%s" % (wifi.url_encode(sid), _query(cfg, now)))
    if isinstance(data, dict):
        raw = data.get("departures", [])
        rt = data.get("realtimeDataUpdatedAt")
    else:
        raw, rt = data, None
    del data
    deps = []
    for d in raw:
        try:
            s = logic.slim_departure(d)
        except (ValueError, KeyError, TypeError) as e:
            print("transit: kalkış atlandı:", repr(e))
            continue
        if s is not None:
            deps.append(s)
    del raw
    gc.collect()
    if not isinstance(rt, int):
        rt = None
    return deps, rt
