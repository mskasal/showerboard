# AGENTS.md — Showerboard

Cross-agent repository instructions (Claude Code, Antigravity, Gemini CLI, OpenAI Codex, Cursor).

- **Flashing / setting up Showerboard:** Follow `SETUP.md` — ask the user for their e-Paper panel revision (`V3` / `V4` / `V4B`), power setup, and configuration preference before flashing or writing configs.
- **Hardware & 3D enclosure:** See `hardware/README.md` and `hardware/enclosure/enclosure.py` (designed with Forge / Build123d). Never guess real-component dimensions; cite caliper measurements or datasheets.

## Architecture
- **`firmware/`:** MicroPython (≥ v1.22) deployed to the Raspberry Pi Pico W root (`tools/deploy.sh`).
  - `main.py`: state machine (Setup / Active / Sleep / Error), 8 s watchdog (active mode only), persistent `log.txt`, LED status pulses, instant single-button toggle to Setup.
  - `i18n.py`: on-device `EN` / `DE` / `TR` translations (verified against `firmware/fonts/mid.bin` & `small.bin` glyphs).
  - `config_store.py`: layered config (`DEFAULTS` → optional `config.py` → atomic `config.json`).
  - `portal.py` + `portal.html` + `qr.py`: ephemeral WPA2 Wi-Fi AP + DNS captive portal (`192.168.4.1`) with live `EN`/`DE`/`TR` switcher, CSRF & Host validation, and automatic LAN fallback on `MemoryError`.
  - `button.py`: single-button state machine (`GP15` ↔ `GND`: instant click toggles Setup Portal, 9 s factory reset).
  - `logic.py` + `timeutil.py`: pure-Python Berlin DST, conservative leave-by countdowns, line priority, sleep schedule.
  - `transit.py` + `weather.py` + `wifi.py` + `battery.py`: BVG/VBB `transport.rest` (validated/encoded stop IDs), Open-Meteo, CYW43 Wi-Fi lifecycle (`power_down()` before deep sleep), VSYS `ADC3` battery sensing.
  - `display.py` + `epd_2in13.py`: 250×122 layout + desktop PNG preview + unified Waveshare V3/V4/V4B driver with BUSY recovery.
  - `fonts/*.bin`: bitmap fonts (JetBrains Mono, SIL OFL 1.1).
- **`hardware/enclosure/`:** Parametric Build123d CAD (`enclosure.py`), fit test coupons (`test_coupons/`), and ready-to-print exports (`exports/*.stl`, `exports/*.step`).
- **`tools/`:** `deploy.sh` (`mpremote` uploader), `find_stop.py`, `make_fonts.py`, `framebuf_pc.py`.
- **`tests/`:** CPython `unittest` suite (78 tests).

## Non-negotiable rules
1. **Never commit secrets or personal data** (`config.py`, `config.json`, Wi-Fi passwords, home street addresses, or private coordinates).
2. **Never weaken countdown conservatism** in `firmware/logic.py` (floor rounding, skipping cancelled trains, hiding stale data).
3. **Never weaken portal security** in `firmware/portal.py` (ephemeral WPA2 AP password, `Host` check, `Origin` + `X-Requested-With` CSRF guard on `POST`, `STOP_ID` validation, `BUTTON_PIN` excluded from `USER_KEYS`).
4. **Keep `firmware/i18n.py` strings within the glyphs present in `firmware/fonts/*.bin`** (verified by `tests/test_i18n.py`).
5. **Keep `firmware/epd_2in13.py` Waveshare license header and `firmware/fonts/*.bin` OFL attribution intact.**
6. **Run verification before committing:**
   - `python3 -m unittest discover -s tests -t .`
   - `python3 firmware/display.py` (when changing `display.py`, `i18n.py`, `qr.py`, or `logic.py`)
