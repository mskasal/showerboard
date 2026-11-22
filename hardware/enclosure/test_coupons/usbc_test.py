"""HW-373 (USB-C) kızak uyum testi v3: yalnızca arkadan (lehimli taraftan) sürgülü.

- Arka uç (lehimli B+/B-/OUT+/OUT- tarafı): sol 7 mm tamamen açık, kızak ve duvar yok.
- Ön uç (USB-C soket tarafı): iki kızağın ön ucu kapalı (1.2 mm stop); ortadaki 15 mm
  tamamen açık olduğundan USB-C soketi dışarı çıkar, PCB öne kaçmaz.
- Modül arkadan öne doğru düz sürülür, ön stopta durur; lehimler kızağa hiç girmez.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build123d import Align, Axis, Box, Cylinder, Pos, chamfer

import forge.check
from forge.check import check
import kutu

MIN = (Align.MIN, Align.MIN, Align.MIN)

PAD_L = 2.0
PAD_Z = 2.5
SOLDER_OPEN_X = 7.0  # arka (lehimli) uçta kızaksız tamamen açık bölge (mm)
FRONT_STOP_T = 1.2   # ön (USB-C) uçta kızak sonu durdurucu duvar kalınlığı (mm)

x0 = kutu.MOD_X0 - PAD_L
x1 = kutu.MOD_X1 + FRONT_STOP_T
z_lo = kutu.ZC - kutu.MOD_H / 2 - kutu.GROOVE_CLR - kutu.RAIL_T - PAD_Z
z_hi = kutu.ZC + kutu.MOD_H / 2 + kutu.GROOVE_CLR + kutu.RAIL_T + PAD_Z

parca = Pos(x0, kutu.Y_IN, z_lo) * Box(x1 - x0, kutu.CAP_T, z_hi - z_lo, align=MIN)
parca = chamfer(parca.edges().group_by(Axis.Y)[-1], 0.4)

# Kızaklar: arkadan (rail_x0) açık, önde (MOD_X1) 1.2 mm stop ile kapalı
gy0, gy1 = kutu.MOD_Y0 - kutu.GROOVE_FIT, kutu.MOD_Y1 + kutu.GROOVE_FIT
rail_y0 = gy0 - kutu.LIP_T
rail_x0 = kutu.MOD_X0 + SOLDER_OPEN_X
led_x = (kutu.MOD_X1 - kutu.LED_X1, kutu.MOD_X1 - kutu.LED_X2)

for s in (1, -1):
    z_edge = kutu.ZC + s * kutu.MOD_H / 2
    z_face = z_edge - s * kutu.GROOVE_D
    z_bottom = z_edge + s * kutu.GROOVE_CLR
    lo, hi = sorted((z_face, z_bottom + s * kutu.RAIL_T))
    rail = Pos(rail_x0, rail_y0, lo) * Box(x1 - rail_x0, kutu.Y_IN - rail_y0 + 0.01, hi - lo, align=MIN)
    glo, ghi = sorted((z_face, z_bottom))
    # Oluk arkadan (rail_x0) açık, önde MOD_X1 + 0.1'de biter -> ön uç kapalı stop
    rail -= Pos(rail_x0 - 0.5, gy0, glo - 0.01) * Box(
        (kutu.MOD_X1 + 0.1) - (rail_x0 - 0.5), gy1 - gy0, ghi - glo + 0.02, align=MIN
    )
    if s > 0:
        for lx in led_x:
            rail -= Pos(lx - kutu.LED_KEEP, rail_y0 - 1, lo - 1) * Box(
                2 * kutu.LED_KEEP, kutu.Y_IN, hi - lo + 2, align=MIN
            )
    parca += rail

# Şarj LED delikleri
led_z = kutu.ZC + kutu.MOD_H / 2 - kutu.LED_EDGE
for lx in led_x:
    parca -= Pos(lx, kutu.OUT_D, led_z) * Cylinder(kutu.LED_HOLE / 2, 2 * kutu.CAP_T + 2, rotation=(90, 0, 0))

# Dış yüz tablada (Z=0), kızaklar yukarı
test_p = kutu.tablaya(parca.rotate(Axis.X, -90), 0)

if __name__ == "__main__":
    bb = test_p.bounding_box()
    print(f"HW-373 kızak test v3: {bb.size.X:.1f} × {bb.size.Y:.1f} × {bb.size.Z:.1f} mm (arkadan sürgülü, ön stoplu)")
    forge.check.COLORS = ["#3a3a3a"]
    check({"usbc_test": test_p}, name="showerboard_usbc_test")
