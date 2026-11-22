import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import qr


def decode_matrix(g):
    size = len(g)
    spec = [v for v in qr._VERSIONS if v[1] == size][0]
    _, _, total_cw, blocks, ec_cw, aligns = spec
    coords1 = (
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    )
    coords2 = (
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
        (size - 5, 8), (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
        (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1),
    )
    f1 = sum(g[r][c] << (14 - i) for i, (r, c) in enumerate(coords1))
    f2 = sum(g[r][c] << (14 - i) for i, (r, c) in enumerate(coords2))
    assert f1 == f2
    raw_fmt = f1 ^ 0x5412
    assert ((raw_fmt >> 13) & 3) == 1
    mask = (raw_fmt >> 10) & 7
    assert f1 == qr._format_bits(mask)
    assert g[size - 8][8] == 1

    used = [[0] * size for _ in range(size)]
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(max(0, r0 - 1), min(size, r0 + 8)):
            for c in range(max(0, c0 - 1), min(size, c0 + 8)):
                used[r][c] = 1
    for ar in aligns:
        for ac in aligns:
            if not used[ar][ac]:
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        used[ar + dr][ac + dc] = 1
    for i in range(size):
        used[6][i] = used[i][6] = 1
    for i in range(9):
        used[8][i] = used[i][8] = 1
    for i in range(size - 8, size):
        used[8][i] = used[i][8] = 1

    bits = []
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
                    bits.append(g[r][c] ^ (1 if qr._mask_fn(mask, r, c) else 0))
        col -= 2
        up = not up

    cws = [sum(bits[i * 8 + j] << (7 - j) for j in range(8)) for i in range(total_cw + blocks * ec_cw)]
    bsize = total_cw // blocks
    data = []
    for bi in range(blocks):
        db = [cws[i * blocks + bi] for i in range(bsize)]
        eb = [cws[total_cw + i * blocks + bi] for i in range(ec_cw)]
        assert qr._rs_encode(db, ec_cw) == eb
        data.extend(db)
    dbits = "".join("%08d" % int(bin(b)[2:]) for b in data)
    assert dbits[:4] == "0100"
    n = int(dbits[4:12], 2)
    return bytes(int(dbits[12 + i * 8:20 + i * 8], 2) for i in range(n)).decode("utf-8")


class QrTest(unittest.TestCase):
    def test_roundtrip_all_versions(self):
        samples = [
            "http://192.168.4.1/",
            qr.wifi_payload("ShowerBoard-A1B2"),
            qr.wifi_payload("ShowerBoard-A1B2", "pass;1:2"),
            "A" * 17,
            "B" * 32,
            "C" * 53,
            "D" * 78,
            "E" * 106,
            "F" * 134,
        ]
        for s in samples:
            self.assertEqual(decode_matrix(qr.encode(s)), s)

    def test_wifi_payload_escaping(self):
        self.assertEqual(qr.wifi_payload("My;Net:1"), "WIFI:T:nopass;S:My\\;Net\\:1;;")
        self.assertEqual(qr.wifi_payload("Net", "a\\b"), "WIFI:T:WPA;S:Net;P:a\\\\b;;")

    def test_too_long_raises(self):
        with self.assertRaises(ValueError):
            qr.encode("X" * 135)


if __name__ == "__main__":
    unittest.main()
