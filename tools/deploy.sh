#!/bin/sh
# Tüm firmware dosyalarını USB'ye takılı Pico W'ya kopyalar (mpremote gerekir: pip install mpremote)
# Kullanım: sh tools/deploy.sh            (otomatik port)
#           sh tools/deploy.sh /dev/tty.usbmodem1101
set -e
cd "$(dirname "$0")/.."
MP=${MPREMOTE:-$([ -x .venv/bin/mpremote ] && echo .venv/bin/mpremote || echo mpremote)}
PORT=${1:+connect $1}
$MP $PORT mkdir :fonts 2>/dev/null || true
$MP $PORT cp \
    firmware/i18n.py firmware/config_store.py firmware/timeutil.py firmware/logic.py \
    firmware/wifi.py firmware/transit.py firmware/weather.py firmware/battery.py \
    firmware/button.py firmware/qr.py firmware/portal.py firmware/portal.html \
    firmware/display.py firmware/epd_2in13.py :
if [ -f firmware/config.py ]; then
    $MP $PORT cp firmware/config.py :
elif [ -f config.py ]; then
    $MP $PORT cp config.py :
fi
$MP $PORT cp firmware/fonts/big.bin firmware/fonts/mid.bin firmware/fonts/small.bin :fonts/
# main.py en son: kopyalama yarıda kalırsa eksik kodla açılmasın
$MP $PORT cp firmware/main.py :
echo "Tamam. Yeniden başlatıp logları izlemek için: $MP $PORT reset && $MP $PORT repl"
