# Showerboard Setup Guide (AI Agents & Humans)

Single source of truth for flashing, configuring, testing, and troubleshooting Showerboard — whether an AI coding agent walks you through it or you run the commands yourself.

---

## AI Agent Setup Protocol

If a user asked you to set up Showerboard, **do not flash or write Wi-Fi credentials blindly.**

### Step 1 — Ask the user first (one short message)
Ask these 4 concise questions and wait for their answers:

1. **e-Paper panel revision:** Check the sticker on the back of the Waveshare Pico-ePaper-2.13 board — is it **`V3`**, **`V4`** (black/white), or **`V4B`** (3-color red/black/white with a red sticker near the FPC)?
2. **Power & button hardware:** Are you testing over USB first, or running on a LiPo battery + TP4056 + GP15 tactile button? *(See [hardware/README.md](hardware/README.md) for wiring.)*
3. **Configuration method:** Do you want to configure language, Wi-Fi, and transit stop on the device via **QR + phone captive portal** *(recommended — zero secrets on your laptop)*, or pre-populate a local `config.py`?
4. **3D enclosure:** Do you want to slice the ready-to-print STL files in `hardware/enclosure/exports/`, or modify the Build123d script?

### Step 2 — Deploy & verify
- **Never** commit `config.py`, `config.json`, or print Wi-Fi passwords into chat output.
- Run the CPython test suite first (`python3 -m unittest discover -s tests -t .`) and confirm all 78 tests pass.
- Flash/deploy using `sh tools/deploy.sh` and guide the user through either the on-screen QR portal or serial REPL verification.

---

## Manual Setup

### 1. Check your e-Paper panel revision

Look at the label on the back of the Waveshare Pico-ePaper-2.13 module:
- **`V3`** or **`V4`**: 2-color black/white panel (supports fast partial refresh every minute; full refresh every 10 partials to prevent ghosting).
- **`V4B`**: 3-color red/black/white `Pico-ePaper-2.13-B V4` (red sticker near the FPC ribbon). No partial refresh — each refresh takes ~17 seconds with a full flash; red channel is unused. Set `REFRESH_MIN` to `3` or `5` minutes (default `3`, matching Waveshare's 180 s minimum interval recommendation for panel longevity).

The display plugs directly onto the Pico W headers (no extra wires): `SPI1` (`GP10` SCK, `GP11` MOSI), `GP9` CS, `GP8` DC, `GP12` RST, `GP13` BUSY.

### 2. Flash MicroPython onto the Pico W

1. Download the latest stable **`.uf2`** for **Raspberry Pi Pico W** (MicroPython ≥ v1.22) from [micropython.org/download/RPI_PICO_W](https://micropython.org/download/RPI_PICO_W/).
2. Hold the **BOOTSEL** button on the Pico W, plug it into USB, then release BOOTSEL.
3. Drag the `.uf2` file onto the `RPI-RP2` USB drive. The Pico reboots automatically into MicroPython.

### 3. Install host tools & deploy firmware

```bash
pip install mpremote          # required to copy files to the Pico W
pip install pillow            # optional: only for desktop PNG previews
```

Connect the Pico W over USB and run:

```bash
sh tools/deploy.sh                           # auto-detects the serial port
# or specify explicitly:
sh tools/deploy.sh /dev/tty.usbmodem1101
```

`tools/deploy.sh` copies all modules from `firmware/` (including `i18n.py`, `portal.html`, and `fonts/*.bin`) to the Pico W root, copying `main.py` last so a partial upload never leaves a broken boot. If a local `firmware/config.py` (or root `config.py`) exists, it is copied too.

> **Using Thonny instead?** Select *Tools → Options → Interpreter → MicroPython (Raspberry Pi Pico)* and save everything inside `firmware/` (all `.py` files, `portal.html`, and the `fonts/` folder) onto the Pico W root directory.

Reboot and watch serial logs:

```bash
mpremote reset && mpremote repl
```

### 4. Configure on-device (QR + Captive Portal)

When no valid configuration exists — or anytime you **press the side button** (or hold it **2.5 s during boot**) — Showerboard opens its local setup portal:

1. The e-Paper displays a **WPA2 Wi-Fi QR code** (`ShowerBoard-XXXX`), the ephemeral per-session password (`PW: XXXXXXXX`), and IP `192.168.4.1`.
2. Scan the QR code with your phone to join the encrypted temporary access point.
3. The captive portal opens automatically (if not, browse to `http://192.168.4.1/`).
4. Pick your language (**`EN` / `DE` / `TR`**) at the top right — it switches the web page immediately and persists to the e-Paper display when saved.
5. Fill in:
   - **1. Wi-Fi (2.4 GHz):** scan networks, enter password, tap **Connect & Test Wi-Fi** (Pico W supports 2.4 GHz only).
   - **2. Address & Transit (Berlin):** enter your Berlin address → tap **Find** → pick transport modes (S-Bahn / U-Bahn / Bus / Tram) and nearest stop → adjust walking minutes and prep minutes, plus optional direction filters and priority direct lines.
   - **3. Sleep Schedule:** enable/disable overnight sleep, set sleep start & wake time (Berlin time, midnight wrap supported), active weekdays, and manual wake duration.
   - **4. Display:** choose orientation (`0°` / `180°`), panel revision (`V4B` / `V4` / `V3`), and refresh interval (`1` / `2` / `3` / `5` min).
6. Tap **Save & Start** (or press the side button again to close without saving). Settings are written atomically to `config.json` and the Pico returns to normal operation.

> **Automatic LAN fallback:** Simultaneous AP + TLS HTTPS requests can occasionally hit MicroPython's RAM limit on Pico W. If that happens during address/stop search, Showerboard automatically reboots into **LAN setup mode** on your home Wi-Fi and shows a new QR code pointing directly to its local IP.

> **Security model notes:** The setup AP uses a fresh random 8-character WPA2 password per session, so your home Wi-Fi password never crosses an open Wi-Fi link. Local portal API endpoints enforce `Host` matching (blocks DNS rebinding), `Origin` + `X-Requested-With` checks on `POST` (blocks browser CSRF), strict input validation, and CSP/frame headers. Note that outbound `https://` requests on Pico W use MicroPython's default `ssl.wrap_socket` without an embedded CA root bundle due to RP2040 flash/RAM limits.

### 5. Optional: Headless `config.py` setup

If you prefer editing a file before deploying (note: `config.json` written by the portal overrides `config.py`):

```bash
cp firmware/config.example.py firmware/config.py
```

Look up any Berlin/Brandenburg stop ID and direction names from your computer:

```bash
python3 tools/find_stop.py "Alexanderplatz"
python3 tools/find_stop.py --departures 900100003
```

Key fields in `config.py`:
- `LANG`: `"en"`, `"tr"`, or `"de"`.
- `WIFI_SSID`, `WIFI_PASSWORD` (2.4 GHz only; `config.py` is gitignored).
- `STOP_ID`, `STOP_NAME_HINT`, `PRODUCTS`, `DIRECTIONS`, `DIRECT_LINES`.
- `YURUME_DK` (required walking time in minutes) and `HAZIRLIK_DK` (prep time, default `5`).
- `EPD_VERSION` (`"V3"`, `"V4"`, or `"V4B"`).
- `NO_DEEPSLEEP = True` while bench-testing over USB so the serial port stays attached during sleep hours.
- Keep `LOW_POWER = False` on Pico W (`lightsleep` after CYW43 Wi-Fi activity can hang or return early on rp2; overnight `deepsleep` still runs normally).

---

## Desktop Preview & Tests

Render sample screens (`EN` and `TR`) to `preview/*.png` without a Pico W:

```bash
python3 firmware/display.py
```

Run the full CPython unit test suite (Python 3.9+, zero external dependencies):

```bash
python3 -m unittest discover -s tests -t .
```

Covers: Berlin CET/CEST DST transitions (2024–2027 hourly against `zoneinfo`), ISO 8601 offsets, delayed/cancelled trips, direction & direct-line selection, floor-rounded countdown guarantees, stale/missing data states, sleep schedules, instant single-button state machine, QR encoding, `EN`/`DE`/`TR` glyph coverage against `fonts/*.bin`, atomic `config_store`, portal CSRF/DNS-rebinding/input-validation hardening, and display BUSY recovery.

---

## Screen Reading Reference

| Shown on screen (`EN` / `TR` / `DE`) | Meaning |
| --- | --- |
| `S5 07:49 +2 … 5 m` / `5 dk` | S5 departs at 07:49 (includes +2 min live delay). Leave within **5 min**. |
| Inverted black row, `GO!` / `ÇIK!` / `LOS!` | Less than 2 minutes left before you must leave (or prep time exhausted, still walkable). |
| `LATE` / `GEÇ` / `SPÄT` | Missed (less than `YURUME_DK` before departure), not yet departed. Next catchable train appears below. |
| `XFR` / `AKT.` / `UMST` | Non-direct / transfer line (not in `DIRECT_LINES`). |
| `SCH` / `PLAN` | No real-time telemetry; scheduled time only. |
| `No data` / `Veri yok` / `Keine Daten` | BVG and VBB servers both unreachable. Stale numbers are never displayed. |
| `No Wi-Fi` / `Bağlantı yok` / `Kein WLAN` | Could not join 2.4 GHz Wi-Fi. Press the button to jump straight to Setup. |
| `Stale data` / `Veri eski` / `Alte Daten` | Last successful fetch is older than `MAX_DATA_AGE_S` (or feed realtime stamp stale). |
| `Sleep` / `Uyku` / `Ruhe` | Outside active schedule. Clock hidden while sleeping; shows next wake time and battery. |

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `No Wi-Fi` / `Bağlantı yok` | Verify SSID/password and ensure the network is **2.4 GHz** (Pico W has no 5 GHz radio). Press the button to jump straight to Setup. |
| `Clock error` / `Saat alınamadı` | NTP (UDP port 123) blocked or unreachable. Change `NTP_HOST` in `config.py`. |
| `Invalid stop` / `Durak ID hatalı` | `STOP_ID` did not match `STOP_NAME_HINT`. Re-pick the stop in the portal or check with `tools/find_stop.py`. |
| Screen never updates | Wrong `EPD_VERSION` — switch between `"V3"`, `"V4"`, and `"V4B"`. |
| Red/grainy artifacts or `BUSY zaman aşımı` | You have the 3-color B panel — set `EPD_VERSION = "V4B"`. |
| Image shifted or clipped vertically | Try `EPD_Y_OFFSET = 0` (default is `6` for the 128→122 px framebuffer mapping). |
| Upside-down display | Change **Display → Orientation** to `180°` in the portal (or `ROTATION = 180` in `config.py`). |
| Check what happened overnight | Read persistent flash logs: `mpremote cat :log.txt` (rotated log is `:log.old`). |
| On-board LED patterns | Brief pulse every 5 s = OK; every 3 s = no Wi-Fi; rapid blink = display error / recovery. |
| Can't connect over USB (device asleep) | Unplug and replug USB, then run `deploy.sh` or `mpremote` within the **2.5 s** USB boot window. |
| `MemoryError` during transit fetch | Lower `TRANSIT_RESULTS` (e.g. `6`). |
| Unhandled crash | Error type is written to the e-Paper and the Pico reboots after 5 s. Active mode also runs an 8 s hardware watchdog. |
