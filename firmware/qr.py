# Küçük, bağımlılıksız QR kod üreticisi (ISO/IEC 18004, Byte modu, ECC-L, V1-V6).
# MicroPython (Pico W) ve CPython'da çalışır; 134 bayta kadar veri destekler.

# (versiyon, boyut, toplam_veri_cw, blok_sayisi, blok_ec_cw, hizalama_merkezleri)
_VERSIONS = (
    (1, 21, 19, 1, 7, ()),
    (2, 25, 34, 1, 10, (6, 18)),
    (3, 29, 55, 1, 15, (6, 22)),
    (4, 33, 80, 1, 20, (6, 26)),
    (5, 37, 108, 1, 26, (6, 30)),
    (6, 41, 136, 2, 18, (6, 34)),
)


def _gf_mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
        b >>= 1
    return r


def _rs_gen(n):
    g = [1]
    p = 1
    for _ in range(n):
        nxt = [0] * (len(g) + 1)
        for i, c in enumerate(g):
            nxt[i] ^= c
            nxt[i + 1] ^= _gf_mul(c, p)
        g = nxt
        p = _gf_mul(p, 2)
    return g


def _rs_encode(data, ec_len):
    gen = _rs_gen(ec_len)
    rem = [0] * ec_len
    for b in data:
        f = b ^ rem[0]
        rem = rem[1:] + [0]
        if f:
            for i in range(ec_len):
                rem[i] ^= _gf_mul(gen[i + 1], f)
    return rem


def _format_bits(mask):
    # ECC Level L = 0b01
    data = (1 << 3) | (mask & 7)
    d = data << 10
    for i in range(4, -1, -1):
        if d & (1 << (i + 10)):
            d ^= 0x537 << i
    return ((data << 10) | d) ^ 0x5412


def _mask_fn(mask, r, c):
    if mask == 0:
        return (r + c) % 2 == 0
    if mask == 1:
        return r % 2 == 0
    if mask == 2:
        return c % 3 == 0
    if mask == 3:
        return (r + c) % 3 == 0
    if mask == 4:
        return ((r // 2) + (c // 3)) % 2 == 0
    if mask == 5:
        return ((r * c) % 2 + (r * c) % 3) == 0
    if mask == 6:
        return (((r * c) % 2 + (r * c) % 3) % 2) == 0
    return (((r + c) % 2 + (r * c) % 3) % 2) == 0


def _encode_data(raw, total_cw):
    bits = []

    def push(val, n):
        for i in range(n - 1, -1, -1):
            bits.append((val >> i) & 1)

    push(0b0100, 4)         # Byte modu
    push(len(raw), 8)       # Karakter sayısı (V1-V9 için 8 bit)
    for b in raw:
        push(b, 8)
    cap = total_cw * 8
    term = min(4, cap - len(bits))
    for _ in range(term):
        bits.append(0)
    while len(bits) % 8:
        bits.append(0)
    out = []
    for i in range(0, len(bits), 8):
        v = 0
        for j in range(8):
            v = (v << 1) | bits[i + j]
        out.append(v)
    pad = (0xEC, 0x11)
    pi = 0
    while len(out) < total_cw:
        out.append(pad[pi])
        pi ^= 1
    return out


def _make_codewords(raw, total_cw, blocks, ec_cw):
    data = _encode_data(raw, total_cw)
    if blocks == 1:
        return data + _rs_encode(data, ec_cw)
    # Eşit bloklu (V6: 2 x 68 veri + 2 x 18 EC)
    bsize = total_cw // blocks
    dblocks = [data[i * bsize:(i + 1) * bsize] for i in range(blocks)]
    eblocks = [_rs_encode(b, ec_cw) for b in dblocks]
    out = []
    for i in range(bsize):
        for b in dblocks:
            out.append(b[i])
    for i in range(ec_cw):
        for b in eblocks:
            out.append(b[i])
    return out


def _place_finder(grid, used, r0, c0, size):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            r, c = r0 + dr, c0 + dc
            if 0 <= r < size and 0 <= c < size:
                dark = (
                    0 <= dr <= 6 and 0 <= dc <= 6 and (
                        dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)
                    )
                )
                grid[r][c] = 1 if dark else 0
                used[r][c] = 1


def _place_align(grid, used, cr, cc):
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            dark = max(abs(dr), abs(dc)) != 1
            grid[cr + dr][cc + dc] = 1 if dark else 0
            used[cr + dr][cc + dc] = 1


def _place_format(grid, size, mask):
    bits = _format_bits(mask)
    # Sol üst çevresi
    coords1 = (
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    )
    # Sağ üst + sol alt
    coords2 = (
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
        (size - 5, 8), (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
        (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1),
    )
    for i in range(15):
        v = (bits >> (14 - i)) & 1
        r1, c1 = coords1[i]
        r2, c2 = coords2[i]
        grid[r1][c1] = v
        grid[r2][c2] = v


def _penalty(grid, size):
    score = 0
    # Satır/sütun ardışık aynı renk + 2x2 bloklar
    for r in range(size):
        row = grid[r]
        run = 1
        for c in range(1, size):
            if row[c] == row[c - 1]:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run = 1
        if run >= 5:
            score += run - 2
    for c in range(size):
        run = 1
        for r in range(1, size):
            if grid[r][c] == grid[r - 1][c]:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run = 1
        if run >= 5:
            score += run - 2
    for r in range(size - 1):
        r0, r1 = grid[r], grid[r + 1]
        for c in range(size - 1):
            v = r0[c]
            if v == r0[c + 1] == r1[c] == r1[c + 1]:
                score += 3
    dark = sum(sum(row) for row in grid)
    pct = (dark * 100) // (size * size)
    score += (abs(pct - 50) // 5) * 10
    return score


def encode(text):
    # Metin -> NxN 0/1 matris (1 = siyah modül)
    raw = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    spec = None
    for v in _VERSIONS:
        if len(raw) <= v[2] - 2:   # 4 bit mod + 8 bit uzunluk = 1.5 bayt -> 2 bayt başlık
            spec = v
            break
    if spec is None:
        raise ValueError("QR verisi çok uzun (%d bayt)" % len(raw))
    _, size, total_cw, blocks, ec_cw, aligns = spec
    codewords = _make_codewords(raw, total_cw, blocks, ec_cw)

    base = [bytearray(size) for _ in range(size)]
    used = [bytearray(size) for _ in range(size)]

    # Bulucu desenler
    _place_finder(base, used, 0, 0, size)
    _place_finder(base, used, 0, size - 7, size)
    _place_finder(base, used, size - 7, 0, size)

    # Hizalama desenleri
    for ar in aligns:
        for ac in aligns:
            if not used[ar][ac]:
                _place_align(base, used, ar, ac)

    # Zamanlama çizgileri
    for i in range(8, size - 8):
        v = 1 - (i & 1)
        if not used[6][i]:
            base[6][i] = v
            used[6][i] = 1
        if not used[i][6]:
            base[i][6] = v
            used[i][6] = 1

    # Format bilgisi alanlarını rezerve et + sabit koyu modül
    for i in range(9):
        used[8][i] = 1
        used[i][8] = 1
    for i in range(size - 8, size):
        used[8][i] = 1
        used[i][8] = 1
    base[size - 8][8] = 1
    used[size - 8][8] = 1

    # Veri bitlerini zikzak yerleştir
    bit_idx = 0
    total_bits = len(codewords) * 8
    col = size - 1
    up = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not used[r][c]:
                    b = 0
                    if bit_idx < total_bits:
                        b = (codewords[bit_idx >> 3] >> (7 - (bit_idx & 7))) & 1
                        bit_idx += 1
                    base[r][c] = b
        col -= 2
        up = not up

    # En düşük cezalı maskeyi seç
    best_grid = None
    best_score = None
    for mask in range(8):
        g = [bytearray(row) for row in base]
        for r in range(size):
            for c in range(size):
                if not used[r][c] and _mask_fn(mask, r, c):
                    g[r][c] ^= 1
        _place_format(g, size, mask)
        sc = _penalty(g, size)
        if best_score is None or sc < best_score:
            best_score = sc
            best_grid = g
    return best_grid


def wifi_payload(ssid, password=None):
    # Standart Wi-Fi QR metni (iOS & Android kamera ile otomatik ağa katılma)
    def esc(s):
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace(":", "\\:")

    if password:
        return "WIFI:T:WPA;S:%s;P:%s;;" % (esc(ssid), esc(password))
    return "WIFI:T:nopass;S:%s;;" % esc(ssid)
