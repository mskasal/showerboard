# Yerel kurulum portalı: DNS captive portal + hafif HTTP/JSON sunucusu.
# AP modu (WPA2 şifreli geçici Wi-Fi) ve LAN fallback modu (ev Wi-Fi'ı) desteklenir.

import gc
import json
import math
import os
import select
import socket
import time

import config_store
import i18n
import qr
import transit
import wifi

AP_IP = "192.168.4.1"
HTML_FILE = "portal.html"
IDLE_TIMEOUT_S = 600
_AP_PW_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

CAPTIVE_PATHS = (
    "/hotspot-detect.html",
    "/library/test/success.html",
    "/generate_204",
    "/gen_204",
    "/connecttest.txt",
    "/ncsi.txt",
    "/fwlink",
    "/redirect",
    "/canonical.html",
    "/success.txt",
)

SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'"),
)


def _now_s():
    return time.time()


def _gen_ap_password(length=8):
    # Oturum başına rastgele WPA2 şifresi (QR'a gömülür ve ekranda görünür)
    raw = os.urandom(length)
    n = len(_AP_PW_CHARS)
    return "".join(_AP_PW_CHARS[b % n] for b in raw)


def _safe_int(val):
    if isinstance(val, bool) or val is None:
        raise ValueError("not int")
    return int(val)


def _finite_coord(val, lo, hi):
    if isinstance(val, bool) or val is None:
        raise ValueError("coord")
    f = float(val)
    if not math.isfinite(f) or f < lo or f > hi:
        raise ValueError("coord range")
    return round(f, 6)


def url_decode(s):
    if not s:
        return ""
    s = s.replace("+", " ")
    out = bytearray()
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "%" and i + 2 < n:
            try:
                out.append(int(s[i + 1:i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        out.extend(ch.encode("utf-8"))
        i += 1
    try:
        return out.decode("utf-8")
    except Exception:
        return "".join(chr(b) for b in out if b < 128)


def parse_query(qs):
    out = {}
    if not qs:
        return out
    for pair in qs.split("&"):
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[url_decode(k)] = url_decode(v)
        else:
            out[url_decode(pair)] = ""
    return out


def build_dns_reply(req, ip=AP_IP):
    # Herhangi bir DNS A sorgusuna verilen IP ile yanıt üretir (captive portal).
    # Yanıt paketlerini (QR=1) ve sıkıştırma işaretçilerini reddeder.
    if len(req) < 12 or (req[2] & 0x80):
        return None
    i = 12
    n = len(req)
    while i < n and req[i] != 0:
        if req[i] >= 0xC0:
            return None
        i += req[i] + 1
    qend = i + 5
    if qend > n:
        return None
    octets = bytes(int(p) for p in ip.split("."))
    hdr = req[0:2] + b"\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00"
    question = req[12:qend]
    answer = b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + octets
    return hdr + question + answer


def validate_and_apply(cfg, payload):
    # Web formundan gelen ayarları doğrular ve cfg kopyası üzerinde uygular.
    # (ok, yeni_cfg_veya_hata_mesaji) döner.
    if not isinstance(payload, dict):
        return False, "Invalid payload"
    new_cfg = dict(cfg)

    if "LANG" in payload and payload["LANG"] is not None:
        lang = str(payload["LANG"]).strip().lower()
        if lang not in i18n.SUPPORTED:
            return False, "Unsupported language"
        new_cfg["LANG"] = lang

    ssid = str(payload.get("WIFI_SSID") or "").strip()
    if not ssid:
        return False, "Wi-Fi SSID required"
    if len(ssid.encode("utf-8")) > 32:
        return False, "Wi-Fi SSID too long (max 32 bytes)"
    new_cfg["WIFI_SSID"] = ssid

    pw = payload.get("WIFI_PASSWORD")
    if isinstance(pw, str) and pw != "":
        if len(pw.encode("utf-8")) > 63:
            return False, "Wi-Fi password too long (max 63 bytes)"
        new_cfg["WIFI_PASSWORD"] = pw
    elif ssid != cfg.get("WIFI_SSID"):
        new_cfg["WIFI_PASSWORD"] = ""

    stop_id = str(payload.get("STOP_ID") or "").strip()
    if not stop_id or not transit.is_valid_stop_id(stop_id):
        return False, "Invalid stop ID"
    new_cfg["STOP_ID"] = stop_id
    new_cfg["STOP_NAME"] = str(payload.get("STOP_NAME") or stop_id)[:40]
    new_cfg["STOP_NAME_HINT"] = str(payload.get("STOP_NAME_HINT") or new_cfg["STOP_NAME"])[:40]
    new_cfg["ADDRESS"] = str(payload.get("ADDRESS") or "")[:80]

    try:
        walk = _safe_int(payload.get("YURUME_DK"))
    except (TypeError, ValueError):
        return False, "Walk time must be a number"
    if walk < 0 or walk > 60:
        return False, "Walk time must be 0-60 min"
    new_cfg["YURUME_DK"] = walk

    try:
        prep = _safe_int(payload.get("HAZIRLIK_DK", 5))
    except (TypeError, ValueError):
        return False, "Prep time must be a number"
    if prep < 0 or prep > 60:
        return False, "Prep time must be 0-60 min"
    new_cfg["HAZIRLIK_DK"] = prep

    prods = payload.get("PRODUCTS")
    if isinstance(prods, dict):
        p = dict(config_store.DEFAULTS["PRODUCTS"])
        for k in p:
            if k in prods:
                p[k] = bool(prods[k])
        if not any(p.values()):
            return False, "Select at least one transport mode"
        new_cfg["PRODUCTS"] = p

    for list_key in ("DIRECTIONS", "DIRECT_LINES"):
        val = payload.get(list_key)
        if isinstance(val, list):
            new_cfg[list_key] = [str(x).strip()[:24] for x in val if str(x).strip()][:12]

    if "LAT" in payload and payload["LAT"] is not None:
        try:
            new_cfg["LAT"] = _finite_coord(payload["LAT"], -90.0, 90.0)
        except (TypeError, ValueError):
            return False, "Invalid latitude"
    if "LON" in payload and payload["LON"] is not None:
        try:
            new_cfg["LON"] = _finite_coord(payload["LON"], -180.0, 180.0)
        except (TypeError, ValueError):
            return False, "Invalid longitude"

    sleep_on = bool(payload.get("SLEEP_ENABLED", True))
    new_cfg["SLEEP_ENABLED"] = sleep_on
    s_start = str(payload.get("SLEEP_START") or "10:00")
    s_end = str(payload.get("SLEEP_END") or "06:00")
    if not (config_store.valid_hhmm(s_start) and config_store.valid_hhmm(s_end)):
        return False, "Sleep time must be HH:MM"
    new_cfg["SLEEP_START"] = s_start
    new_cfg["SLEEP_END"] = s_end
    new_cfg["ACTIVE_HOURS"] = None

    days = payload.get("ACTIVE_DAYS")
    if isinstance(days, list):
        clean_days = sorted(set(
            d for d in days if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 6
        ))
        new_cfg["ACTIVE_DAYS"] = clean_days

    try:
        mw = _safe_int(payload.get("MANUAL_WAKE_MIN", 30))
        new_cfg["MANUAL_WAKE_MIN"] = max(5, min(240, mw))
    except (TypeError, ValueError):
        pass

    try:
        rot = _safe_int(payload.get("ROTATION", 0))
    except (TypeError, ValueError):
        return False, "Invalid rotation"
    new_cfg["ROTATION"] = 180 if rot == 180 else 0

    epd = str(payload.get("EPD_VERSION") or new_cfg.get("EPD_VERSION", "V4B"))
    if epd in ("V3", "V4", "V4B"):
        new_cfg["EPD_VERSION"] = epd
    try:
        rmin = _safe_int(payload.get("REFRESH_MIN", new_cfg.get("REFRESH_MIN", 3)))
        new_cfg["REFRESH_MIN"] = max(1, min(15, rmin))
    except (TypeError, ValueError):
        pass
    return True, new_cfg


class PortalApp:
    # HTTP istek yönlendiricisi (donanımdan bağımsız test edilebilir)
    def __init__(self, cfg, host_ip, networks=None, ap_mode=True,
                 wifi_mod=wifi, transit_mod=transit, store_mod=config_store,
                 html_path=HTML_FILE, batt=None):
        self.cfg = dict(cfg)
        self.host_ip = host_ip
        self.networks = list(networks or [])
        self.ap_mode = ap_mode
        self.wifi = wifi_mod
        self.transit = transit_mod
        self.store = store_mod
        self.html_path = html_path
        self.batt = batt
        self.done = None
        self._pending_wifi = None

    def _sta_info(self):
        if hasattr(self.wifi, "sta_state"):
            st, info = self.wifi.sta_state()
            if st == "connected" and self._pending_wifi:
                ssid, pw = self._pending_wifi
                self._pending_wifi = None
                self.cfg["WIFI_SSID"] = ssid
                self.cfg["WIFI_PASSWORD"] = pw
                try:
                    self.store.save(self.cfg)
                except OSError:
                    pass
            elif st == "error":
                self._pending_wifi = None
            return st, info
        ip = self.wifi.sta_ip()
        return ("connected", ip) if ip else ("idle", None)

    def _check_security(self, method, path, req_headers):
        # DNS rebinding ve tarayıcı CSRF koruması (tüm /api/* uçlarında).
        hdrs = req_headers or {}
        host = hdrs.get("host", "").strip().lower()
        if host:
            bare = host.split(":", 1)[0]
            if bare != self.host_ip.lower():
                return False, "Forbidden host"
        if method == "POST":
            if hdrs.get("x-requested-with", "").strip().lower() != "showerboard":
                return False, "Missing X-Requested-With header"
            origin = hdrs.get("origin", "").strip().lower()
            if origin and origin != "http://" + self.host_ip.lower():
                return False, "Forbidden origin"
        return True, None

    def handle(self, method, target, body_bytes, headers=None):
        # (status_int, content_type, body_bytes_or_None, extra_headers, stream_file)
        if "?" in target:
            path, qs = target.split("?", 1)
        else:
            path, qs = target, ""

        if path in CAPTIVE_PATHS:
            return 302, "text/plain", b"Redirect", [("Location", "http://%s/" % self.host_ip)], None

        if method == "GET" and path in ("/", "/index.html"):
            return 200, "text/html; charset=utf-8", None, [], self.html_path

        if path.startswith("/api/"):
            ok, err = self._check_security(method, path, headers)
            if not ok:
                return self._json(403, {"ok": False, "error": err})

        if method == "GET" and path == "/api/state":
            st, info = self._sta_info()
            return self._json(200, {
                "config": self.store.public_view(self.cfg),
                "networks": self.networks,
                "sta_state": st,
                "sta_connected": st == "connected",
                "sta_ip": info if st == "connected" else None,
                "sta_error": info if st == "error" else None,
                "ap_mode": self.ap_mode,
                "battery": self.batt,
            })

        if method == "GET" and path == "/api/scan":
            try:
                self.networks = self.wifi.scan()
                return self._json(200, {"ok": True, "networks": self.networks})
            except Exception as e:
                return self._json(500, {"ok": False, "error": str(e)})

        if method == "POST" and path == "/api/wifi":
            try:
                data = json.loads(body_bytes or b"{}")
            except ValueError:
                return self._json(400, {"ok": False, "error": "Invalid JSON"})
            if not isinstance(data, dict):
                return self._json(400, {"ok": False, "error": "Invalid JSON"})
            ssid = str(data.get("ssid") or "").strip()
            pw = data.get("password")
            if not ssid or len(ssid.encode("utf-8")) > 32:
                return self._json(400, {"ok": False, "error": "Invalid Wi-Fi SSID"})
            if (pw is None or pw == "") and ssid == self.cfg.get("WIFI_SSID"):
                pw = self.cfg.get("WIFI_PASSWORD", "")
            pw = str(pw or "")
            if len(pw.encode("utf-8")) > 63:
                return self._json(400, {"ok": False, "error": "Password too long"})
            if hasattr(self.wifi, "start_connect"):
                self._pending_wifi = (ssid, pw)
                self.wifi.start_connect(ssid, pw)
                return self._json(200, {"ok": True, "connecting": True})
            ok, info = self.wifi.connect_status(ssid, pw, timeout_s=15, keep_active_on_fail=False)
            if ok:
                self.cfg["WIFI_SSID"] = ssid
                self.cfg["WIFI_PASSWORD"] = pw
                try:
                    self.store.save(self.cfg)
                except OSError:
                    pass
                return self._json(200, {"ok": True, "ip": info})
            return self._json(200, {"ok": False, "error": info})

        if method == "GET" and path == "/api/address":
            q = parse_query(qs).get("q", "").strip()[:100]
            if not q:
                return self._json(400, {"ok": False, "error": "Address required"})
            if not self.wifi.sta_ip():
                return self._json(400, {"ok": False, "error": "Connect to Wi-Fi first"})
            try:
                gc.collect()
                res = self.transit.search_address(q)
                return self._json(200, {"ok": True, "results": res})
            except MemoryError:
                gc.collect()
                if self.ap_mode:
                    self.done = "lan_fallback"
                    return self._json(200, {"ok": False, "lan_fallback": True})
                return self._json(500, {"ok": False, "error": "Out of memory"})
            except Exception as e:
                return self._json(502, {"ok": False, "error": "Address service: " + str(e)})

        if method == "GET" and path == "/api/nearby":
            params = parse_query(qs)
            try:
                lat = _finite_coord(params["lat"], -90.0, 90.0)
                lon = _finite_coord(params["lon"], -180.0, 180.0)
            except (KeyError, ValueError):
                return self._json(400, {"ok": False, "error": "Invalid coordinates"})
            if not self.wifi.sta_ip():
                return self._json(400, {"ok": False, "error": "Connect to Wi-Fi first"})
            try:
                gc.collect()
                stops = self.transit.nearby_stops(lat, lon)
                return self._json(200, {"ok": True, "stops": stops})
            except MemoryError:
                gc.collect()
                if self.ap_mode:
                    self.done = "lan_fallback"
                    return self._json(200, {"ok": False, "lan_fallback": True})
                return self._json(500, {"ok": False, "error": "Out of memory"})
            except Exception as e:
                return self._json(502, {"ok": False, "error": "Stop service: " + str(e)})

        if method == "POST" and path == "/api/save":
            try:
                data = json.loads(body_bytes or b"{}")
            except ValueError:
                return self._json(400, {"ok": False, "error": "Invalid JSON"})
            ok, res = validate_and_apply(self.cfg, data)
            if not ok:
                return self._json(400, {"ok": False, "error": res})
            try:
                self.store.save(res)
            except OSError as e:
                return self._json(500, {"ok": False, "error": "Save failed: " + str(e)})
            self.cfg = res
            self.done = "saved"
            return self._json(200, {"ok": True})

        if method == "POST" and path == "/api/cancel":
            self.done = "cancel"
            return self._json(200, {"ok": True})

        if method == "POST" and path == "/api/reset":
            self.store.reset()
            self.done = "reset"
            return self._json(200, {"ok": True})

        if path.startswith("/api/"):
            return self._json(404, {"ok": False, "error": "Not found"})

        # Captive portal: tanınmayan yolları ana sayfaya yönlendir
        return 302, "text/plain", b"Redirect", [("Location", "http://%s/" % self.host_ip)], None

    def _json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        return status, "application/json; charset=utf-8", body, [], None


def _recv_http(conn):
    conn.settimeout(3)
    buf = b""
    head_end = -1
    while head_end < 0 and len(buf) < 4096:
        chunk = conn.recv(512)
        if not chunk:
            break
        buf += chunk
        head_end = buf.find(b"\r\n\r\n")
    if head_end < 0:
        return None, None, b"", {}
    try:
        head = buf[:head_end].decode("utf-8")
    except Exception:
        head = "".join(chr(b) for b in buf[:head_end] if b < 128)
    rest = buf[head_end + 4:]
    lines = head.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) < 2:
        return None, None, b"", {}
    method, target = parts[0], parts[1]
    clen = 0
    req_headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        kl = k.strip().lower()
        vl = v.strip()
        if kl in ("host", "origin", "x-requested-with"):
            req_headers[kl] = vl
        elif kl == "content-length":
            try:
                clen = max(0, min(4096, int(vl)))
            except ValueError:
                clen = 0
    while len(rest) < clen:
        chunk = conn.recv(min(512, clen - len(rest)))
        if not chunk:
            break
        rest += chunk
    return method, target, rest[:clen], req_headers


def _send_all(conn, data):
    mv = memoryview(data)
    sent = 0
    total = len(data)
    while sent < total:
        n = conn.send(mv[sent:])
        if not n:
            break
        sent += n


def _serve_client(conn, app):
    try:
        method, target, body, req_headers = _recv_http(conn)
        if not method:
            return
        status, ctype, resp_body, headers, stream_file = app.handle(method, target, body, req_headers)
        reason = {200: "OK", 302: "Found", 400: "Bad Request", 403: "Forbidden",
                  404: "Not Found", 500: "Error", 502: "Bad Gateway"}.get(status, "OK")
        hdr = ["HTTP/1.1 %d %s" % (status, reason),
               "Content-Type: " + ctype,
               "Cache-Control: no-store",
               "Connection: close"]
        for k, v in SECURITY_HEADERS:
            hdr.append("%s: %s" % (k, v))
        for k, v in headers:
            hdr.append("%s: %s" % (k, v))
        if stream_file:
            fsize = os.stat(stream_file)[6]
            hdr.append("Content-Length: %d" % fsize)
            _send_all(conn, ("\r\n".join(hdr) + "\r\n\r\n").encode("utf-8"))
            with open(stream_file, "rb") as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    _send_all(conn, chunk)
        else:
            resp_body = resp_body or b""
            hdr.append("Content-Length: %d" % len(resp_body))
            _send_all(conn, ("\r\n".join(hdr) + "\r\n\r\n").encode("utf-8"))
            if resp_body:
                _send_all(conn, resp_body)
    except Exception as e:
        print("portal HTTP hata:", repr(e))
    finally:
        try:
            conn.close()
        except Exception:
            pass
        gc.collect()


def _run_server(app, with_dns=True, btn=None, idle_s=IDLE_TIMEOUT_S):
    http_sock = socket.socket()
    http_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    http_sock.bind(("0.0.0.0", 80))
    http_sock.listen(3)
    http_sock.setblocking(False)

    dns_sock = None
    if with_dns:
        dns_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        dns_sock.bind(("0.0.0.0", 53))
        dns_sock.setblocking(False)

    poller = select.poll()
    poller.register(http_sock, select.POLLIN)
    if dns_sock is not None:
        poller.register(dns_sock, select.POLLIN)

    last_activity = _now_s()
    try:
        while app.done is None:
            if btn is not None:
                ev = btn.poll()
                if ev in ("click", "double"):
                    app.done = "cancel"
                    break
                if ev == "factory":
                    app.store.reset()
                    app.done = "reset"
                    break
            if _now_s() - last_activity > idle_s:
                app.done = "timeout"
                break
            events = poller.poll(50)
            for sock, _ev in events:
                if sock is dns_sock:
                    try:
                        req, addr = dns_sock.recvfrom(512)
                        rep = build_dns_reply(req, app.host_ip)
                        if rep:
                            dns_sock.sendto(rep, addr)
                    except OSError:
                        pass
                elif sock is http_sock:
                    try:
                        conn, _ = http_sock.accept()
                    except OSError:
                        continue
                    last_activity = _now_s()
                    _serve_client(conn, app)
    finally:
        http_sock.close()
        if dns_sock is not None:
            dns_sock.close()
    time.sleep_ms(300) if hasattr(time, "sleep_ms") else time.sleep(0.3)
    return app.done


def run_ap(cfg, screen, btn=None, idle_s=IDLE_TIMEOUT_S, batt=None):
    # WPA2 şifreli geçici AP + QR captive portal kurulumu
    gc.collect()
    networks = []
    try:
        networks = wifi.scan()
    except Exception as e:
        print("WiFi tarama hata:", repr(e))

    if cfg.get("WIFI_SSID"):
        wifi.connect_status(cfg["WIFI_SSID"], cfg.get("WIFI_PASSWORD", ""), timeout_s=8)

    ap_ssid = "ShowerBoard-" + wifi.device_id()
    ap_pass = _gen_ap_password()
    ap_ssid, ap_ip = wifi.start_ap(ap_ssid, password=ap_pass, ip=AP_IP)

    lang = i18n.norm(cfg.get("LANG"))
    matrix = qr.encode(qr.wifi_payload(ap_ssid, ap_pass))
    screen.render_qr(matrix, i18n.t(lang, "setup_title"), [
        i18n.t(lang, "qr_step1"),
        ap_ssid,
        "PW: " + ap_pass,
        ap_ip,
        i18n.t(lang, "qr_close"),
    ])
    del matrix
    gc.collect()
    screen.show(full=True)

    app = PortalApp(cfg, ap_ip, networks=networks, ap_mode=True, batt=batt)
    try:
        return _run_server(app, with_dns=True, btn=btn, idle_s=idle_s)
    finally:
        wifi.stop_ap()
        wifi.off()
        gc.collect()


def run_lan(cfg, screen, btn=None, idle_s=IDLE_TIMEOUT_S, batt=None):
    # AP+STA belleği yetmezse: ev Wi-Fi'ına bağlanıp yerel IP QR'ı gösterir
    gc.collect()
    ok, ip = wifi.connect_status(cfg.get("WIFI_SSID", ""), cfg.get("WIFI_PASSWORD", ""), timeout_s=15)
    if not ok:
        return "no_wifi"
    lang = i18n.norm(cfg.get("LANG"))
    url = "http://%s/" % ip
    matrix = qr.encode(url)
    screen.render_qr(matrix, i18n.t(lang, "setup_title"), [
        i18n.t(lang, "qr_lan_ok"),
        i18n.t(lang, "qr_step1"),
        ip,
        i18n.t(lang, "qr_lan_hint"),
        i18n.t(lang, "qr_close"),
    ])
    del matrix
    gc.collect()
    screen.show(full=True)

    app = PortalApp(cfg, ip, networks=[], ap_mode=False, batt=batt)
    try:
        return _run_server(app, with_dns=False, btn=btn, idle_s=idle_s)
    finally:
        wifi.off()
        gc.collect()
