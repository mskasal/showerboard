# Wi-Fi bağlantısı, AP (erişim noktası) modu ve zaman aşımlı HTTPS GET istemcisi.
# Normal modda Wi-Fi sadece veri çekerken açık tutulur.

import time
import socket
import gc

try:
    import network
except ImportError:
    network = None

try:
    import ssl
except ImportError:
    ssl = None

feed = lambda: None  # main.py watchdog besleme fonksiyonunu buraya koyar

_wlan = None
_ap = None


def url_encode(s):
    # UTF-8 URL kodlama (MicroPython'da urllib yok)
    raw = s.encode("utf-8") if isinstance(s, str) else bytes(s)
    out = []
    for b in raw:
        if (65 <= b <= 90) or (97 <= b <= 122) or (48 <= b <= 57) or b in (45, 46, 95, 126):
            out.append(chr(b))
        elif b == 32:
            out.append("%20")
        else:
            out.append("%%%02X" % b)
    return "".join(out)


def device_id():
    # MAC adresinin son 4 hex hanesi (ör. "A1B2")
    if network is None:
        return "TEST"
    try:
        w = network.WLAN(network.STA_IF)
        mac = w.config("mac")
        return "%02X%02X" % (mac[-2], mac[-1])
    except Exception:
        return "0001"


def scan(max_results=15):
    # Çevredeki 2.4 GHz ağları sinyal gücüne göre benzersiz listeler
    global _wlan
    if network is None:
        return []
    _wlan = network.WLAN(network.STA_IF)
    was_active = _wlan.active()
    if not was_active:
        _wlan.active(True)
    best = {}
    try:
        for item in _wlan.scan():
            try:
                ssid = item[0].decode("utf-8").strip()
            except Exception:
                continue
            if not ssid:
                continue
            rssi = item[3]
            sec = item[4]
            if ssid not in best or rssi > best[ssid]["rssi"]:
                best[ssid] = {"ssid": ssid, "rssi": rssi, "open": sec == 0}
    finally:
        if not was_active and not _wlan.isconnected():
            _wlan.active(False)
    nets = list(best.values())
    nets.sort(key=lambda x: x["rssi"], reverse=True)
    return nets[:max_results]


def connect_status(ssid, password, timeout_s=15, keep_active_on_fail=False):
    # (ok, ip_veya_hata_mesaji) döner
    global _wlan
    if network is None:
        return False, "Ağ donanımı yok"
    _wlan = network.WLAN(network.STA_IF)
    _wlan.active(True)
    try:
        _wlan.config(pm=0xA11140)  # güç tasarrufu kapalı: daha kararlı bağlantı
    except Exception:
        pass
    try:
        if _wlan.isconnected():
            _wlan.disconnect()
            time.sleep_ms(200)
    except Exception:
        pass
    _wlan.connect(ssid, password or "")
    t0 = time.ticks_ms()
    reason = "Bağlantı zaman aşımı"
    while not _wlan.isconnected():
        feed()
        st = _wlan.status()
        if st == getattr(network, "STAT_WRONG_PASSWORD", -3):
            reason = "Wi-Fi şifresi hatalı"
            print("WiFi hata durumu:", st)
            break
        if st == getattr(network, "STAT_NO_AP_FOUND", -2):
            reason = "Ağ bulunamadı (2.4 GHz olmalı)"
            print("WiFi hata durumu:", st)
            break
        if st == getattr(network, "STAT_CONNECT_FAIL", -1):
            reason = "Bağlantı reddedildi"
            print("WiFi hata durumu:", st)
            break
        if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
            print("WiFi zaman aşımı, durum:", st)
            break
        time.sleep_ms(200)
    if _wlan.isconnected():
        ip = _wlan.ifconfig()[0]
        print("WiFi bağlı:", ip)
        return True, ip
    if not keep_active_on_fail:
        off()
    return False, reason


def connect(ssid, password, timeout_s=15):
    ok, _ = connect_status(ssid, password, timeout_s=timeout_s)
    return ok


def connect_retry(ssid, password, tries=2):
    for _ in range(tries):
        if connect(ssid, password):
            return True
        feed()
        time.sleep(1)
    return False


def sta_ip():
    if network is None:
        return None
    w = _wlan or network.WLAN(network.STA_IF)
    if w.active() and w.isconnected():
        return w.ifconfig()[0]
    return None


def start_connect(ssid, password):
    # Bloklamayan bağlantı başlatma (AP açıkken HTTP soketini düşürmemek için)
    global _wlan
    if network is None:
        return
    _wlan = network.WLAN(network.STA_IF)
    _wlan.active(True)
    try:
        _wlan.config(pm=0xA11140)
    except Exception:
        pass
    try:
        if _wlan.isconnected():
            _wlan.disconnect()
            time.sleep_ms(100)
    except Exception:
        pass
    _wlan.connect(ssid, password or "")


def sta_state():
    # ("connected", ip) | ("connecting", None) | ("error", mesaj) | ("idle", None)
    if network is None:
        return "idle", None
    w = _wlan or network.WLAN(network.STA_IF)
    if not w.active():
        return "idle", None
    if w.isconnected():
        return "connected", w.ifconfig()[0]
    st = w.status()
    if st == getattr(network, "STAT_WRONG_PASSWORD", -3):
        return "error", "Wi-Fi şifresi hatalı"
    if st == getattr(network, "STAT_NO_AP_FOUND", -2):
        return "error", "Ağ bulunamadı (2.4 GHz olmalı)"
    if st == getattr(network, "STAT_CONNECT_FAIL", -1):
        return "error", "Bağlantı reddedildi"
    if st in (1, 2):   # STAT_CONNECTING / STAT_NOIP
        return "connecting", None
    return "idle", None


def start_ap(ssid, password=None, ip="192.168.4.1"):
    global _ap
    if network is None:
        return ssid, ip
    _ap = network.WLAN(network.AP_IF)
    _ap.active(False)
    time.sleep_ms(100)
    try:
        if password:
            _ap.config(essid=ssid, password=password)
        else:
            _ap.config(essid=ssid, security=0)
    except Exception:
        # Bazı firmware sürümlerinde argüman adı farklı olabilir
        try:
            _ap.config(ssid=ssid, security=0 if not password else 3,
                       key=password or "")
        except Exception:
            _ap.config(essid=ssid)
    _ap.ifconfig((ip, "255.255.255.0", ip, ip))
    _ap.active(True)
    t0 = time.ticks_ms()
    while not _ap.active() and time.ticks_diff(time.ticks_ms(), t0) < 3000:
        time.sleep_ms(50)
    print("AP açık:", ssid, _ap.ifconfig()[0])
    return ssid, _ap.ifconfig()[0]


def stop_ap():
    global _ap
    if network is None:
        return
    if _ap is None:
        _ap = network.WLAN(network.AP_IF)
    try:
        _ap.active(False)
    except Exception:
        pass
    _ap = None


def off():
    global _wlan
    if network is None:
        return
    if _wlan is None:
        _wlan = network.WLAN(network.STA_IF)
    try:
        _wlan.disconnect()
    except Exception:
        pass
    _wlan.active(False)


def power_down():
    # Derin uykudan önce: Wi-Fi çipinin beslemesini de kes (active(False)
    # sadece radyoyu durdurur; çip açık kalınca uykuda ~20 mA çekiliyordu).
    global _wlan
    stop_ap()
    off()
    if network is None:
        return
    try:
        _wlan.deinit()
    except Exception:
        pass
    _wlan = None


def is_on():
    if network is None:
        return False
    sta = _wlan is not None and _wlan.active()
    ap = _ap is not None and _ap.active()
    return sta or ap


def _expected_size(head):
    # Başlık tamamsa ve Content-Length varsa toplam yanıt boyunu döner
    end = head.find(b"\r\n\r\n")
    if end < 0:
        return None
    for line in head[:end].split(b"\r\n"):
        if line.lower().startswith(b"content-length:"):
            try:
                clen = int(line[15:].strip())
            except ValueError:
                return None
            if clen < 0:
                return None
            return end + 4 + clen
    return None


def _parse_response_chunks(chunks):
    # Başlığı tüm yanıtı birleştirmeden ayırır; büyük yanıtların RAM'de
    # iki kez (ham yanıt + gövde) kopyalanmasını önler.
    head = bytearray()
    end = -1
    idx = 0
    n = len(chunks)
    while idx < n:
        c = chunks[idx]
        chunks[idx] = None
        idx += 1
        head.extend(c)
        end = head.find(b"\r\n\r\n")
        if end >= 0:
            break
    if end < 0:
        raise OSError("bozuk HTTP yanıtı")
    nl = head.find(b"\r\n")
    status_line = bytes(head[:nl]) if nl >= 0 else bytes(head[:end])
    sparts = status_line.split(b" ")
    if len(sparts) < 2:
        raise OSError("bozuk HTTP durum satırı")
    try:
        status = int(sparts[1])
    except ValueError:
        raise OSError("bozuk HTTP durum kodu")
    rest = bytes(head[end + 4:])
    del head
    body_chunks = [rest] if rest else []
    while idx < n:
        c = chunks[idx]
        chunks[idx] = None
        idx += 1
        if c:
            body_chunks.append(c)
    del chunks
    body = b"".join(body_chunks)
    del body_chunks
    gc.collect()
    return status, body


def http_get(url, timeout_s=6, total_s=20, max_bytes=30000):
    # HTTPS/HTTP GET, (durum_kodu, gövde_bytes) döner.
    # Her soket işleminde zaman aşımı, toplamda da üst sınır var;
    # okuma sırasında watchdog beslenir.
    # Not: Pico W MicroPython'da CA kök sertifika paketi flash/RAM kısıtı nedeniyle
    # gömülü değildir (ssl.wrap_socket varsayılan olarak CERT_NONE kullanır).
    if url.startswith("https://"):
        port, rest, tls = 443, url[8:], True
    elif url.startswith("http://"):
        port, rest, tls = 80, url[7:], False
    else:
        raise ValueError("url")
    if "\r" in rest or "\n" in rest:
        raise ValueError("url")
    slash = rest.find("/")
    host, path = (rest, "/") if slash < 0 else (rest[:slash], rest[slash:])
    t0 = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.monotonic() * 1000)
    diff = time.ticks_diff if hasattr(time, "ticks_diff") else (lambda a, b: a - b)
    now_ms = time.ticks_ms if hasattr(time, "ticks_ms") else (lambda: int(time.monotonic() * 1000))
    gc.collect()
    feed()
    addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    feed()
    s = socket.socket()
    chunks = []
    try:
        s.settimeout(timeout_s)
        s.connect(addr)
        feed()
        if tls:
            gc.collect()
            if hasattr(ssl, "wrap_socket"):
                s = ssl.wrap_socket(s, server_hostname=host)
            else:
                ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=host)
            feed()
        req = (
            "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: showerboard-pico/1.0\r\n"
            "Accept: application/json\r\nConnection: close\r\n\r\n" % (path, host)
        ).encode()
        if hasattr(s, "write"):
            s.write(req)
        else:
            s.sendall(req)
        size = 0
        want = None   # başlık + Content-Length; biliniyorsa erken bitir
        while want is None or size < want:
            feed()
            if diff(now_ms(), t0) > total_s * 1000:
                raise OSError("toplam zaman aşımı")
            b = s.read(1024) if hasattr(s, "read") else s.recv(1024)
            if not b:
                break
            size += len(b)
            if size > max_bytes:
                raise OSError("yanıt çok büyük")
            chunks.append(b)
            if want is None and len(chunks) <= 4:
                want = _expected_size(b"".join(chunks))
    finally:
        if s is not None:
            s.close()
        s = None
        gc.collect()
    return _parse_response_chunks(chunks)
