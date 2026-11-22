#!/usr/bin/env python3
# Durak adıyla BVG/VBB durak ID'si (STOP_ID) bulur. Bilgisayarda çalışır,
# sadece Python standart kütüphanesi gerekir.
#
#   python3 tools/find_stop.py "Alexanderplatz"
#   python3 tools/find_stop.py --departures 900100003      # yön adlarını görmek için

import json
import sys
import urllib.parse
import urllib.request

HOSTS = ("https://v6.bvg.transport.rest", "https://v6.vbb.transport.rest")


def get(path):
    err = None
    for host in HOSTS:
        try:
            req = urllib.request.Request(host + path, headers={"User-Agent": "showerboard-setup"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r)
        except Exception as e:
            print("(%s: %s)" % (host, e), file=sys.stderr)
            err = e
    raise SystemExit("Sunuculara ulaşılamadı: %s" % err)


def find(query):
    q = urllib.parse.urlencode({"query": query, "results": 10, "addresses": "false", "poi": "false"})
    for loc in get("/locations?" + q):
        if loc.get("type") not in ("stop", "station"):
            continue
        prods = [k for k, v in (loc.get("products") or {}).items() if v]
        print("%-12s %-40s %s" % (loc["id"], loc.get("name", ""), ",".join(prods)))


def departures(stop_id):
    q = "duration=30&results=20&remarks=false&suburban=true&subway=false&tram=false&bus=false&ferry=false&express=false&regional=false"
    data = get("/stops/%s/departures?%s" % (stop_id, q))
    deps = data["departures"] if isinstance(data, dict) else data
    for d in deps:
        when = (d.get("when") or d.get("plannedWhen") or "")[11:16]
        delay = d.get("delay")
        flag = " İPTAL" if d.get("cancelled") else ("" if not delay else " +%d" % (delay // 60))
        print("%-4s %s%-6s -> %s" % (d["line"]["name"], when, flag, d.get("direction")))


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__ or "kullanım: find_stop.py <durak adı> | --departures <ID>")
    if args[0] == "--departures":
        departures(args[1])
    else:
        find(" ".join(args))


if __name__ == "__main__":
    main()
