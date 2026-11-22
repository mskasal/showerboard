"""showerboard kutusu v10 (desk stili): Pico W + Pico-ePaper-2.13-B + MakerFocus 1000 mAh LiPo + HW-373 (TP4056) + 12×12×7.3 tactile buton.

Dört parça, ayrı basılır, vidasız birleşir (desteksiz):
  - govde: önü kapalı, arkası açık kutu (desk stili: R2 köşeler, yan kaburgalar, 15° kaide).
    Sol duvarda btn_test v2 ile doğrulanan arkası açık 12×12×7.3 buton yuvası (Ø8.0 mm damla delik)
    ve sağ duvarda USB-C yarığı.
  - kapak: arka kapak. Pili, usbc_test v3 ile doğrulanan arkadan sürgülü HW-373 şarj modülünü
    (sol 7 mm açık, ön 1.2 mm stoplu) ve ekranı öne bastıran dört yaylı direği taşır.
    Dış yüzde desk stili tam boy kör nokta sırası (şarj LED'lerinin olduğu 2 delik açık).
  - kilit: butonun arkasına oluklardan sürülerek takılan U-kesikli kilitleme parçası (sıfır dikey boşluk).
  - dugme: 4×4 mm sarı kare mile dıştan sıkı geçmeli (3.95 mm soket, 3.2 mm derinlik, 1.8 mm basma payı)
    turuncu/kırmızı vurgu başlığı.

Baskı yönü: gövde ön yüzü tablada, kapak dış yüzü tablada, kilit arka düz yüzü tablada,
düğme dış yüzü tablada. Destek gerekmez.
"""

import math

from build123d import (
    Align,
    Axis,
    Box,
    Cylinder,
    Plane,
    Polyline,
    Pos,
    chamfer,
    extrude,
    fillet,
    make_face,
)

import forge.check
from forge.check import check

# --- Gerçek parçalar ---------------------------------------------------------
EPD_W = 65.11  # ölçüm 2026-11-01 — PCB boyu (stoplar buna dayanır)
EPD_W_MAX = 66.12  # ölçüm 2026-11-01 — en geniş yer (konnektör tarafındaki FPC kıvrımı, sağda)
EPD_H = 30.49  # ölçüm 2026-11-01
VIS_L = 5.0  # ölçüm 2026-11-01 — sol kenardan (konnektörün karşısı)
VIS_R = 10.0  # ölçüm 2026-11-01 — sağ (konnektör) kenarından
VIS_T = 2.0  # ölçüm 2026-11-01 — üstten
VIS_B = 2.5  # ölçüm 2026-11-01 — alttan
EPD_DEPTH = 2.75  # ölçüm 2026-11-01 — cam önünden PCB arkasına
STACK = 19.86  # ölçüm 2026-11-01 — camdan debug soketinin üstüne (Pico'nun sağ ucu)
STACK_LOW = 18.44  # ölçüm 2026-11-01 — debug soketi hariç en yüksek nokta (micro-USB metali)
PICO_L = 51.0  # datasheet: https://datasheets.raspberrypi.com/picow/pico-w-datasheet.pdf
DEBUG_ZONE = 8.0  # varsayım — debug soketinin Pico'nun sağ ucundan içeri uzandığı en fazla mesafe
BATT_L = 42.1  # ölçüm 2026-11-01 — MakerFocus 1000 mAh, boy
BATT_W = 25.0  # ölçüm 2026-11-01
BATT_T = 10.44  # ölçüm 2026-11-01 — kalınlık
MOD_L = 27.93  # ölçüm 2026-11-01 — HW-373 PCB tam boyu
MOD_H = 17.12  # ölçüm 2026-11-01
MOD_T = 0.98  # ölçüm 2026-11-01 — PCB kalınlığı
MOD_TOTAL_T = 4.17  # ölçüm 2026-11-01 — PCB + USB-C
USBC_T = MOD_TOTAL_T - MOD_T  # ölçüm 2026-11-01 — soketin PCB'den yüksekliği
USBC_W = 9.0  # varsayım — soket ağzı genişliği (v4.4/v6 baskısında doğrulandı)
LED_X1 = 7.66  # ölçüm 2026-11-01 — 1. LED'in USB ucundan uzaklığı
LED_X2 = 16.0  # ölçüm 2026-11-01 — 2. LED
LED_EDGE = 1.2  # varsayım — LED merkezinin uzun kenara uzaklığı

# Tactile buton (kullanıcı teknik verisi + fotoğraf + btn_test v2 doğrulaması 2026-11-20)
BTN_W = 12.0  # kullanıcı teknik verisi 2026-11-20
BTN_TOTAL_D = 7.3  # kullanıcı teknik verisi 2026-11-20 — pinler hariç toplam derinlik
BTN_BASE_T = 4.3  # fotoğraf / btn_test v2 doğrulandı 2026-11-20 — siyah gövde kalınlığı
BTN_STEM_W = 4.0  # kullanıcı teknik verisi 2026-11-20 — sarı kare mil

# --- Tasarım: desk stili -----------------------------------------------------
WALL = 2.0  # tasarım — desk.py wall=2.0 (kaburga dibi 1.4 ≥ 1.2 mm)
FRONT = 1.6  # tasarım — desk.py floor=1.6
CAP_T = 2.0  # tasarım — arka kapak plakası (kör delikler 0.8 → 1.2 mm kalır)
CORNER_R = 2.0  # tasarım — desk stili yumuşak köşe
IN_R = 1.0  # tasarım — iç köşe; köşede duvar ≥ 1.6 mm
FRONT_CHAMFER = 0.4  # tasarım — desk.py bed_chamfer=0.4
BACK_FILLET = 0.8  # tasarım — desk.py top_edge_size=0.8
WIN_CHAMFER = 0.8  # tasarım — pencere pahı
RIB_W = 0.8  # tasarım — desk.py rib_width
RIB_PITCH = 2.0  # tasarım — desk.py rib_pitch
RIB_DEPTH = 0.6  # tasarım — desk.py rib_depth (2.0 - 0.6 = 1.4 ≥ 1.2)
DOT_D = 1.6  # tasarım — desk.py grille_size
DOT_PITCH = 3.2  # tasarım — desk.py grille_pitch
DOT_DEPTH = 0.8  # tasarım — desk.py grille_depth (kör nokta sırası)

FIT = 0.2  # tasarım — ekran kartı ile üst/alt kızak arası
FIT_Z = 0.8  # tasarım — kart ile üst/alt duvar arası
LID_FIT = 0.20  # tasarım — tolerans tablosu: gevşek/kapak, köşeli
BATT_GAP = 0.4  # tasarım — pil ile kapak, pil ile sol duvar arası
PICO_GAP = 1.9  # tasarım — pil ile Pico arası nefes payı
BATT_MOD_GAP = 3.5  # tasarım — pil ile modül arası
FRONT_STOP_T = 1.2  # test 2026-11-20 (usbc_test v3) — ön kızak stop duvarı
MOD_END_GAP = LID_FIT + FRONT_STOP_T  # 1.4 mm — ön stop kapağın sağ kenarı (cx1) içinde kalır
FINGER_PLAY = 0.3  # tasarım — kart ile stoplar arası toplam boy boşluğu
FINGER_T = 1.4  # tasarım — stop kalınlığı
FINGER_H = 4.0  # tasarım — stop yüksekliği
FINGER_DZ = 11.5  # tasarım — stopların merkezden uzaklığı
RIB_GUIDE_DEPTH = 6.0  # tasarım — stopların arka kılavuz uzantısı
RIB_LEAD = 1.0  # tasarım — giriş pahı

# Yaylı direkler
POST_X = 3.0
POST_Z = 2.0
POST_PRESS = 0.5
POST_DX_L = 4.5
POST_DX_R = 12.0
TOOTH_L = 14.0
TOOTH_W = 3.5
TOOTH_T = 1.2
SLIT = 0.8

# Kapak üst klipsi
TAB_T = 1.4
TAB_FIT = 0.10
SNAP_L = 10.0
SNAP_W = 20.0
SNAP_H = 0.6
SNAP_POS = 6.5
SNAP_CLR = 0.1
SNAP_X_FIT = 0.05
NAIL_W = 12.0
NAIL_D = 1.0

# Kapak alt kancaları
HOOK_L = 5.0
HOOK_T = 1.6
HOOK_H = 0.8
HOOK_FLAT = 1.0
HOOK_CLR = 0.15

# Pil yatağı
BATT_RAIL_T = 1.2
BATT_RAIL_H = 7.0
BATT_RAIL_GAP = 0.25
BATT_RIB = 0.45

# Modül kızakları (usbc_test v3 ile doğrulandı 2026-11-20)
SOCKET_GAP = 0.3
GROOVE_FIT = 0.20
GROOVE_D = 0.9
GROOVE_CLR = 0.35
RAIL_T = 1.2
LIP_T = 1.0
SOLDER_OPEN_X = 7.0
LED_KEEP = 2.0
LED_HOLE = 1.6
USBC_CLEAR = 0.5
PLUG_RECESS_W = 13.0
PLUG_RECESS_H = 7.0
PLUG_RECESS_WALL = 0.6

# Tactile buton yuvası, kilit ve başlık (btn_test v2 doğrulandı 2026-11-20 + sıkılaştırılmış başlık soketi)
BTN_YC = 13.0
BTN_FIT = 0.10  # test 2026-11-20 (btn_test v2) — 12.20 mm açıklık
BTN_HOLE_D = 8.0  # test 2026-11-20 (btn_test v2) — ~Ø6.8 mm sarı yakaya rahat geçiş
BTN_GUIDE_T = 2.4
BTN_GROOVE_D = 1.25
LOCK_T = 2.2
LOCK_FIT = 0.20
LOCK_Y0 = 9.40
CAP_HEAD_D = 10.4
CAP_COLLAR_D = 6.4
CAP_STANDOFF = 1.8  # test 2026-11-20 (btn_test v2) — rahat basma mesafesi
CAP_HEAD_T = 2.8
CAP_SOCK_W = 3.95  # test 2026-11-20 — 4.10 hafif gevşekti, sıkı tutuş için 3.95 mm (giriş pahlı)
CAP_SOCK_DEPTH = 3.2

# Kaide
TILT = 15.0
PLINTH_Y = 4.0
PLINTH_INSET = CORNER_R + 2.0

# --- Türetilen ölçüler -------------------------------------------------------
IN_L = BATT_GAP + BATT_L + BATT_MOD_GAP + MOD_L + MOD_END_GAP
IN_H = EPD_H + 2 * FIT_Z
OUT_W = IN_L + 2 * WALL
OUT_H = IN_H + 2 * WALL
ZC = OUT_H / 2
X_IN0, X_IN1 = WALL, WALL + IN_L

Y_PICO = FRONT + STACK_LOW
Y_BATT0 = Y_PICO + PICO_GAP
Y_IN = Y_BATT0 + BATT_T + BATT_GAP
OUT_D = Y_IN + CAP_T

VIS_W = EPD_W - VIS_L - VIS_R
VIS_H = EPD_H - VIS_T - VIS_B
EPD_X0 = OUT_W / 2 - VIS_L - VIS_W / 2
EPD_X1 = EPD_X0 + EPD_W
EPD_Y1 = FRONT + EPD_DEPTH
EPD_Z0 = ZC - EPD_H / 2
assert EPD_X0 + EPD_W_MAX < X_IN1 - 0.3, "FPC kıvrımı sağ duvara değiyor"

BATT_X0 = X_IN0 + BATT_GAP
BATT_X1 = BATT_X0 + BATT_L
MOD_X1 = X_IN1 - MOD_END_GAP
MOD_X0 = MOD_X1 - MOD_L
SOCK_Y1 = Y_IN - SOCKET_GAP
MOD_Y1 = SOCK_Y1 - USBC_T
MOD_Y0 = MOD_Y1 - MOD_T
assert MOD_Y0 > FRONT + STACK + 1.0, "modül debug soketine çok yakın"
pico_x0 = (EPD_X0 + EPD_X1) / 2 - PICO_L / 2
pico_x1 = (EPD_X0 + EPD_X1) / 2 + PICO_L / 2
assert pico_x1 - DEBUG_ZONE > BATT_X1, "pil debug soketinin arkasına geliyor"

# Buton ve kilit koordinat + boşluk kontrolleri (btn_test v2 ile birebir)
btn_y0 = BTN_YC - BTN_W / 2 - BTN_FIT  # 6.90
btn_y1 = BTN_YC + BTN_W / 2 + BTN_FIT  # 19.10
btn_z0 = ZC - BTN_W / 2 - BTN_FIT
btn_z1 = ZC + BTN_W / 2 + BTN_FIT
lock_x0 = X_IN0 + BTN_BASE_T + 0.10  # 6.40
lock_x1 = lock_x0 + LOCK_T + 2 * LOCK_FIT  # 9.00
guide_x1 = lock_x1 + 1.4  # 10.40
guide_x_front = EPD_X0 - 0.5  # ekran PCB bölgesinde (Y<5) PCB'ye 0.5 mm pay bırakır
guide_y0 = FRONT  # 1.60
guide_y1 = btn_y1 + 1.5  # 20.60
lock_y1 = btn_y1 + 1.3  # 20.40
assert guide_y1 < Y_BATT0 - 1.0, "buton kılavuzu pile çok yakın"
assert guide_x1 < pico_x0 - 4.0, "buton kılavuzu Pico'ya çok yakın"
assert btn_z0 - BTN_GUIDE_T > ZC - FINGER_DZ + FINGER_H / 2 + 0.5, "buton kılavuzu alt stopa değiyor"
assert btn_z1 + BTN_GUIDE_T < ZC + FINGER_DZ - FINGER_H / 2 - 0.5, "buton kılavuzu üst stopa değiyor"

MIN = (Align.MIN, Align.MIN, Align.MIN)
R3 = math.sqrt(3)


def prism_yz(points, x0, width):
    """YZ düzleminde (y, z) çokgeni x0'dan +X yönünde width kadar uzatır."""
    face = Plane.YZ * make_face(Polyline(*points, close=True))
    return Pos(x0, 0, 0) * extrude(face, width, dir=(1, 0, 0))


def prism_xy(points, z0, height):
    """XY düzleminde (x, y) çokgeni z0'dan +Z yönünde height kadar uzatır."""
    face = Plane.XY * make_face(Polyline(*points, close=True))
    return Pos(0, 0, z0) * extrude(face, height, dir=(0, 0, 1))


def rounded_xz(x0, z0, w, h, y0, d, r):
    """Önden görünüşte R köşeli dikdörtgen, y0'dan d derinliğinde."""
    b = Box(w, d, h, align=MIN)
    return Pos(x0, y0, z0) * fillet(b.edges().filter_by(Axis.Y), r)


def mirror_z(points, top):
    return [(y, OUT_H - z) for y, z in points] if top else points


# --- Gövde -------------------------------------------------------------------
kabuk = rounded_xz(0, 0, OUT_W, OUT_H, 0, OUT_D, CORNER_R)
kabuk = chamfer(kabuk.edges().group_by(Axis.Y)[0], FRONT_CHAMFER)
kabuk = fillet(kabuk.edges().group_by(Axis.Y)[-1], BACK_FILLET)

# Kaide (15° eğim)
t = math.tan(math.radians(TILT))
y_p = (PLINTH_Y + t * OUT_D) / (1 + t)
z_p = -(y_p - PLINTH_Y)
kaide = prism_yz(
    [(PLINTH_Y, 1.0), (PLINTH_Y, 0), (y_p, z_p), (OUT_D, 0), (OUT_D, 1.0)],
    PLINTH_INSET,
    OUT_W - 2 * PLINTH_INSET,
)

govde = kabuk + kaide
govde -= rounded_xz(X_IN0, WALL, IN_L, IN_H, FRONT, OUT_D, IN_R)

# Desk stili yan kaburgalar
rib_z0, rib_z1 = CORNER_R + 2.5, OUT_H - CORNER_R - 2.5
for side_x in (0.0, OUT_W - RIB_DEPTH):
    y_cur = 3.5
    while y_cur + RIB_W <= OUT_D - 3.0:
        skip_left = side_x == 0.0 and (
            BTN_YC - CAP_HEAD_D / 2 - 2.2 < y_cur + RIB_W and y_cur < BTN_YC + CAP_HEAD_D / 2 + 2.2
        )
        skip_right = side_x > 0.0 and (y_cur + RIB_W > MOD_Y1 - 2.5)
        if not skip_left and not skip_right:
            govde -= Pos(side_x - (0.05 if side_x == 0 else 0), y_cur, rib_z0) * Box(
                RIB_DEPTH + 0.05, RIB_W, rib_z1 - rib_z0, align=MIN
            )
        y_cur += RIB_PITCH

# Ekran penceresi
win_x0 = EPD_X0 + VIS_L
win_z0 = EPD_Z0 + VIS_B
govde -= Pos(win_x0, -0.5, win_z0) * Box(VIS_W, FRONT + 1, VIS_H, align=MIN)
win_edges = govde.edges().filter_by(
    lambda e: abs(e.center().Y) < 1e-3
    and win_x0 - 0.1 < e.center().X < win_x0 + VIS_W + 0.1
    and win_z0 - 0.1 < e.center().Z < win_z0 + VIS_H + 0.1
)
govde = chamfer(win_edges, WIN_CHAMFER)

# Sol ve sağ stoplar
rib_y0 = FRONT
rib_d = EPD_Y1 - FRONT + RIB_GUIDE_DEPTH
for x0, x1 in ((X_IN0, EPD_X0), (EPD_X1 + FINGER_PLAY, X_IN1)):
    rib = Box(x1 - x0, rib_d, FINGER_H, align=MIN)
    back = rib.edges().filter_by(Axis.Z).group_by(Axis.Y)[-1].sort_by(Axis.X)
    rib = chamfer(back[-1] if x0 == X_IN0 else back[0], min(RIB_LEAD, x1 - x0 - 0.3))
    for zc in (ZC - FINGER_DZ, ZC + FINGER_DZ):
        govde += Pos(x0, rib_y0, zc - FINGER_H / 2) * rib

# Üst/alt kızaklar
zrail = Box(12.0, rib_d, FIT_Z - FIT, align=MIN)
for x0 in (EPD_X0 + 5, EPD_X1 - 17):
    for top in (False, True):
        r = chamfer(
            zrail.edges().filter_by(Axis.X).group_by(Axis.Y)[-1].group_by(Axis.Z)[0 if top else -1],
            FIT_Z - FIT - 0.05,
        )
        govde += Pos(x0, rib_y0, OUT_H - WALL - (FIT_Z - FIT) if top else WALL) * r

# Sol duvar buton deliği (Ø8.0 mm + üst +Y 45° damla tavan, desteksiz)
btn_r = BTN_HOLE_D / 2
btn_hole = Pos(-0.5, BTN_YC, ZC) * Cylinder(
    btn_r, WALL + 1.0, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
)
btn_hole += prism_yz(
    [
        (BTN_YC + btn_r * 0.707, ZC - btn_r * 0.707),
        (BTN_YC + btn_r * 1.414, ZC),
        (BTN_YC + btn_r * 0.707, ZC + btn_r * 0.707),
    ],
    -0.5,
    WALL + 1.0,
)
govde -= btn_hole

# Sol duvar arkası açık buton kılavuz duvarları (btn_test v2 ile birebir;
# ekran PCB hizasında Y<5.0 iken X=9.1'de kalır, sonra 45° ile 10.4'e çıkar -> sıfır çakışma & destek!)
y_step = EPD_Y1 + 0.65  # 5.00 mm (PCB arkasından 0.65 mm geride)
y_ramp_end = y_step + max(0.0, guide_x1 - guide_x_front)  # ~6.3 mm (45° geçiş, btn_y0=6.9'dan önce biter)
guide_prof = [
    (X_IN0 - 0.05, guide_y0 - 0.05),
    (guide_x_front, guide_y0 - 0.05),
    (guide_x_front, y_step),
    (guide_x1, y_ramp_end),
    (guide_x1, guide_y1),
    (X_IN0 - 0.05, guide_y1),
]
for s, z_wall in ((-1, btn_z0 - BTN_GUIDE_T), (1, btn_z1)):
    g = prism_xy(guide_prof, z_wall, BTN_GUIDE_T)
    # Ön durdurucu çıkıntı (Y=FRONT..btn_y0=6.90, X=2.0..4.8 -> örümcek bacakların önünde)
    z_step = btn_z0 if s < 0 else btn_z1 - 1.4
    g += Pos(X_IN0 - 0.05, guide_y0 - 0.05, z_step) * Box(2.8, btn_y0 - guide_y0 + 0.05, 1.4, align=MIN)
    # Kilit oluğu (arkadan açık, LOCK_Y0'da durur)
    z_gr = btn_z0 - BTN_GROOVE_D if s < 0 else btn_z1
    g -= Pos(lock_x0, LOCK_Y0, z_gr - 0.02) * Box(
        lock_x1 - lock_x0, guide_y1 - LOCK_Y0 + 0.5, BTN_GROOVE_D + 0.04, align=MIN
    )
    govde += g

# USB-C yarığı (sağ duvar)
slot_w = USBC_W + 2 * USBC_CLEAR
slot_y0 = MOD_Y1 - USBC_CLEAR
notch = Box(WALL + 1, OUT_D + 1 - slot_y0, slot_w, align=MIN)
notch = fillet(notch.edges().filter_by(Axis.X).group_by(Axis.Y)[0], 1.5)
govde -= Pos(X_IN1 - 0.5, slot_y0, ZC - slot_w / 2) * notch

sock_yc = (MOD_Y1 + SOCK_Y1) / 2
recess = Box(WALL, PLUG_RECESS_H, PLUG_RECESS_W, align=(Align.MIN, Align.CENTER, Align.CENTER))
recess = fillet(recess.edges().filter_by(Axis.X), PLUG_RECESS_H / 2 - 0.01)
recess = Pos(X_IN1 + PLUG_RECESS_WALL, sock_yc, ZC) * recess
govde -= recess

# --- Arka kapak --------------------------------------------------------------
cx0, cx1 = X_IN0 + LID_FIT, X_IN1 - LID_FIT
cz0, cz1 = WALL + LID_FIT, WALL + IN_H - LID_FIT
kapak = rounded_xz(cx0, cz0, cx1 - cx0, cz1 - cz0, Y_IN, CAP_T, max(0.4, IN_R - LID_FIT))
kapak = chamfer(kapak.edges().group_by(Axis.Y)[-1], 0.4)

# USB-C yarığını arkadan kapatan dil
key = Pos(cx1 - 0.01, Y_IN, ZC - slot_w / 2 + LID_FIT) * Box(
    OUT_W - cx1 + 0.01, CAP_T, slot_w - 2 * LID_FIT, align=MIN
)
kapak += key & kabuk
kapak -= recess

# Üst klips
y_c = Y_IN - SNAP_POS
y_e = y_c - SNAP_H - 0.5 - SNAP_H * R3
d = SNAP_H + SNAP_CLR
z_t = WALL + TAB_FIT
snap_x0 = OUT_W / 2 - SNAP_W / 2
kapak += Pos(snap_x0, Y_IN - SNAP_L, OUT_H - z_t - TAB_T) * Box(SNAP_W, SNAP_L + 0.01, TAB_T, align=MIN)
tirnak = [
    (y_e, z_t + 0.2), (y_e, z_t), (y_e + SNAP_H * R3, z_t - SNAP_H),
    (y_c - SNAP_H, z_t - SNAP_H), (y_c, z_t), (y_c, z_t + 0.2),
]
kapak += prism_yz(mirror_z(tirnak, True), snap_x0, SNAP_W)
oluk = [
    (y_e - SNAP_CLR, z_t + 0.3), (y_c + SNAP_CLR, z_t + 0.3), (y_c + SNAP_CLR, z_t),
    (y_c + SNAP_CLR - d, z_t - d), (y_e - SNAP_CLR + d * R3, z_t - d), (y_e - SNAP_CLR, z_t),
]
govde -= prism_yz(mirror_z(oluk, True), snap_x0 - SNAP_X_FIT, SNAP_W + 2 * SNAP_X_FIT)

# Alt kancalar
post_l, post_r = EPD_X0 + POST_DX_L, EPD_X1 - POST_DX_R
hook_xs = (
    (X_IN0 + IN_R + 0.4, post_l - POST_X / 2 - 0.5 - SLIT - 0.3),
    (snap_x0, snap_x0 + SNAP_W),
    (post_r + POST_X / 2 + 0.5 + SLIT + 0.3, X_IN1 - IN_R - 0.4),
)
hy0 = Y_IN - HOOK_L
hc = HOOK_CLR
for x0, x1 in hook_xs:
    assert x1 - x0 > 3.0, "kanca çok dar"
    kapak += Pos(x0, hy0, z_t) * Box(x1 - x0, HOOK_L + 0.01, HOOK_T, align=MIN)
    kapak += prism_yz(
        [(hy0, z_t + 0.2), (hy0, z_t - HOOK_H), (hy0 + HOOK_FLAT, z_t - HOOK_H),
         (hy0 + HOOK_FLAT + HOOK_H, z_t), (hy0 + HOOK_FLAT + HOOK_H, z_t + 0.2)],
        x0, x1 - x0,
    )
    govde -= prism_yz(
        [(hy0 - hc, z_t + 0.3), (hy0 - hc, z_t - HOOK_H - hc), (hy0 + HOOK_FLAT + hc, z_t - HOOK_H - hc),
         (hy0 + HOOK_FLAT + HOOK_H + 2 * hc, z_t), (hy0 + HOOK_FLAT + HOOK_H + 2 * hc, z_t + 0.3)],
        x0 - SNAP_X_FIT - 0.1, x1 - x0 + 2 * SNAP_X_FIT + 0.2,
    )

# Tırnak çentiği
kapak -= Pos(OUT_W / 2 - NAIL_W / 2, OUT_D - NAIL_D, cz1 - NAIL_D) * Box(
    NAIL_W, NAIL_D + 1, NAIL_D + 1, align=MIN
)

# Yaylı direkler
post_y_tip = EPD_Y1 - POST_PRESS
tooth_y0 = OUT_D - TOOTH_T
post_u = EPD_Z0 + 0.3 + POST_Z / 2 - cz0
for px, root_right in ((post_l, True), (post_r, False)):
    free = px - POST_X / 2 - 0.5 if root_right else px + POST_X / 2 + 0.5
    tx0 = free if root_right else free - TOOTH_L
    fx0 = free - SLIT if root_right else free
    for top in (False, True):
        e, s = (cz1, -1) if top else (cz0, 1)

        def zr(u0, u1):
            return sorted((e + s * u0, e + s * u1))

        for x0, w, (z0, z1) in (
            (min(tx0, fx0), TOOTH_L + SLIT, zr(TOOTH_W, TOOTH_W + SLIT)),
            (fx0, SLIT, zr(-0.5, TOOTH_W + SLIT)),
        ):
            kapak -= Pos(x0, Y_IN - 0.5, z0) * Box(w, CAP_T + 1, z1 - z0, align=MIN)
        z0, z1 = zr(-0.5, TOOTH_W)
        kapak -= Pos(tx0, Y_IN - 0.5, z0) * Box(TOOTH_L, tooth_y0 - Y_IN + 0.5, z1 - z0, align=MIN)
        zc = e + s * post_u
        post = Box(POST_X, tooth_y0 - post_y_tip + 0.01, POST_Z, align=MIN)
        post = chamfer(post.edges().group_by(Axis.Y)[0], 0.4)
        kapak += Pos(px - POST_X / 2, post_y_tip, zc - POST_Z / 2) * post

# Modül kızakları (usbc_test v3 ile birebir: sol 7 mm açık, ön uç 1.2 mm stoplu)
gy0, gy1 = MOD_Y0 - GROOVE_FIT, MOD_Y1 + GROOVE_FIT
rail_y0 = gy0 - LIP_T
rail_x0 = MOD_X0 + SOLDER_OPEN_X
led_x = (MOD_X1 - LED_X1, MOD_X1 - LED_X2)
for s in (1, -1):
    z_edge = ZC + s * MOD_H / 2
    z_face = z_edge - s * GROOVE_D
    z_bottom = z_edge + s * GROOVE_CLR
    lo, hi = sorted((z_face, z_bottom + s * RAIL_T))
    rail = Pos(rail_x0, rail_y0, lo) * Box(cx1 - rail_x0, Y_IN - rail_y0 + 0.01, hi - lo, align=MIN)
    glo, ghi = sorted((z_face, z_bottom))
    rail -= Pos(rail_x0 - 0.5, gy0, glo - 0.01) * Box(
        (MOD_X1 + 0.1) - (rail_x0 - 0.5), gy1 - gy0, ghi - glo + 0.02, align=MIN
    )
    if s > 0:
        for lx in led_x:
            rail -= Pos(lx - LED_KEEP, rail_y0 - 1, lo - 1) * Box(2 * LED_KEEP, Y_IN, hi - lo + 2, align=MIN)
    kapak += rail

# Desk stili: arka kapakta yazı yok; LED hizasında tam boy kör nokta sırası,
# sadece 2 şarj LED'i açık (boydan boya delik)
led_z = ZC + MOD_H / 2 - LED_EDGE
dot_x = cx0 + 7.0
while dot_x <= cx1 - 7.0:
    if all(abs(dot_x - lx) > 2.0 for lx in led_x):
        kapak -= Pos(dot_x, OUT_D - DOT_DEPTH, led_z) * Cylinder(
            DOT_D / 2, DOT_DEPTH + 0.5, rotation=(-90, 0, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
    dot_x += DOT_PITCH
for lx in led_x:
    kapak -= Pos(lx, OUT_D, led_z) * Cylinder(LED_HOLE / 2, 2 * CAP_T + 2, rotation=(90, 0, 0))

# Pil yatağı
br_x0 = post_l - POST_X / 2 - 0.5 + TOOTH_L + 0.5
br_x1 = BATT_X1 - 1.0
for s in (1, -1):
    z0, z1 = sorted((ZC + s * (BATT_W / 2 - 0.5), ZC + s * (MOD_H / 2 + 2.0)))
    kapak += Pos(BATT_X1 + BATT_GAP, Y_IN - 6, z0) * Box(1.2, 6.01, z1 - z0, align=MIN)
    face = ZC + s * (BATT_W / 2 + BATT_RAIL_GAP)
    z0, z1 = sorted((face, face + s * BATT_RAIL_T))
    kapak += Pos(br_x0, Y_IN - BATT_RAIL_H, z0) * Box(br_x1 - br_x0, BATT_RAIL_H + 0.01, z1 - z0, align=MIN)
    rib = Box(1.0, BATT_RAIL_H, BATT_RIB + 0.01, align=MIN)
    rib = chamfer(
        rib.edges().filter_by(Axis.X).group_by(Axis.Y)[0].group_by(Axis.Z)[0 if s > 0 else -1],
        BATT_RIB - 0.05,
    )
    for xr in (br_x0 + 4.0, br_x1 - 4.0):
        kapak += Pos(xr - 0.5, Y_IN - BATT_RAIL_H, face - BATT_RIB if s > 0 else face - 0.01) * rib

# --- Buton arka kilidi (kilit — btn_test v2 ile birebir) ---------------------
k_x0 = lock_x0 + LOCK_FIT
k_x1 = lock_x1 - LOCK_FIT
k_z0 = btn_z0 - (BTN_GROOVE_D - LOCK_FIT)
k_z1 = btn_z1 + (BTN_GROOVE_D - LOCK_FIT)
kilit = Pos(k_x0, LOCK_Y0 + 0.1, k_z0) * Box(k_x1 - k_x0, lock_y1 - (LOCK_Y0 + 0.1), k_z1 - k_z0, align=MIN)
kilit -= Pos(k_x0 - 0.5, 16.6, ZC - 3.8) * Box(
    (k_x1 - k_x0) + 1.0, lock_y1 - 16.6 + 0.5, 7.6, align=MIN
)
kilit += Pos(X_IN0 + BTN_BASE_T, 9.7, btn_z0 + 0.8) * Box(
    k_x0 - (X_IN0 + BTN_BASE_T) + 0.05, 6.6, (btn_z1 - btn_z0) - 1.6, align=MIN
)
for z_t0 in (ZC - 5.8, ZC + 4.0):
    kilit += Pos(4.2, btn_y1, z_t0) * Box(k_x0 - 4.2 + 0.05, lock_y1 - btn_y1, 1.8, align=MIN)

# --- Ayrı basılan vurgu buton başlığı (dugme) --------------------------------
# Sıkı geçme kare soket (3.95×3.95 mm, 3.2 mm derinlik, 0.3 mm giriş pahı) + 1.8 mm basma payı
cap_x_in = 0.8
cap_x_neck = -CAP_STANDOFF  # -1.8 mm
cap_x_outer = -(CAP_STANDOFF + CAP_HEAD_T)  # -4.6 mm
cap_head = Pos(cap_x_outer, BTN_YC, ZC) * Cylinder(
    CAP_HEAD_D / 2, CAP_HEAD_T, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
)
cap_head = chamfer(cap_head.edges().group_by(Axis.X)[0], 0.4)
cap_collar = Pos(cap_x_neck, BTN_YC, ZC) * Cylinder(
    CAP_COLLAR_D / 2, cap_x_in - cap_x_neck, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.MIN)
)
dugme = cap_head + cap_collar
sock_x0 = cap_x_in - CAP_SOCK_DEPTH  # -2.4 mm (3.2 mm derinlik, 2.2 mm dolu tavan)
dugme -= Pos(sock_x0, BTN_YC, ZC) * Box(
    cap_x_in - sock_x0 + 0.2, CAP_SOCK_W, CAP_SOCK_W, align=(Align.MIN, Align.CENTER, Align.CENTER)
)
# Soket ağzında 0.3 mm kılavuz pahı (kare mile rahat hizalanıp sıkı oturur)
dugme -= Pos(cap_x_in - 0.3, BTN_YC, ZC) * Box(
    0.5, CAP_SOCK_W + 0.4, CAP_SOCK_W + 0.4, align=(Align.MIN, Align.CENTER, Align.CENTER)
)

DESK_Z = govde.rotate(Axis.X, -TILT).bounding_box().min.Z


def montaj(shape):
    """Masadaki konum: 15° geriye yatık, kaidenin tabanı z=0."""
    return Pos(0, 0, -DESK_Z) * shape.rotate(Axis.X, -TILT)


def tablaya(shape, x):
    bb = shape.bounding_box()
    return Pos(x - bb.min.X, -bb.min.Y, -bb.min.Z) * shape


# --- Baskı düzeni (4 parça, hepsi desteksiz Z=0'da) --------------------------
GAP = 8.0
govde_p = govde.rotate(Axis.X, 90)   # ön yüz tablada
kapak_p = kapak.rotate(Axis.X, -90)  # dış yüz tablada
kilit_p = kilit.rotate(Axis.Y, 90)   # düz arka yüz tablada, tırnaklar + yastık yukarı
dugme_p = dugme.rotate(Axis.Y, -90)  # dış yüz tablada, soket yukarı

baski = {"govde": tablaya(govde_p, 0)}
x_kapak = govde_p.bounding_box().size.X + GAP
baski["kapak"] = tablaya(kapak_p, x_kapak)
x_kilit = x_kapak + kapak_p.bounding_box().size.X + GAP
baski["kilit"] = tablaya(kilit_p, x_kilit)
x_dugme = x_kilit + kilit_p.bounding_box().size.X + GAP
baski["dugme"] = tablaya(dugme_p, x_dugme)

if __name__ == "__main__":
    print(
        f"Kutu v10 (desk) dış ölçü: {OUT_W:.1f} × {OUT_H:.1f} × {OUT_D:.1f} mm (G × Y × D), "
        f"buton deliği Ø{BTN_HOLE_D:.1f} mm, başlık Ø{CAP_HEAD_D:.1f} mm (soket {CAP_SOCK_W:.2f} mm)"
    )
    forge.check.COLORS = ["#ece9e2", "#3a3a3a", "#555555", "#e05a2b"]
    check(
        {"govde": montaj(govde), "kapak": montaj(kapak), "kilit": montaj(kilit), "dugme": montaj(dugme)},
        name="showerboard_kutu_montaj",
    )
    check(baski, name="showerboard_kutu")
