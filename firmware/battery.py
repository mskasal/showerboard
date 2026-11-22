# Pil gerilimi (VSYS) ölçümü.
# Pico W'da VSYS/3 bölücüsü GPIO29'da (ADC3) ve bu pin Wi-Fi çipinin saat
# hattıyla paylaşılıyor; GPIO25 de Wi-Fi çipinin CS hattı. Bu yüzden ölçüm
# sadece Wi-Fi kapalıyken yapılır ve pinler ölçümden sonra geri verilir.

from machine import ADC, Pin
import logic


def read_vsys(samples=8):
    Pin(25, Pin.OUT, value=1)       # Wi-Fi çipini SPI'dan ayır
    Pin(29, Pin.IN, pull=None)      # ADC için analog giriş
    adc = ADC(3)
    adc.read_u16()                  # ilk ölçümü at
    total = 0
    for _ in range(samples):
        total += adc.read_u16()
    v = total / samples * 3.3 * 3 / 65535
    Pin(29, Pin.ALT, pull=Pin.PULL_DOWN, alt=7)  # Wi-Fi'a geri ver
    Pin(25, Pin.OUT, value=0)
    return v


def read(diode_drop_v=0.0, usb_threshold_v=4.35):
    # {"v": gerilim, "pct": yüzde veya None, "usb": bool}
    v = read_vsys() + diode_drop_v
    if v >= usb_threshold_v:
        return {"v": v, "pct": None, "usb": True}
    return {"v": v, "pct": logic.battery_percent(v), "usb": False}
