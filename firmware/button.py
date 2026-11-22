# Tek buton durum makinesi: kısa tek basış, çift basış, uzun basış, fabrika sıfırlama.
# ButtonTracker donanımdan bağımsızdır ve CPython'da birim testleriyle doğrulanır.

import time

try:
    _ticks_ms = time.ticks_ms
    _ticks_diff = time.ticks_diff
except AttributeError:
    _ticks_ms = lambda: int(time.monotonic() * 1000)
    _ticks_diff = lambda a, b: a - b


class ButtonTracker:
    def __init__(self, debounce_ms=40, dbl_ms=0, long_ms=3500, factory_ms=9000):
        self.debounce_ms = debounce_ms
        self.dbl_ms = dbl_ms
        self.long_ms = long_ms
        self.factory_ms = factory_ms
        self.raw = False
        self.raw_since = None
        self.stable = False
        self.press_start = None
        self.long_fired = False
        self.factory_fired = False
        self.pending_clicks = 0
        self.last_release = None

    def reset(self):
        self.press_start = None
        self.long_fired = False
        self.factory_fired = False
        self.pending_clicks = 0
        self.last_release = None

    def update(self, pressed, now_ms):
        # pressed: True ise buton basılı. Olay döner: None | "click" | "double" | "long" | "factory"
        pressed = bool(pressed)
        if self.raw_since is None:
            self.raw = pressed
            self.raw_since = now_ms
            self.stable = pressed
            if pressed:
                self.press_start = now_ms
            return None

        if pressed != self.raw:
            self.raw = pressed
            self.raw_since = now_ms

        if pressed != self.stable and _ticks_diff(now_ms, self.raw_since) >= self.debounce_ms:
            self.stable = pressed
            if pressed:
                # Basış başlangıcı
                self.press_start = now_ms
                self.long_fired = False
                self.factory_fired = False
            else:
                # Bırakış
                was_long = self.long_fired or self.factory_fired
                self.press_start = None
                self.long_fired = False
                self.factory_fired = False
                if not was_long:
                    if self.dbl_ms <= 0:
                        return "click"
                    self.pending_clicks += 1
                    self.last_release = now_ms
                    if self.pending_clicks >= 2:
                        self.pending_clicks = 0
                        self.last_release = None
                        return "double"

        # Basılı tutulurken uzun basış kontrolü
        if self.stable and self.press_start is not None:
            held = _ticks_diff(now_ms, self.press_start)
            if not self.factory_fired and held >= self.factory_ms:
                self.factory_fired = True
                self.long_fired = True
                self.pending_clicks = 0
                self.last_release = None
                return "factory"
            if not self.long_fired and held >= self.long_ms:
                self.long_fired = True
                self.pending_clicks = 0
                self.last_release = None
                return "long"

        # İlk kısa basıştan sonra çift basış penceresi dolduysa tek tık yayınla
        if self.pending_clicks == 1 and not self.stable and self.last_release is not None:
            if _ticks_diff(now_ms, self.last_release) >= self.dbl_ms:
                self.pending_clicks = 0
                self.last_release = None
                return "click"

        return None

    def waiting(self):
        # Aktif basış veya bekleyen çift tık penceresi varsa hızlı tarama gerekir
        return self.stable or self.raw != self.stable or self.pending_clicks > 0


class Button:
    # MicroPython donanım sarmalayıcısı (active-low, internal pull-up: pin <-> GND).
    def __init__(self, pin_num, **tracker_kw):
        self.pin_num = pin_num
        self.pin = None
        self.tracker = ButtonTracker(**tracker_kw)
        self._irq_flag = False
        if pin_num is not None:
            import machine
            self.pin = machine.Pin(pin_num, machine.Pin.IN, machine.Pin.PULL_UP)
            self.pin.irq(
                trigger=machine.Pin.IRQ_FALLING | machine.Pin.IRQ_RISING,
                handler=self._on_edge,
            )

    def _on_edge(self, _pin):
        # IRQ içinde bellek ayırma yok
        self._irq_flag = True

    def is_pressed(self):
        if self.pin is None:
            return False
        return self.pin.value() == 0

    def has_activity(self):
        return self._irq_flag or self.tracker.waiting() or self.is_pressed()

    def poll(self):
        if self.pin is None:
            return None
        self._irq_flag = False
        return self.tracker.update(self.is_pressed(), _ticks_ms())
