# Contributing to Showerboard

Thank you for contributing to Showerboard!

## Development & Test Setup

No Pico W hardware is needed for core logic, portal, QR, button, or display layout changes:

```bash
python3 -m venv .venv
.venv/bin/pip install pillow mpremote
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python firmware/display.py   # regenerates preview/*.png
```

## Architecture & Invariants

- **Keep pure logic testable on CPython:** `logic.py`, `timeutil.py`, `button.py` (`ButtonTracker`), `qr.py`, `config_store.py`, and `portal.py` (`PortalApp`) must run cleanly under standard CPython 3.9+ without importing `machine` or `network` at top level.
- **Respect Pico W RAM limits:** MicroPython on RP2040 has tight heap headroom, especially around TLS sockets and simultaneous AP + STA mode. Keep JSON responses bounded (`max_bytes`), free temporary buffers promptly, and call `gc.collect()` around network calls.
- **Never overstate remaining time:** Countdown rounding in `logic.py` must remain conservative (floor-rounded until the next refresh slot) and stale/failed data must never display old countdown numbers.
- **Never commit personal data or secrets:** No real Wi-Fi credentials, home addresses, or private coordinates in code, configs, tests, or preview screenshots. Use neutral public examples (e.g. `Alexanderplatz`, `52.5200, 13.4050`).
- **Measured hardware dimensions only:** Any change to `hardware/enclosure/enclosure.py` must cite caliper measurements or datasheets — never guessed component dimensions.

## Adding Another City / Transit Provider

Today `transit.py` targets Berlin/Brandenburg (`v6.bvg.transport.rest` / `v6.vbb.transport.rest`) and `timeutil.py` implements Europe/Berlin `CET`/`CEST` DST rules. Contributions that introduce a clean provider abstraction (for example GTFS-RT, TfL, NYC MTA, or configurable IANA/POSIX DST rules) while keeping Pico W RAM usage low are very welcome — open an issue first to align on the config schema.

## Contributor License Agreement (CLA)

Showerboard is licensed under **GNU AGPL-3.0**. To keep the option of offering commercial products, pre-assembled hardware kits, or alternative licensing in the future, by submitting a pull request to this repository you agree that:

1. Your contribution is your original work and you have the legal right to submit it.
2. You license your contribution under **AGPL-3.0**, and you additionally grant the project maintainer (Mustafa Samed Kasal) a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use, modify, redistribute, and relicense your contribution under alternative open-source or commercial licenses.
