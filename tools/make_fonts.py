# fonts/*.bin dosyalarını bir TTF fonttan üretir (bilgisayarda çalışır, Pillow gerekir).
# Kullanım: python3 tools/make_fonts.py [bold.ttf] [extrabold.ttf]
# Varsayılan: JetBrains Mono (SIL OFL 1.1). Hazır .bin dosyaları repoda var;
# bu scripti sadece fontları değiştirmek istersen çalıştır.

import os
import sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "firmware", "fonts")

CANDIDATES = {
    "bold": ["/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
             os.path.expanduser("~/Library/Fonts/JetBrainsMono-Bold.ttf")],
    "xbold": ["/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-ExtraBold.ttf",
              os.path.expanduser("~/Library/Fonts/JetBrainsMono-ExtraBold.ttf")],
}

TEXT = (" !%'()+,-./0123456789:?ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"
        "ÇĞİÖŞÜçğıöşüÄäß°")
# (ad, font dosyası, hedef rakam yüksekliği px, karakterler)
SPECS = [
    ("BIG", "xbold", 44, "0123456789:-"),
    ("MID", "xbold", 16, TEXT),
    ("SMALL", "bold", 9, TEXT),
]


def find(kind, override):
    if override:
        return override
    for p in CANDIDATES[kind]:
        if os.path.exists(p):
            return p
    sys.exit("Font bulunamadı (%s); yolu argüman olarak ver." % kind)


def load_for_digit_height(path, target):
    # Rakam '0' yüksekliği hedefe eşit olacak en büyük puntoyu bul
    best = None
    for size in range(6, 120):
        f = ImageFont.truetype(path, size)
        top, bottom = f.getbbox("0", anchor="ls")[1], f.getbbox("0", anchor="ls")[3]
        if bottom - top <= target:
            best = f
        else:
            break
    return best


def render(font, chars):
    adv = int(round(font.getlength("0")))
    asc, desc = font.getmetrics()
    glyphs = []
    top, bottom = 10 ** 6, -10 ** 6
    for ch in chars:
        img = Image.new("1", (adv * 2, asc + desc + 8), 0)
        d = ImageDraw.Draw(img)
        d.fontmode = "1"
        d.text((adv // 2, asc + 4), ch, font=font, fill=1, anchor="ls")
        bb = img.getbbox()
        if bb:
            top, bottom = min(top, bb[1]), max(bottom, bb[3])
        glyphs.append(img)
    out = []
    for ch, img in zip(chars, glyphs):
        cell = img.crop((adv // 2, top, adv // 2 + adv, bottom))
        out.append((ch, cell))
    return adv, bottom - top, out


def pack(img):
    w, h = img.size
    stride = (w + 7) // 8
    data = bytearray(stride * h)
    px = img.load()
    for y in range(h):
        for x in range(w):
            if px[x, y]:
                data[y * stride + x // 8] |= 0x80 >> (x % 8)
    return bytes(data)


def main():
    over = sys.argv[1:] + [None, None]
    paths = {"bold": find("bold", over[0]), "xbold": find("xbold", over[1])}
    # Dosya biçimi: ilk satır "genişlik,yükseklik,karakterler\n" (UTF-8),
    # ardından her karakter için sırayla MONO_HLSB glif verisi.
    os.makedirs(OUT, exist_ok=True)
    for name, kind, target, chars in SPECS:
        f = load_for_digit_height(paths[kind], target)
        w, h, glyphs = render(f, chars)
        blob = b"".join(pack(img) for _, img in glyphs)
        with open(os.path.join(OUT, name.lower() + ".bin"), "wb") as fp:
            fp.write(("%d,%d,%s\n" % (w, h, chars)).encode("utf-8"))
            fp.write(blob)
        print("%s: %dx%d, %d karakter, %d bayt" % (name, w, h, len(chars), len(blob)))


if __name__ == "__main__":
    main()
