# Ekran düzeni ve çizim.
# Cihazda: Screen(epd) ile e-Paper'a çizer.
# Bilgisayarda: `python3 display.py` örnek ekranları preview/*.png olarak üretir
# (Pillow gerekir), böylece tasarım cihaza yüklemeden görülebilir.

try:
    import framebuf
except ImportError:
    import os as _os
    import sys as _sys
    _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from tools import framebuf_pc as framebuf

import i18n
import timeutil

W, H = 250, 122          # mantıksal ekran (yatay)
BUF_H = 128              # sürücü tamponu 128 satır (8'in katı)
BLACK, WHITE = 0, 1

ROW_Y = (56, 90)         # iki tren satırının üst kenarı
ROW_H = 32
DIVIDER_Y = 51


def _path(name):
    try:
        import os
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", name)
    except (ImportError, AttributeError, NameError):
        return "fonts/" + name   # MicroPython: kök dizin


def _palette(ink):
    # Kaynak 1 -> ink, 0 -> zemin; zemin rengi "key" ile saydam yapılır
    p = framebuf.FrameBuffer(bytearray(1), 2, 1, framebuf.MONO_HLSB)
    p.pixel(0, 0, 1 - ink)
    p.pixel(1, 0, ink)
    return p


_PAL = {BLACK: _palette(BLACK), WHITE: _palette(WHITE)}


class Font:
    def __init__(self, name):
        with open(_path(name), "rb") as f:
            head = f.readline().decode("utf-8").rstrip("\n")
            self.data = bytearray(f.read())
        w, h, self.chars = head.split(",", 2)
        self.w, self.h = int(w), int(h)
        self.gsize = ((self.w + 7) // 8) * self.h

    def width(self, s):
        return len(s) * self.w

    def draw(self, fb, s, x, y, color=BLACK):
        mv = memoryview(self.data)
        pal = _PAL[color]
        for ch in s:
            if ch != " ":
                i = self.chars.find(ch)
                if i < 0:
                    i = self.chars.find("?")
                g = framebuf.FrameBuffer(mv[i * self.gsize:(i + 1) * self.gsize],
                                         self.w, self.h, framebuf.MONO_HLSB)
                fb.blit(g, x, y, 1 - color, pal)
            x += self.w
        return x


BIG = Font("big.bin")      # saat, 44 px rakam
MID = Font("mid.bin")      # trenler, 16 px rakam
SMALL = Font("small.bin")  # hava, pil, etiketler, 9 px rakam

# Glif hücresi içinde rakamın üst kenarı (Türkçe şapkalar için hücrede pay var)
MID_TOP = 6
SMALL_TOP = 4

# 12x12 ikonlar ('#' = siyah)
ICONS = {
    "sun": (
        ".....#......", "..#..#..#...", "...#...#....", "....###.....",
        "...#####....", "####.#.####.", "...#####....", "....###.....",
        "...#...#....", "..#..#..#...", ".....#......", "............"),
    "partly": (
        "..#..#......", "...###......", ".#######....", "..##..####..",
        "....######..", "...########.", "..##########", ".###########",
        ".###########", "..#########.", "............", "............"),
    "cloud": (
        "............", "....####....", "...######...", "..########..",
        ".##########.", "############", "############", "############",
        ".##########.", "............", "............", "............"),
    "fog": (
        "............", "############", "............", ".##########.",
        "............", "############", "............", ".##########.",
        "............", "############", "............", "............"),
    "rain": (
        "....####....", "...######...", "..########..", ".##########.",
        "############", ".##########.", "............", "..#..#..#...",
        ".#..#..#....", "#..#..#.....", "............", "............"),
    "snow": (
        "....####....", "...######...", "..########..", ".##########.",
        "############", ".##########.", "............", ".#...#...#..",
        "###.###.###.", ".#...#...#..", "............", "............"),
    "storm": (
        "....####....", "...######...", "..########..", ".##########.",
        "############", ".####..####.", ".....##.....", "....##......",
        "...######...", ".....##.....", "....##......", "...#........"),
    "umbrella": (
        ".....##.....", "...######...", ".##########.", "############",
        "#..#..#..#..", ".....#......", ".....#......", ".....#......",
        ".....#......", ".....#..#...", "......##....", "............"),
}


def icon(fb, name, x, y, color=BLACK):
    for r, row in enumerate(ICONS[name]):
        for c, ch in enumerate(row):
            if ch == "#":
                fb.pixel(x + c, y + r, color)


def battery_icon(fb, x, y, pct, color=BLACK):
    # 18x9 pil simgesi, dolu kısmı yüzdeye göre
    fb.rect(x, y, 16, 9, color)
    fb.fill_rect(x + 16, y + 3, 2, 3, color)
    fill = 0 if pct is None else (12 * pct + 50) // 100
    if fill:
        fb.fill_rect(x + 2, y + 2, fill, 5, color)


def short_direction(s, n):
    # "S Westkreuz (Berlin)" -> "Westkr"
    for p in ("S+U ", "S ", "U "):
        if s.startswith(p):
            s = s[len(p):]
            break
    i = s.find(" (")
    if i > 0:
        s = s[:i]
    return s[:n]


class Screen:
    def __init__(self, epd=None, rotation=0, y_offset=6, full_every=10, lang="en"):
        self.epd = epd
        self.rotation = rotation
        self.y_offset = y_offset
        self.full_every = full_every
        self.lang = i18n.norm(lang)
        self.buf = bytearray(W * BUF_H // 8)
        self.fb = framebuf.FrameBuffer(self.buf, W, BUF_H, framebuf.MONO_VLSB)
        self.out = bytearray(len(self.buf))
        self.last = None
        self.partials = 0
        self.need_full = True
        self.fail_streak = 0      # art arda başarısız güncelleme sayısı

    def _t(self, key):
        return i18n.t(self.lang, key)

    # ---- yardımcılar ----
    def _text_center(self, font, s, y, color=BLACK):
        font.draw(self.fb, s, (W - font.width(s)) // 2, y, color)

    def _clock(self, now):
        s = timeutil.hhmm(now) if now is not None else "--:--"
        BIG.draw(self.fb, s, 1, 3)

    def _status_corner(self, weather, batt):
        # Sağ üst: hava (ikon + sıcaklık), yağış olasılığı, pil.
        # Sağ kenara hizalı: en geniş satır pil + "100%" (22 + 4 karakter).
        x = W - 22 - SMALL.w * 4 - 1
        if weather:
            icon(self.fb, weather["kind"], x, 3)
            SMALL.draw(self.fb, "%d°" % round(weather["temp"]), x + 16, 3 - SMALL_TOP + 2)
            rain = weather.get("rain")
            if rain is not None and rain >= weather.get("rain_min", 20):
                icon(self.fb, "umbrella", x, 19)
                SMALL.draw(self.fb, "%d%%" % rain, x + 16, 19 - SMALL_TOP + 2)
        if batt:
            if batt.get("usb"):
                battery_icon(self.fb, x, 37, 100)
                SMALL.draw(self.fb, "USB", x + 22, 37 - SMALL_TOP)
            elif batt.get("pct") is not None:
                battery_icon(self.fb, x, 37, batt["pct"])
                SMALL.draw(self.fb, "%d%%" % batt["pct"], x + 22, 37 - SMALL_TOP)

    def _row(self, y, r, show_direction):
        fg, bg = BLACK, WHITE
        if r["urgent"]:
            self.fb.fill_rect(0, y, W, ROW_H, BLACK)
            fg, bg = WHITE, BLACK
        top = y + (ROW_H - 16) // 2 - MID_TOP     # 16 px rakamı satırda ortala
        # Hat kutusu (ters renk)
        bw = MID.width("S75") + 6
        self.fb.fill_rect(0, y + 4, bw, ROW_H - 8, fg)
        name = r["line"]
        if len(name) <= 3:
            MID.draw(self.fb, name, (bw - MID.width(name)) // 2, top, bg)
        else:
            short = name[:5]
            st = y + (ROW_H - 9) // 2 - SMALL_TOP
            SMALL.draw(self.fb, short, max(1, (bw - SMALL.width(short)) // 2), st, bg)
        # Kalkış saati ve rötar
        x = MID.draw(self.fb, timeutil.hhmm(r["when"]), bw + 5, top, fg)
        d = r["delay_min"]
        if d:
            x = MID.draw(self.fb, ("+%d" % d) if d > 0 else ("%d" % d), x + 2, top, fg)
        # Sağda: çıkış süresi
        if r.get("missed"):
            lbl = self._t("missed")
            right = W - MID.width(lbl) - 2
            MID.draw(self.fb, lbl, right, top, fg)
        elif r["urgent"]:
            lbl = self._t("urgent")
            right = W - MID.width(lbl) - 2
            MID.draw(self.fb, lbl, right, top, fg)
        else:
            num = "%d" % r["minutes"]
            unit = self._t("min_unit")
            uw = SMALL.width(unit)
            right = W - MID.width(num) - uw - 4
            MID.draw(self.fb, num, right, top, fg)
            SMALL.draw(self.fb, unit, W - uw - 1, top + MID_TOP + 16 - 9 - SMALL_TOP, fg)
        # Küçük etiketler: aktarmalı / sadece tarife / yön
        tags = []
        if not r["direct"]:
            tags.append(self._t("transfer"))
        if not r["realtime"]:
            tags.append(self._t("planned"))
        n = (right - 4 - (x + 5)) // SMALL.w
        if show_direction and n >= 3:
            tags.append(short_direction(r["direction"], n))
        tags = tags[:2]
        ty = y + (ROW_H - 9) // 2 if len(tags) == 1 else y + 5
        for t in tags:
            SMALL.draw(self.fb, t[:max(n, 4)], x + 5, ty - SMALL_TOP, fg)
            ty += 13

    def _message(self, title, detail=None):
        self._text_center(MID, title, ROW_Y[0] + 8 - MID_TOP)
        if detail:
            self._text_center(SMALL, detail, ROW_Y[0] + 38 - SMALL_TOP)

    # ---- ekranlar ----
    def render_main(self, now, tv, weather=None, batt=None, show_direction=True):
        # tv: logic.transit_view sonucu
        fb = self.fb
        fb.fill(WHITE)
        self._clock(now)
        self._status_corner(weather, batt)
        fb.hline(0, DIVIDER_Y, W, BLACK)
        st = tv["status"]
        if st == "ok":
            for y, r in zip(ROW_Y, tv["rows"]):
                self._row(y, r, show_direction)
        elif st == "stale":
            self._message(self._t("stale_title"), self._t("stale_detail") + timeutil.hhmm(tv["since"]))
        elif st == "none":
            self._message(self._t("none_title"), self._t("none_detail"))
        else:
            self._message(self._t("nodata_title"), tv.get("detail") or self._t("nodata_detail"))

    def render_message(self, now, title, detail=None, batt=None):
        # Hata/uyarı: saat yine en büyük öğe
        self.fb.fill(WHITE)
        self._clock(now)
        self._status_corner(None, batt)
        self.fb.hline(0, DIVIDER_Y, W, BLACK)
        self._message(title, detail)

    def render_sleep(self, next_start, batt=None, note=None):
        # Uykuda saat gösterilmez (güncellenmeyeceği için yanlış olurdu)
        fb = self.fb
        fb.fill(WHITE)
        self._status_corner(None, batt)
        MID.draw(fb, self._t("sleep_title"), 4, 14 - MID_TOP)
        fb.hline(0, DIVIDER_Y, W, BLACK)
        if next_start is not None:
            t = timeutil.berlin(next_start)
            s = "%s %02d:%02d" % (i18n.weekdays(self.lang)[t[6]], t[3], t[4])
            self._message(self._t("wake_prefix") + s, note)
        else:
            self._message(self._t("no_active_title"), note or self._t("no_active_detail"))

    def render_qr(self, matrix, title, lines):
        # Solda QR kodu (quiet zone ile), sağda kısa yönlendirme metni
        fb = self.fb
        fb.fill(WHITE)
        size = len(matrix)
        scale = max(1, min((H - 12) // size, 4))
        qw = size * scale
        qx = 6
        qy = (H - qw) // 2
        for r in range(size):
            row = matrix[r]
            ry = qy + r * scale
            for c in range(size):
                if row[c]:
                    fb.fill_rect(qx + c * scale, ry, scale, scale, BLACK)
        rx = qx + qw + 10
        avail_w = W - rx - 2
        max_mid = max(1, avail_w // MID.w)
        max_sm = max(1, avail_w // SMALL.w)
        if title:
            MID.draw(fb, title[:max_mid], rx, 6 - MID_TOP)
        y = 30
        for line in lines:
            if y > H - 10:
                break
            SMALL.draw(fb, str(line)[:max_sm], rx, y - SMALL_TOP)
            y += 15

    # ---- tamponu panele gönder ----
    def _transform(self):
        # Mantıksal 250x122 görüntüyü sürücünün tamponuna çevirir:
        # isteğe bağlı 180° döndürme ve dikey kaydırma (EPD_Y_OFFSET).
        src, out, off = self.buf, self.out, self.y_offset
        rot = self.rotation == 180
        vis = (1 << H) - 1
        pad = ((1 << (BUF_H - H)) - 1) << H     # görünmeyen satırlar beyaz
        mask = (1 << BUF_H) - 1
        fill = (1 << off) - 1
        for x in range(W):
            sx = W - 1 - x if rot else x
            col = 0
            for j in range(BUF_H // 8):
                b = src[j * W + sx]
                if rot:
                    col |= _REV[b] << (8 * (BUF_H // 8 - 1 - j))
                else:
                    col |= b << (8 * j)
            if rot:
                col >>= BUF_H - H
            col = (col & vis) | pad
            if off:
                col = ((col << off) | fill) & mask
            for j in range(BUF_H // 8):
                out[j * W + x] = (col >> (8 * j)) & 0xFF

    def show(self, full=False):
        # Değişiklik yoksa paneli yormaz. Her `full_every` kısmi yenilemede
        # bir tam yenileme yapar (gölgelenmeyi önler).
        # Panel BUSY'de takılırsa (OSError) kademeli kurtarma: önce init ile,
        # sonra uzun RST (hard_reset) ile tam yenilemeyi tekrar dener; ikisi de
        # olmazsa bu güncellemeyi atlar ve fail_streak'i artırır.
        self._transform()
        cur = bytes(self.out)
        if not full and not self.need_full and self.last == cur:
            return False
        try:
            if full or self.need_full or self.partials >= self.full_every:
                if self.epd is not None:
                    self.epd.prepare()
                    self.epd.Display_Base(self.out)
                self.partials = 0
                self.need_full = False
            else:
                if self.epd is not None:
                    self.epd.displayPartial(self.out)
                self.partials += 1
        except OSError as e:
            print("ekran:", e)
            if not self._recover():
                self.fail_streak += 1
                self.need_full = True
                self.last = None
                return False
        self.fail_streak = 0
        self.last = cur
        return True

    def _recover(self):
        for name, wake in (("init", self.epd.init), ("uzun reset", self.epd.hard_reset)):
            print("ekran: kurtarma (%s) deneniyor" % name)
            try:
                wake()
                self.epd.Display_Base(self.out)
                print("ekran: kurtarma (%s) başarılı" % name)
                self.partials = 0
                self.need_full = False
                return True
            except OSError as e:
                print("ekran: kurtarma (%s) başarısız:" % name, e)
        return False

    def sleep(self):
        if self.epd is not None:
            self.epd.sleep()
            self.need_full = True

    def save_png(self, path, scale=3):
        from PIL import Image
        img = Image.new("1", (W, H), 1)
        px = img.load()
        for y in range(H):
            for x in range(W):
                px[x, y] = self.fb.pixel(x, y)
        img = img.resize((W * scale, H * scale), Image.NEAREST).convert("RGB")
        img.save(path)


def _rev_table():
    t = bytearray(256)
    for i in range(256):
        r = 0
        for b in range(8):
            if i & (1 << b):
                r |= 0x80 >> b
        t[i] = r
    return t


_REV = _rev_table()


# ---------------------------------------------------------------------------
# Bilgisayarda önizleme: python3 display.py
# ---------------------------------------------------------------------------

def _preview():
    import os
    import logic

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview")
    os.makedirs(out_dir, exist_ok=True)
    cfg = {"YURUME_DK": 7, "HAZIRLIK_DK": 5, "DIRECT_LINES": ["S5", "S7"],
           "DIRECTIONS": [], "MAX_DATA_AGE_S": 180, "MAX_REALTIME_AGE_S": 300}
    now = timeutil.to_epoch(2026, 10, 26, 6, 31, 2)       # 07:31 Berlin (CET)
    valid = (now // 60 + 1) * 60

    def dep(line, hhmm_local, delay_min, direction):
        h, m = int(hhmm_local[:2]), int(hhmm_local[3:])
        t = timeutil.berlin_to_utc(2026, 10, 26, h, m)
        return {"line": line, "when": t + (delay_min or 0) * 60, "planned": t,
                "delay": None if delay_min is None else delay_min * 60, "direction": direction}

    weather = {"temp": 12.4, "kind": "rain", "rain": 60, "time": now}
    batt = {"pct": 87, "usb": False, "v": 3.98}
    scenes = {
        "1_normal": [dep("S5", "07:47", 2, "S Westkreuz (Berlin)"),
                     dep("S75", "07:44", 0, "S Warschauer Straße (Berlin)"),
                     dep("S7", "07:57", 0, "S Potsdam Hauptbahnhof")],
        "2_cik": [dep("S7", "07:44", 1, "S Potsdam Hauptbahnhof"),
                  dep("S5", "07:57", None, "S Westkreuz (Berlin)")],
        "3_akt_once": [dep("S75", "07:46", 0, "S Warschauer Straße (Berlin)"),
                       dep("S5", "07:52", 12, "S Spandau Bhf (Berlin)")],
        "8_gec": [dep("S5", "07:41", 1, "S Westkreuz (Berlin)"),
                  dep("S7", "07:48", 0, "S Potsdam Hauptbahnhof")],
    }
    s = Screen(lang="en")
    for name, deps in scenes.items():
        tv = logic.transit_view(now, valid, cfg, deps, True, now - 20)
        s.render_main(now, tv, weather, batt)
        s.save_png(os.path.join(out_dir, name + ".png"))
    s.render_main(now, logic.transit_view(now, valid, cfg, [], True, now - 400),
                  {"temp": -3, "kind": "snow", "rain": 0, "time": now}, {"usb": True, "pct": None})
    s.save_png(os.path.join(out_dir, "4_stale.png"))
    s.render_main(now, logic.transit_view(now, valid, cfg, [], False, None),
                  {"temp": 21, "kind": "sun", "rain": None, "time": now}, batt)
    s.save_png(os.path.join(out_dir, "5_nodata.png"))
    s.render_sleep(timeutil.berlin_to_utc(2026, 10, 27, 6, 30), {"pct": 9, "usb": False})
    s.save_png(os.path.join(out_dir, "7_sleep.png"))
    import qr
    m = qr.encode(qr.wifi_payload("ShowerBoard-A1B2", "K7M4P9X2"))
    s.render_qr(m, "Setup", ["1. Scan QR", "ShowerBoard-A1B2", "PW: K7M4P9X2", "192.168.4.1", "Press: Close"])
    s.save_png(os.path.join(out_dir, "9_qr_en.png"))
    # Turkish preview sample
    s_tr = Screen(lang="tr")
    s_tr.render_main(now, logic.transit_view(now, valid, cfg, scenes["1_normal"], True, now - 20), weather, batt)
    s_tr.save_png(os.path.join(out_dir, "10_normal_tr.png"))
    s_tr.render_qr(m, "Ayarlar", ["1. QR okut", "ShowerBoard-A1B2", "PW: K7M4P9X2", "192.168.4.1", "Bas: Kapat"])
    s_tr.save_png(os.path.join(out_dir, "11_qr_tr.png"))
    print("Önizlemeler:", out_dir)


if __name__ == "__main__":
    _preview()
