# *****************************************************************************
# * | File        :   Pico_ePaper-2.13_V3.py
# * | Author      :   Waveshare team
# * | Function    :   Electronic paper driver
# * | Info        :
# *----------------
# * | This version:   V1.0
# * | Date        :   2021-11-01
# # | Info        :   python demo
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# Bu dosya Waveshare'in resmi Pico_ePaper_Code deposundaki
# python/Pico_ePaper-2.13_V3.py ve python/Pico_ePaper-2.13_V4.py
# sürücülerinin (Landscape sınıfları) birleştirilmiş halidir:
# https://github.com/waveshare/Pico_ePaper_Code
# Komut dizileri ve LUT tabloları aynen korunmuştur. Değişiklikler:
#  - V3/V4 tek sınıfta, `version` parametresiyle seçiliyor
#  - görüntü verisi bayt bayt değil 250 baytlık bloklar halinde gönderiliyor
#  - BUSY beklemesinde zaman aşımı ve watchdog besleme var, print'ler kaldırıldı
#  - tampon (framebuffer) bu sınıfın dışında, display.py'de tutuluyor
#
# Görüntü tamponu: 250x128 MONO_VLSB (yatay), 1 = beyaz, 0 = siyah.
# Panel 122 piksel yüksek; tamponun 6 satırı görünmez (display.py, EPD_Y_OFFSET).

from machine import Pin, SPI
import time

EPD_WIDTH = 122
EPD_HEIGHT = 250

# Pin eşlemesi Waveshare sürücüsünden (SPI1: SCK=GP10, MOSI=GP11)
RST_PIN = 12
DC_PIN = 8
CS_PIN = 9
BUSY_PIN = 13

WF_PARTIAL_2IN13_V3= [
    0x0,0x40,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x80,0x80,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x40,0x40,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x80,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x14,0x0,0x0,0x0,0x0,0x0,0x0,  
    0x1,0x0,0x0,0x0,0x0,0x0,0x0,
    0x1,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x22,0x22,0x22,0x22,0x22,0x22,0x0,0x0,0x0,
    0x22,0x17,0x41,0x00,0x32,0x36,
]

WS_20_30_2IN13_V3 = [ 
    0x80,0x4A,0x40,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x40,0x4A,0x80,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x80,0x4A,0x40,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x40,0x4A,0x80,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,0x0,
    0xF,0x0,0x0,0x0,0x0,0x0,0x0,    
    0xF,0x0,0x0,0xF,0x0,0x0,0x2,    
    0xF,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x1,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x0,0x0,0x0,0x0,0x0,0x0,0x0,    
    0x22,0x22,0x22,0x22,0x22,0x22,0x0,0x0,0x0,  
    0x22,0x17,0x41,0x0,0x32,0x36  
]


class EPD:
    def __init__(self, version="V4", feed=None):
        if version not in ("V3", "V4", "V4B"):
            raise ValueError("EPD_VERSION 'V3', 'V4' ya da 'V4B' olmalı")
        # V4B: Pico-ePaper-2.13-B V4 (siyah/beyaz/kırmızı). Kırmızı RAM (0x26)
        # sıfırlanır, kısmi yenileme yok, tam yenileme ~17 sn sürer.
        self.tricolor = version == "V4B"
        self.awake = False
        if self.tricolor:
            version = "V4"
        self.version = version
        self.feed = feed or (lambda: None)
        # Önce SPI, sonra kontrol pinleri. MicroPython'da SPI(1)'in varsayılan
        # MISO pini GP8 = DC pini: donanım resetinden sonraki ilk SPI(1)
        # kurulumu GP8'i SPI'a bağlar. DC önce tanımlanırsa GPIO olmaktan
        # çıkar, panel komut/veriyi ayırt edemez ve BUSY'de takılır.
        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)
        self.reset_pin = Pin(RST_PIN, Pin.OUT, value=1)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT, value=1)
        self.dc_pin = Pin(DC_PIN, Pin.OUT, value=0)
        self.width = (EPD_WIDTH // 8) * 8 + 8   # 128
        self.height = EPD_HEIGHT                # 250
        self.full_lut = WF_PARTIAL_2IN13_V3
        self.partial_lut = WS_20_30_2IN13_V3
        self.init()

    def delay_ms(self, ms):
        time.sleep_ms(ms)

    def reset(self):
        t = 50 if self.tricolor else 20     # B V4 resmi sürücüsü: 50/2/50 ms
        self.reset_pin.value(1)
        self.delay_ms(t)
        self.reset_pin.value(0)
        self.delay_ms(2)
        self.reset_pin.value(1)
        self.delay_ms(t)

    def send_command(self, command):
        self.dc_pin.value(0)
        self.cs_pin.value(0)
        self.spi.write(bytearray([command]))
        self.cs_pin.value(1)

    def send_data(self, data):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(bytearray([data]))
        self.cs_pin.value(1)

    def send_data1(self, buf):
        self.dc_pin.value(1)
        self.cs_pin.value(0)
        self.spi.write(buf)
        self.cs_pin.value(1)

    def send_image(self, image):
        # Landscape sürücüsündeki sırayla: bayt satırları sondan başa
        mv = memoryview(image)
        h = self.height
        for j in range(self.width // 8 - 1, -1, -1):
            self.send_data1(mv[j * h:(j + 1) * h])

    def ReadBusy(self, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = 30000 if self.tricolor else 10000
        if not self.tricolor:
            self.delay_ms(10)
        t0 = time.ticks_ms()
        while self.busy_pin.value() == 1:      # 0: boşta, 1: meşgul
            self.feed()
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                raise OSError("e-Paper BUSY zaman aşımı")
            self.delay_ms(10)
        if self.tricolor:
            self.delay_ms(20)

    def TurnOnDisplay(self):
        if self.tricolor:
            # B V4: güncelleme dizisi SWRESET sonrası varsayılanı (0xFF, OTP
            # dalga formu). 0xF7 bu panelde yenilemenin yarıda takılmasına yol açıyor.
            self.send_command(0x20)
            self.ReadBusy()
            return
        self.send_command(0x22)
        self.send_data(0xC7 if self.version == "V3" else 0xF7)
        self.send_command(0x20)
        self.ReadBusy()

    def TurnOnDisplayPart(self):
        self.send_command(0x22)
        self.send_data(0x0F if self.version == "V3" else 0xFF)
        self.send_command(0x20)
        self.ReadBusy()

    def LUT(self, lut):
        self.send_command(0x32)
        self.send_data1(bytearray(lut[0:153]))
        self.ReadBusy()

    def LUT_by_host(self, lut):
        self.LUT(lut)
        self.send_command(0x3F)
        self.send_data(lut[153])
        self.send_command(0x03)   # gate voltage
        self.send_data(lut[154])
        self.send_command(0x04)   # source voltage
        self.send_data(lut[155])  # VSH
        self.send_data(lut[156])  # VSH2
        self.send_data(lut[157])  # VSL
        self.send_command(0x2C)   # VCOM
        self.send_data(lut[158])

    def SetWindows(self, Xstart, Ystart, Xend, Yend):
        self.send_command(0x44)
        self.send_data((Xstart >> 3) & 0xFF)
        self.send_data((Xend >> 3) & 0xFF)
        self.send_command(0x45)
        self.send_data(Ystart & 0xFF)
        self.send_data((Ystart >> 8) & 0xFF)
        self.send_data(Yend & 0xFF)
        self.send_data((Yend >> 8) & 0xFF)

    def SetCursor(self, Xstart, Ystart):
        self.send_command(0x4E)
        self.send_data(Xstart & 0xFF)
        self.send_command(0x4F)
        self.send_data(Ystart & 0xFF)
        self.send_data((Ystart >> 8) & 0xFF)

    def pins_ok(self):
        # Kontrol pinleri GPIO (SIO, FUNCSEL 5) modunda mı? (rp2'ye özgü)
        try:
            import machine
            return all((machine.mem32[0x40014004 + 8 * n] & 0x1F) == 5
                       for n in (DC_PIN, CS_PIN, RST_PIN))
        except Exception:
            return True

    def prepare(self):
        # Çizimden önce: B/W panelde her seferinde init; B panel her çizimden
        # sonra uyutulduğu için (bkz. Display_Base) uyanıksa tekrar init yok.
        if not self.tricolor or not self.awake:
            self.init()

    def hard_reset(self, low_ms=1000):
        # Kurtarma: RST'yi uzun süre low tutup paneli tamamen sıfırla, sonra init
        self.reset_pin.value(0)
        for _ in range(low_ms // 100):
            self.feed()
            self.delay_ms(100)
        self.reset_pin.value(1)
        self.delay_ms(200)
        self.init()

    def init(self):
        self.reset()
        if not self.tricolor:
            self.delay_ms(100)
        self.ReadBusy()
        self.send_command(0x12)  # SWRESET
        self.ReadBusy()

        self.send_command(0x01)  # Driver output control
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x11)  # data entry mode (yatay)
        self.send_data(0x07)

        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)

        self.send_command(0x3C)  # BorderWaveform
        self.send_data(0x05)

        if self.tricolor:
            # Waveshare Pico_ePaper-2.13-B_V4.py ile aynı sıra ve değerler;
            # 0x21 A=0x80: kırmızı RAM ters (0xFF = kırmızı yok)
            self.send_command(0x18)  # dahili sıcaklık sensörü
            self.send_data(0x80)
            self.send_command(0x21)  # Display update control
            self.send_data(0x80)
            self.send_data(0x80)
        else:
            self.send_command(0x21)  # Display update control
            self.send_data(0x00)
            self.send_data(0x80)

            self.send_command(0x18)  # dahili sıcaklık sensörü
            self.send_data(0x80)

        self.ReadBusy()
        if self.version == "V3":
            self.LUT_by_host(self.partial_lut)
        self.awake = True

    def Clear(self):
        self.send_command(0x24)
        self.send_data1(b"\xff" * (self.height * self.width // 8))
        self.TurnOnDisplay()

    def display(self, image):
        self.send_command(0x24)
        self.send_image(image)
        self.TurnOnDisplay()

    def Display_Base(self, image):
        # Tam yenileme + kısmi yenileme için referans görüntüyü yaz
        self.send_command(0x24)
        self.send_image(image)
        self.send_command(0x26)
        if self.tricolor:
            # 0x26 bu panelde kırmızı katman; init'te ters çevrildi: 0xFF = kırmızı yok
            self.send_data1(b"\xff" * len(image))
        else:
            self.send_image(image)
        self.TurnOnDisplay()
        if self.tricolor:
            # Waveshare: çizim yokken panel uykuda olmalı (uzun süre yüksek
            # voltajda kalmasın). Sonraki çizimde prepare() uyandırır.
            self.sleep()

    def displayPartial(self, image):
        if self.tricolor:
            # Üç renkli panelde kısmi yenileme yok: tam yenileme
            self.prepare()
            self.Display_Base(image)
        elif self.version == "V3":
            self._partial_v3(image)
        else:
            self._partial_v4(image)

    def _partial_v3(self, image):
        self.reset_pin.value(0)
        self.delay_ms(1)
        self.reset_pin.value(1)

        self.LUT_by_host(self.full_lut)

        self.send_command(0x37)
        for b in (0x00, 0x00, 0x00, 0x00, 0x00, 0x40, 0x00, 0x00, 0x00, 0x00, 0x00):
            self.send_data(b)

        self.send_command(0x3C)
        self.send_data(0x80)

        self.send_command(0x22)
        self.send_data(0xC0)
        self.send_command(0x20)
        self.ReadBusy()

        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)

        self.send_command(0x24)
        self.send_image(image)
        self.TurnOnDisplayPart()

    def _partial_v4(self, image):
        self.reset()

        self.send_command(0x3C)  # BorderWavefrom
        self.send_data(0x80)

        self.send_command(0x01)  # Driver output control
        self.send_data(0xF9)
        self.send_data(0x00)
        self.send_data(0x00)

        self.send_command(0x11)  # data entry mode
        self.send_data(0x07)

        self.SetWindows(0, 0, self.width - 1, self.height - 1)
        self.SetCursor(0, 0)

        self.send_command(0x24)  # WRITE_RAM
        self.send_image(image)
        self.TurnOnDisplayPart()

    def sleep(self):
        self.send_command(0x10)  # derin uyku
        self.send_data(0x01)
        self.awake = False
        if self.tricolor:
            # B V4 resmi sürücüsü: 2 sn bekle, sonra RST low (module_exit)
            for _ in range(20):
                self.feed()
                self.delay_ms(100)
            self.reset_pin.value(0)
        else:
            self.delay_ms(100)
