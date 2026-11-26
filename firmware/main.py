# showerboard: duşakabin için Berlin toplu taşıma + saat ekranı (Pico W + e-Paper 2.13)
#
# Durumlar:
#   KURULUM : WPA2 şifreli geçici Wi-Fi AP + QR + captive portal web ayar sayfası.
#   AKTİF   : aktif saatlerde (veya uyku kapalıyken 7/24) ekranı günceller,
#             butona basılınca doğrudan kurulum portalını açar.
#   UYKU    : ekrana uyku + uyanış saatini yazar, Wi-Fi'ı kapatır, deepsleep.
#   HATA    : beklenmeyen hatada ekrana yazar ve kısa süre sonra yeniden başlar.
# Watchdog sadece aktif durumda çalışır (rp2'de watchdog durdurulamaz ve
# deepsleep/kurulum sırasında sorun çıkarır). Mod değişimlerinde temiz reset atılır.

import time
import gc
import sys
import json
import machine

import config_store
import i18n
import timeutil
import logic
import wifi
import transit
import weather
from button import Button
from epd_2in13 import EPD
from display import Screen

# Sadece USB bağlıyken (veya pil okunamazsa) geliştirici Ctrl-C beklemesi yap;
# pilde derin uykudan uyanırken gereksiz bekleme yapılmasın.
_usb_boot = True
try:
    import battery as _batt_boot
    _usb_boot = _batt_boot.read().get("usb", True)
except Exception:
    pass
if _usb_boot:
    print("showerboard başlıyor; durdurmak için 2.5 sn içinde Ctrl-C")
    time.sleep_ms(2500)

gc.collect()

STATE_FILE = "state.json"
LOG_FILE = "log.txt"       # kalıcı olay kaydı (gece ne olduğunu sabah okumak için)
LOG_MAX = 8000             # aşınca log.old'a taşınır
MAX_SLEEP_S = 1800         # tek derin uyku dilimi (µs olarak 2^31'in altında kalsın)
FETCH_LEAD_S = 20          # dakika başından bu kadar önce veri çek
WDT_MS = 8000              # rp2 en fazla ~8.3 sn
BATTERY_EVERY_S = 300
WAKE_LEAD_S = 90           # aktif saatten bu kadar önce uyan (NTP + ilk veri)
MAX_DISPLAY_RESETS = 3     # ekran yanıt vermezse art arda en fazla bu kadar Pico reseti
MAX_OOM_STREAK = 3         # art arda bu kadar bellek hatasında temiz reset (7/24 kurtarma)
CHECKS = ("ekran", "pil", "wifi", "saat", "bvg", "hava")

# Kart üstü LED: (yanık ms, periyot ms). LED Wi-Fi çipine bağlı, kısılamaz;
# "sönük" görünüm için çok kısa yakılır.
LED_PATTERNS = {
    "ok": (15, 5000),        # her şey yolunda: 5 sn'de bir kısa nabız
    "nowifi": (150, 3000),   # çalışıyor ama Wi-Fi'ya bağlanamıyor
    "error": (250, 500),     # ekran yanıt vermiyor / hata: sürekli yanıp sönme
}


def _is_oom(e):
    # MicroPython: MemoryError veya mbedTLS OSError(12) [ENOMEM]
    if isinstance(e, MemoryError):
        return True
    return isinstance(e, OSError) and bool(e.args) and e.args[0] == 12


def log(*args):
    t = timeutil.hhmm(timeutil.now()) if timeutil.clock_valid() else "--:--"
    print("[%s]" % t, *args)


def event(*args):
    # log + flash'taki log.txt'ye ekle (önemli olaylar için; her dakika değil)
    log(*args)
    try:
        if timeutil.clock_valid():
            t = timeutil.berlin(timeutil.now())
            stamp = "%02d.%02d %02d:%02d" % (t[2], t[1], t[3], t[4])
        else:
            stamp = "--.-- --:--"
        try:
            import os
            if os.stat(LOG_FILE)[6] > LOG_MAX:
                os.rename(LOG_FILE, "log.old")
        except OSError:
            pass
        with open(LOG_FILE, "a") as f:
            f.write(stamp + " " + " ".join(str(a) for a in args) + "\n")
    except Exception:
        pass


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_state(st):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)
    except OSError as e:
        log("state yazılamadı:", e)


class Led:
    # Pin("LED") Wi-Fi çipini başlatır; uyku yolunda çip kapalı kalsın diye
    # pin ilk yanıp sönmede (sadece aktif modda) oluşturulur.
    def __init__(self):
        self.pin = None
        self.failed = False
        self.mode = "ok"
        self.next = time.ticks_ms()

    def _ensure(self):
        if self.pin is None and not self.failed:
            try:
                self.pin = machine.Pin("LED", machine.Pin.OUT)
            except Exception:
                self.failed = True

    def pulse(self, ms=40):
        # Buton geri bildirimi için kısa yanıp sönme
        self._ensure()
        if self.pin is not None:
            self.pin.value(1)
            time.sleep_ms(ms)
            self.pin.value(0)

    def tick(self):
        self._ensure()
        if self.pin is None:
            return 4000
        on, period = LED_PATTERNS[self.mode]
        if time.ticks_diff(time.ticks_ms(), self.next) >= 0:
            self.pin.value(1)
            time.sleep_ms(on)
            self.pin.value(0)
            self.next = time.ticks_add(time.ticks_ms(), period - on)
        return max(0, time.ticks_diff(self.next, time.ticks_ms()))

    def blink_for(self, seconds):
        self.mode = "error"
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < seconds * 1000:
            time.sleep_ms(self.tick())


class App:
    def __init__(self):
        self.cfg = config_store.load()
        self.lang = i18n.norm(self.cfg.get("LANG"))
        self.wdt = None
        self.led = Led()
        self.btn = Button(self.cfg.get("BUTTON_PIN", 15))
        self.check = dict((k, None) for k in CHECKS)   # None: henüz denenmedi
        self.wifi_fail = False
        try:
            self.epd = EPD(self.cfg.get("EPD_VERSION", "V4B"), feed=self.feed)
            self.check["ekran"] = self.epd.pins_ok()
            if not self.check["ekran"]:
                event("ekran pinleri GPIO modunda değil (SPI çakışması)")
        except OSError as e:
            event("ekran başlatılamadı:", e)
            self.epd = None
            self.check["ekran"] = False
        self.screen = Screen(
            self.epd,
            self.cfg.get("ROTATION", 0),
            self.cfg.get("EPD_Y_OFFSET", 6),
            self.cfg.get("FULL_REFRESH_EVERY", 10),
            lang=self.lang,
        )
        self.deps = []
        self.rt = None
        self.fetch_ok = False
        self.data_time = None
        self.transit_try = None
        self.transit_detail = None
        self.weather = None
        self.weather_try = None
        self.batt = None
        self.batt_time = None
        self.stop_error = None
        self.oom_streak = 0
        self.state = load_state()
        self.ntp_time = (self.state or {}).get("ntp_time")
        self.stop_verified = (
            bool(self.state)
            and bool(self.cfg.get("STOP_ID"))
            and self.state.get("stop_ok") == self.cfg["STOP_ID"]
        )

    def _t(self, key):
        return i18n.t(self.lang, key)

    def feed(self):
        if self.wdt is not None:
            self.wdt.feed()

    # ---------------- yardımcılar ----------------
    def read_battery(self, force=False):
        if not self.cfg.get("BATTERY", True) or wifi.is_on():
            return
        now = time.time()
        if not force and self.batt_time is not None and now - self.batt_time < BATTERY_EVERY_S:
            return
        try:
            import battery
            self.batt = battery.read(self.cfg.get("VSYS_DIODE_DROP_V", 0.0))
            self.batt_time = now
            self.check["pil"] = True
            log("pil: %.2f V" % self.batt["v"], self.batt)
        except Exception as e:
            self.check["pil"] = False
            log("pil okunamadı:", repr(e))

    def enter_setup(self, mode="setup"):
        event("kurulum moduna geçiliyor:", mode)
        self.save(mode=mode)
        wifi.off()
        machine.reset()

    def _handle_button_event(self, ev):
        # Tek buton akışı: kısa/uzun basış -> QR web ayarları; 9 sn -> fabrika sıfırlama.
        if ev == "factory":
            self.led.pulse(200)
            event("fabrika sıfırlama (buton)")
            config_store.reset()
            self.enter_setup("setup")
        elif ev in ("click", "double", "long"):
            self.led.pulse(60)
            self.enter_setup("setup")

    def sleep_until(self, t):
        # t: UTC epoch. Watchdog, LED ve butonu izleyerek bekler.
        while True:
            self.feed()
            ev = self.btn.poll()
            if ev:
                self._handle_button_event(ev)
            if timeutil.now() >= t:
                return
            step = 25 if self.btn.has_activity() else 150
            ms = min(step, self.led.tick())
            dt_ms = (t - timeutil.now()) * 1000
            if dt_ms <= 0:
                return
            ms = min(ms, dt_ms)
            if ms > 0:
                time.sleep_ms(ms)

    # ---------------- öz kontrol ----------------
    def update_led(self):
        if not self.check["ekran"] or self.screen.fail_streak:
            self.led.mode = "error"
        elif self.wifi_fail:
            self.led.mode = "nowifi"
        else:
            self.led.mode = "ok"

    def report_check(self):
        names = {True: "OK", False: "HATA", None: "-"}
        event("KONTROL:", " ".join("%s=%s" % (k, names[self.check[k]]) for k in CHECKS))
        self.save(check=dict(self.check))
        self.update_led()

    def display_failed(self):
        n = (self.state or {}).get("disp_resets") or 0
        if n < MAX_DISPLAY_RESETS:
            event("ekran yanıt vermiyor; Pico yeniden başlatılıyor (%d/%d)" % (n + 1, MAX_DISPLAY_RESETS))
            self.save(disp_resets=n + 1)
            wifi.off()
            self.led.blink_for(3)
            machine.reset()
        event("ekran yanıt vermiyor; %d reset denendi, ekransız devam" % n)
        self.update_led()

    def message(self, title, detail=None):
        now = timeutil.now() if timeutil.clock_valid() else None
        self.screen.render_message(now, title, detail, self.batt)
        self.screen.show()

    def save(self, **kw):
        st = self.state or {}
        st.update(kw)
        st["stop_ok"] = self.cfg.get("STOP_ID") if self.stop_verified else None
        if self.ntp_time is not None:
            st["ntp_time"] = self.ntp_time
        self.state = st
        save_state(st)

    def deep_sleep(self, seconds):
        seconds = max(10, int(seconds))
        v = (self.batt or {}).get("v")
        event("uyku: %d sn" % seconds, "pil: %.3f V" % v if v else "")
        wifi.power_down()
        # Pico W: Wi-Fi çipi kapandıktan hemen sonra deepsleep anında uyanıyor
        time.sleep_ms(2500)
        self.screen.sleep()
        pin = self.cfg.get("BUTTON_PIN")
        if pin is not None:
            machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP).irq(
                trigger=machine.Pin.IRQ_FALLING, handler=lambda p: None)
        if self.cfg.get("NO_DEEPSLEEP", False):
            t0 = time.time()
            while time.time() - t0 < seconds:
                if self.btn.poll() in ("click", "double", "long", "factory"):
                    break
                time.sleep_ms(100)
            machine.reset()
        machine.deepsleep(seconds * 1000)
        machine.reset()

    def wait_with_button(self, seconds):
        # Wi-Fi/NTP hatasında beklerken butona basılırsa hemen kuruluma geç
        t0 = time.time()
        while time.time() - t0 < seconds:
            ev = self.btn.poll()
            if ev:
                self._handle_button_event(ev)
            time.sleep_ms(50)

    # ---------------- veri ----------------
    def refresh_seconds(self):
        return max(60, int(self.cfg.get("REFRESH_MIN", 3)) * 60)

    def transit_due(self, at):
        if self.transit_try is None:
            return True
        if not self.fetch_ok:
            return at - self.transit_try >= 55     # hata sonrası her dakika dene
        rs = self.refresh_seconds()
        interval = rs if rs >= 120 else self.cfg.get("TRANSIT_REFRESH_S", 120)
        return at - self.transit_try >= interval - 5

    def weather_due(self, at):
        return self.weather_try is None or at - self.weather_try >= self.cfg.get("WEATHER_REFRESH_S", 900) - 5

    def ntp_due(self, at):
        return self.ntp_time is None or at - self.ntp_time >= self.cfg.get("NTP_REFRESH_S", 3600)

    def fetch(self, at):
        t_due, w_due, n_due = self.transit_due(at), self.weather_due(at), self.ntp_due(at)
        if not (t_due or w_due or n_due):
            return
        now = timeutil.now()
        if t_due:
            self.transit_try = now
        if w_due:
            self.weather_try = now
        if not wifi.connect_retry(self.cfg["WIFI_SSID"], self.cfg.get("WIFI_PASSWORD", "")):
            event("WiFi bağlanamadı")
            self.wifi_fail = True
            self.update_led()
            if t_due:
                self.set_transit_fail(self._t("nowifi_detail"))
            return
        self.wifi_fail = False
        self.check["wifi"] = True
        try:
            if n_due:
                if timeutil.sync_ntp(self.cfg.get("NTP_HOST", "pool.ntp.org"), feed=self.feed):
                    self.ntp_time = timeutil.now()
                    self.check["saat"] = True
                    self.save(ntp_time=self.ntp_time)
                    log("NTP tamam")
                self.feed()
            if not self.stop_verified:
                self.verify_stop()
            if t_due:
                self.fetch_transit()
            if w_due:
                self.fetch_weather()
        finally:
            wifi.off()
            gc.collect()
        self.read_battery()

    def set_transit_fail(self, detail):
        # Eski sayıyı asla gösterme
        self.fetch_ok = False
        self.deps = []
        self.rt = None
        self.transit_detail = detail

    def verify_stop(self):
        try:
            ok, name = transit.verify_stop(self.cfg["STOP_ID"], self.cfg.get("STOP_NAME_HINT", ""))
        except Exception as e:
            log("durak doğrulanamadı (sonra tekrar):", repr(e))
            return
        if ok:
            log("durak doğrulandı:", self.cfg["STOP_ID"], name)
            self.stop_verified = True
            self.stop_error = None
            self.save()
        else:
            event("HATA: STOP_ID", self.cfg["STOP_ID"], "beklenen durak değil:", name)
            self.stop_error = (name or "?")[:30]

    def fetch_transit(self):
        try:
            deps, rt = transit.fetch_departures(self.cfg, timeutil.now())
            self.deps, self.rt = deps, rt
            self.data_time = timeutil.now()
            self.fetch_ok = True
            self.transit_detail = None
            self.oom_streak = 0
            self.check["bvg"] = True
            log("kalkış: %d adet, rt=%s" % (len(deps), rt))
            for d in deps:
                log("  ", d["line"], timeutil.hhmm(d["when"]), d["delay"], d["direction"])
        except Exception as e:
            self.check["bvg"] = False
            event("kalkış verisi alınamadı:", repr(e))
            self.set_transit_fail(self._t("nodata_detail"))
            if _is_oom(e):
                self.oom_streak += 1
                if self.oom_streak >= MAX_OOM_STREAK:
                    event("bellek sıkıştı; yeniden başlatılıyor")
                    wifi.off()
                    machine.reset()
            else:
                self.oom_streak = 0
        gc.collect()

    def fetch_weather(self):
        try:
            self.weather = weather.fetch(self.cfg["LAT"], self.cfg["LON"], timeutil.now())
            self.check["hava"] = True
            log("hava:", self.weather)
        except Exception as e:
            self.check["hava"] = False
            event("hava alınamadı:", repr(e))
        gc.collect()

    # ---------------- ekran ----------------
    def render(self, now, valid_until):
        if self.stop_error:
            self.screen.render_message(now, self._t("bad_stop_title"), self.stop_error, self.batt)
        else:
            rs = self.refresh_seconds()
            vcfg = dict(self.cfg)
            vcfg["MAX_DATA_AGE_S"] = max(self.cfg.get("MAX_DATA_AGE_S", 180), rs + 90)
            vcfg["MAX_REALTIME_AGE_S"] = max(self.cfg.get("MAX_REALTIME_AGE_S", 300), rs + 180)
            tv = logic.transit_view(now, valid_until, vcfg, self.deps, self.fetch_ok,
                                    self.data_time, self.rt)
            if tv["status"] == "nodata" and self.transit_detail:
                tv["detail"] = self.transit_detail
            w = None
            if self.weather is not None and now - self.weather["time"] <= 3 * self.cfg.get("WEATHER_REFRESH_S", 900):
                w = dict(self.weather)
                w["rain_min"] = self.cfg.get("RAIN_MIN_PCT", 20)
            show_dir = self.cfg.get("SHOW_DIRECTION", True) and not self.cfg.get("DIRECTIONS")
            self.screen.render_main(now, tv, w, self.batt, show_dir)
            if tv["status"] != "ok":
                log("ekran:", tv["status"], tv.get("detail", ""))
        t0 = time.ticks_ms()
        if self.screen.show():
            log("ekran güncellendi (%d ms)" % time.ticks_diff(time.ticks_ms(), t0))
        self.after_show()

    def after_show(self):
        if self.screen.fail_streak >= 2:
            self.display_failed()
        elif self.screen.fail_streak == 0 and (self.state or {}).get("disp_resets"):
            event("ekran tekrar çalışıyor")
            self.save(disp_resets=0)
        self.update_led()

    # ---------------- kurulum ----------------
    def run_portal(self, mode):
        import portal
        self.save(mode=None)
        if mode == "setup_lan":
            res = portal.run_lan(self.cfg, self.screen, self.btn, batt=self.batt)
        else:
            res = portal.run_ap(self.cfg, self.screen, self.btn, batt=self.batt)
        event("kurulum sonucu:", res)
        if res == "lan_fallback":
            self.save(mode="setup_lan")
        elif res == "reset":
            self.save(mode="setup")
        elif res == "saved":
            self.save(mode=None, screen=None, stop_ok=None)
        machine.reset()

    # ---------------- ana akış ----------------
    def run(self):
        if not self.check["ekran"]:
            self.display_failed()
        self.read_battery(force=True)

        # Açılışta buton 2.5 sn basılı tutulursa doğrudan kuruluma gir
        if self.btn.is_pressed():
            t0 = time.ticks_ms()
            while self.btn.is_pressed() and time.ticks_diff(time.ticks_ms(), t0) < 2500:
                time.sleep_ms(50)
            if self.btn.is_pressed():
                self.run_portal("setup")

        req_mode = (self.state or {}).get("mode")
        if req_mode in ("setup", "setup_lan"):
            self.run_portal(req_mode)

        if config_store.needs_setup(self.cfg):
            event("ilk kurulum gerekli -> AP/QR modu")
            self.run_portal("setup")

        # Saat geçersizse (soğuk açılış) NTP çek; derin uyku arası uyanışta
        # saat hala geçerliyse gece boşuna Wi-Fi açma.
        if not timeutil.clock_valid():
            self.check["wifi"] = wifi.connect_retry(self.cfg["WIFI_SSID"], self.cfg.get("WIFI_PASSWORD", ""))
            if not self.check["wifi"]:
                event("WiFi yok, 2 dk sonra tekrar")
                self.wifi_fail = True
                self.report_check()
                self.message(self._t("nowifi_title"), self._t("btn_setup_2m"))
                self.wait_with_button(120)
                machine.reset()
            ok = timeutil.sync_ntp(self.cfg.get("NTP_HOST", "pool.ntp.org"))
            self.check["saat"] = ok
            wifi.off()
            if not ok:
                self.report_check()
                event("NTP başarısız, 2 dk sonra tekrar")
                self.message(self._t("ntp_title"), self._t("btn_setup_2m"))
                self.wait_with_button(120)
                machine.reset()
            self.ntp_time = timeutil.now()
            self.save(ntp_time=self.ntp_time)
            self.read_battery(force=True)

        now = timeutil.now()
        event("saat (Berlin):", timeutil.hhmm(now), "UTC epoch", now)
        st = self.state
        active, bound = logic.schedule_status(now, self.cfg)
        end = bound if active else None

        if not active:
            manual_until = (st or {}).get("manual_until") or 0
            planned = (st or {}).get("planned_wake")
            if manual_until > now:
                active = True
                end = manual_until
            elif st is None or (planned and now < planned - 120):
                # İlk açılış ya da zamanından önce uyanma (buton / RESET)
                active = True
                end = now + self.cfg.get("MANUAL_WAKE_MIN", 30) * 60
                event("elle uyandırma: %d dk aktif" % self.cfg.get("MANUAL_WAKE_MIN", 30))
                self.save(manual_until=end, planned_wake=None)

        if not active:
            self.report_check()
            self.sleep_mode(now, bound)
        else:
            self.save(planned_wake=None, screen=None)
            self.active_mode(end)

    def sleep_mode(self, now, start):
        if start is not None and start - now <= 180:
            event("aktif saate az kaldı, bekleniyor")
            while timeutil.now() < start:
                if self.btn.poll() in ("click", "double", "long", "factory"):
                    break
                time.sleep_ms(200)
            machine.reset()
        pct = (self.batt or {}).get("pct")
        key = "%s/%s" % (start, None if pct is None else pct // 10)
        if (self.state or {}).get("screen") != key:
            self.screen.render_sleep(start, self.batt)
            self.screen.show(full=True)
        dur = MAX_SLEEP_S if start is None else min(start - WAKE_LEAD_S - now, MAX_SLEEP_S)
        self.save(screen=key, planned_wake=now + dur, manual_until=0)
        self.deep_sleep(dur)

    def active_mode(self, end):
        rs = self.refresh_seconds()
        event("aktif mod, bitiş:", timeutil.hhmm(end) if end is not None else "7/24",
              "yenileme: %d dk" % (rs // 60))
        self.wdt = machine.WDT(timeout=WDT_MS)
        wifi.feed = self.feed
        self.fetch(timeutil.now())
        self.report_check()
        last_slot = None
        while True:
            self.feed()
            now = timeutil.now()
            if end is not None and now >= end:
                event("aktif dönem bitti, yeniden başlatılıyor")
                machine.reset()

            slot = now // rs
            nb = (slot + 1) * rs
            if slot != last_slot or self.transit_try is None:
                if self.transit_try is None:
                    self.fetch(now)
                self.render(now, nb)
                last_slot = slot
                gc.collect()

            if self.transit_due(nb) or self.weather_due(nb) or self.ntp_due(nb):
                self.sleep_until(nb - FETCH_LEAD_S)
                self.fetch(nb)
            self.sleep_until(nb)


def main():
    app = None
    event("açılış, reset nedeni:", machine.reset_cause())
    try:
        app = App()
        app.run()
    except KeyboardInterrupt:
        wifi.off()
        raise
    except Exception as e:
        sys.print_exception(e)
        event("HATA:", repr(e))
        try:
            if app is not None:
                app.message(app._t("err_prefix") + type(e).__name__, app._t("restarting"))
        except Exception as e2:
            sys.print_exception(e2)
        if app is not None:
            app.led.blink_for(5)
        else:
            time.sleep(5)
        machine.reset()


main()
