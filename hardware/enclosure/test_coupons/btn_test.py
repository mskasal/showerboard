"""12×12×7.3 mm tactile buton uyum testi v2 (dikey kilitlemeli + derin/yüksek basma paylı dugme).

v1 testinden gelen düzeltmeler:
  1. Yukarı-aşağı (Y) gevşeklik giderildi: `kilit` parçasının +Y ucuna örümcek bacakların
     dışında kalan köşelere basan iki durdurucu tırnak eklendi; switch ön stop (Y=6.9)
     ile kilit tırnakları (Y=19.1) arasında 12.2 mm'de sabitlenir. Yan pay 0.20 -> 0.10 mm.
  2. `dugme` başlığı v17'deki kanıtlanmış sıkı geçme kare sokete (3.2 mm derinlik, Ø6.4 boyun)
     döndürüldü ve duvar dışı basma payı 0.8 -> 1.8 mm artırıldı (rahat basma stroku).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build123d import Align, Axis, Box, Cylinder, Plane, Polyline, Pos, chamfer, extrude, make_face

import forge.check
from forge.check import check
import kutu

MIN = (Align.MIN, Align.MIN, Align.MIN)

# --- Buton ölçüleri ----------------------------------------------------------
BTN_W = 12.0         # satıcı verisi 2026-11-20 — kare gövde
BTN_TOTAL_D = 7.3    # satıcı verisi 2026-11-20 — toplam derinlik (pinler hariç)
BTN_BASE_T = 4.3     # varsayım 2026-11-20 (fotoğraf / v1 testinde doğrulandı)
BTN_STEM_W = 4.0     # satıcı verisi 2026-11-20 — sarı kare uç
BTN_FIT = 0.10       # v2: 0.20 -> 0.10 mm (sıkı kayar, sallanmaz -> 12.20 mm açıklık)

# --- Yuva ve kilit ölçüleri (kutu.py sol duvar koordinatları) -----------------
WALL = kutu.WALL     # 2.0 mm
FRONT = kutu.FRONT   # 1.6 mm
X_IN0 = WALL
BTN_YC = 13.0
ZC = kutu.ZC
BTN_HOLE_D = 8.0     # ~Ø6.8 mm sarı yakaya rahat geçiş

GUIDE_T = 2.4        # üst/alt kılavuz duvar kalınlığı
GROOVE_D = 1.25      # kilit oluğu derinliği (Z)
LOCK_T = 2.2         # kilit plakası kalınlığı (X)
LOCK_FIT = 0.20      # oluk kayma boşluğu
LOCK_Y0 = 9.40       # kilit oluğu ön durdurucusu (Y)

# --- Başlık (dugme) ölçüleri (v17 kanıtlanmış soket + artırılmış basma payı) -
CAP_HEAD_D = 10.4    # desk vurgu butonu dış çapı
CAP_COLLAR_D = 6.4   # v17 ölçüsü (Ø8.0 delik içinde sürtünmesiz)
CAP_STANDOFF = 1.8   # v2: 0.8 -> 1.8 mm duvar dışı basma payı
CAP_HEAD_T = 2.8     # v17 ölçüsü — sağlam başlık
CAP_SOCK_W = 3.95    # sıkı geçme: 4.10 hafif gevşekti -> 3.95 × 3.95 mm kare soket
CAP_SOCK_DEPTH = 3.2 # v17 kanıtlanmış soket derinliği (düşmez!)

# Türetilen koordinatlar
btn_y0 = BTN_YC - BTN_W / 2 - BTN_FIT   # 6.90
btn_y1 = BTN_YC + BTN_W / 2 + BTN_FIT   # 19.10
btn_z0 = ZC - BTN_W / 2 - BTN_FIT
btn_z1 = ZC + BTN_W / 2 + BTN_FIT

lock_x0 = X_IN0 + BTN_BASE_T + 0.10     # 6.40 (switch arka yüzü 6.30)
lock_x1 = lock_x0 + LOCK_T + 2 * LOCK_FIT  # 9.00
guide_x1 = lock_x1 + 1.4                # 10.40
guide_y0 = FRONT                        # 1.60
guide_y1 = btn_y1 + 1.5                 # 20.60 (pil 21.94'te başlar -> 1.34 mm pay)

lock_y1 = btn_y1 + 1.3                  # 20.40 (köşe tırnakları Y=19.10..20.40)


def prism_yz(points, x0, width):
    face = Plane.YZ * make_face(Polyline(*points, close=True))
    return Pos(x0, 0, 0) * extrude(face, width, dir=(1, 0, 0))


# --- 1. Sol duvar test kesiti (duvar) ----------------------------------------
test_z0 = btn_z0 - GUIDE_T - 2.0
test_z1 = btn_z1 + GUIDE_T + 2.0
duvar = Pos(0, 0, test_z0) * Box(WALL, guide_y1, test_z1 - test_z0, align=MIN)
duvar += Pos(0, 0, test_z0) * Box(guide_x1, FRONT, test_z1 - test_z0, align=MIN)
duvar = chamfer(duvar.edges().group_by(Axis.Y)[0], 0.4)

# Ø8.0 mm buton deliği + üst (+Y) 45° damla tavan
r = BTN_HOLE_D / 2
hole = Pos(-0.5, BTN_YC, ZC) * Cylinder(r, WALL + 1.0, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
hole += prism_yz(
    [(BTN_YC + r * 0.707, ZC - r * 0.707), (BTN_YC + r * 1.414, ZC), (BTN_YC + r * 0.707, ZC + r * 0.707)],
    -0.5, WALL + 1.0,
)
duvar -= hole

# Üst ve alt kılavuz duvarları (arkası +X tamamen açık!)
for s, z_wall in ((-1, btn_z0 - GUIDE_T), (1, btn_z1)):
    g = Pos(X_IN0 - 0.05, guide_y0 - 0.05, z_wall) * Box(
        guide_x1 - X_IN0 + 0.05, guide_y1 - guide_y0 + 0.05, GUIDE_T, align=MIN
    )
    # Ön durdurucu çıkıntı (Y=FRONT..btn_y0=6.90, X=2.0..4.8 -> örümcek bacakların önünde)
    z_step = btn_z0 if s < 0 else btn_z1 - 1.4
    g += Pos(X_IN0 - 0.05, guide_y0 - 0.05, z_step) * Box(
        2.8, btn_y0 - guide_y0 + 0.05, 1.4, align=MIN
    )
    # Kilit oluğu (arkadan açık, LOCK_Y0'da durur)
    z_gr = btn_z0 - GROOVE_D if s < 0 else btn_z1
    g -= Pos(lock_x0, LOCK_Y0, z_gr - 0.02) * Box(
        lock_x1 - lock_x0, guide_y1 - LOCK_Y0 + 0.5, GROOVE_D + 0.04, align=MIN
    )
    duvar += g

# --- 2. Arkadan sürgülü arka kilit (kilit) -----------------------------------
k_x0 = lock_x0 + LOCK_FIT               # 6.60
k_x1 = lock_x1 - LOCK_FIT               # 8.80 (kalınlık 2.2 mm)
k_z0 = btn_z0 - (GROOVE_D - LOCK_FIT)
k_z1 = btn_z1 + (GROOVE_D - LOCK_FIT)
# Ana gövde: LOCK_Y0+0.1 .. lock_y1 (9.50 .. 20.40) — arka köşe tırnaklarına kadar uzanır
# Ortada +Y tarafındaki 2 örümcek bacak (Z = ZC ± 2.5, Y ≈ 19) için U-kesik bırakılır!
kilit = Pos(k_x0, LOCK_Y0 + 0.1, k_z0) * Box(k_x1 - k_x0, lock_y1 - (LOCK_Y0 + 0.1), k_z1 - k_z0, align=MIN)
# Arka örümcek bacaklar için orta açıklık (Y=16.6..20.6, Z=ZC±3.8 -> 7.6 mm geniş boşluk)
kilit -= Pos(k_x0 - 0.5, 16.6, ZC - 3.8) * Box(
    (k_x1 - k_x0) + 1.0, lock_y1 - 16.6 + 0.5, 7.6, align=MIN
)
# Switch düz arka ortasına dayanan baskı yastığı (Y=9.7..16.3, X=6.30..6.60)
kilit += Pos(X_IN0 + BTN_BASE_T, 9.7, btn_z0 + 0.8) * Box(
    k_x0 - (X_IN0 + BTN_BASE_T) + 0.05, 6.6, (btn_z1 - btn_z0) - 1.6, align=MIN
)
# İki köşe +Y durdurucu tırnak (Y=19.10..20.40, Z=ZC±(4.0..5.8) -> örümcek bacakların dışında!)
# Switch gövdesinin arka kenarını (Y=19.10) öndeki 6.90 stopuna karşı sıkıştırır (dikey boşluk = 0)
for z_t0 in (ZC - 5.8, ZC + 4.0):
    kilit += Pos(4.2, btn_y1, z_t0) * Box(k_x0 - 4.2 + 0.05, lock_y1 - btn_y1, 1.8, align=MIN)

# --- 3. Dıştan geçmeli vurgu buton başlığı (dugme) ---------------------------
# v17 kanıtlanmış 3.2 mm derin 4.10×4.10 kare soket + artırılmış 1.8 mm basma payı
cap_x_in = 0.8                              # duvara 0.8 mm girer (v17 ile aynı)
cap_x_neck = -CAP_STANDOFF                  # -1.8 mm (duvarla 1.8 mm rahat basma payı)
cap_x_outer = -(CAP_STANDOFF + CAP_HEAD_T)  # -4.6 mm (2.8 mm başlık)
cap_head = Pos(cap_x_outer, BTN_YC, ZC) * Cylinder(
    CAP_HEAD_D / 2, CAP_HEAD_T, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
)
cap_head = chamfer(cap_head.edges().group_by(Axis.X)[0], 0.4)
cap_collar = Pos(cap_x_neck, BTN_YC, ZC) * Cylinder(
    CAP_COLLAR_D / 2, cap_x_in - cap_x_neck, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
)
dugme = cap_head + cap_collar
sock_x0 = cap_x_in - CAP_SOCK_DEPTH         # -2.4 mm (3.2 mm derin soket, üstte 2.2 mm dolu tavan)
dugme -= Pos(sock_x0, BTN_YC, ZC) * Box(
    cap_x_in - sock_x0 + 0.2, CAP_SOCK_W, CAP_SOCK_W, align=(Align.MIN, Align.CENTER, Align.CENTER)
)
dugme -= Pos(cap_x_in - 0.3, BTN_YC, ZC) * Box(
    0.5, CAP_SOCK_W + 0.4, CAP_SOCK_W + 0.4, align=(Align.MIN, Align.CENTER, Align.CENTER)
)

# --- Baskı düzeni (tüm parçalar desteksiz, Z=0'da) ---------------------------
GAP = 6.0
duvar_p = duvar.rotate(Axis.X, 90)          # ön taban (Y=0) tablada -> kutuyla birebir yön
kilit_p = kilit.rotate(Axis.Y, 90)          # düz arka yüz (k_x1) tablada, tırnaklar + yastık yukarı
dugme_p = dugme.rotate(Axis.Y, -90)         # dış yüz (-X) tablada, soket yukarı

baski = {"duvar": kutu.tablaya(duvar_p, 0)}
x_k = duvar_p.bounding_box().size.X + GAP
baski["kilit"] = kutu.tablaya(kilit_p, x_k)
x_d = x_k + kilit_p.bounding_box().size.X + GAP
baski["dugme"] = kutu.tablaya(dugme_p, x_d)

if __name__ == "__main__":
    forge.check.COLORS = ["#ece9e2", "#3a3a3a", "#e05a2b"]
    check({"duvar": duvar, "kilit": kilit, "dugme": dugme}, name="showerboard_btn_test_montaj")
    check(baski, name="showerboard_btn_test")
