#!/usr/bin/env python3
"""PoC01 - Definition de la zone d'etude : unique source de verite.

Lit ../zone.env (point central WGS84 + rayon du disque en metres), convertit
le point en Lambert-93 via gdaltransform (gdal-bin, deja requis) et en deduit
la liste des dalles 1 km^2 du carroyage national couvrant le disque.

Convention de carroyage (voir README) : le nom d'une dalle encode son coin
NW - ouest X*1000, nord Y*1000 ; la dalle (X, Y) couvre
[X*1000, (X+1)*1000] x [(Y-1)*1000, Y*1000].

Critere d'inclusion (identique a l'ancien controle de couverture de
check.py) : une dalle est requise des que le disque de rayon R touche son
emprise, i.e. la distance centre->emprise la plus proche est <= R.

Usage:
  python3 scripts/zone.py l93       # "E N" du point central
  python3 scripts/zone.py rayon     # rayon en metres
  python3 scripts/zone.py dalles    # liste des dalles "XXXX_YYYY", une par ligne

En module : from zone import zone ; zone.dalles, zone.point_l93, zone.rayon
"""

import os
import subprocess
import sys
from pathlib import Path

POC = Path(__file__).resolve().parent.parent
ENV = POC / "zone.env"


def _lit_env():
    vals = {}
    for ligne in ENV.read_text().splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        cle, _, val = ligne.partition("=")
        vals[cle.strip()] = val.strip()
    try:
        return float(vals["LAT"]), float(vals["LON"]), float(vals["RAYON_M"])
    except (KeyError, ValueError) as e:
        raise SystemExit(f"zone.env illisible ({ENV}): {e}")


def _wgs84_vers_l93(lat, lon):
    try:
        r = subprocess.run(["gdaltransform", "-s_srs", "EPSG:4326", "-t_srs", "EPSG:2154"],
                           input=f"{lon} {lat}\n", capture_output=True, text=True, check=True)
        try:
            x, y = r.stdout.split()[0:2]
            return float(x), float(y)
        except (IndexError, ValueError):
            raise RuntimeError(f"gdaltransform illisible: {r.stdout!r} / {r.stderr!r}")
    except FileNotFoundError:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
        return t.transform(lon, lat)


def dalles_disque(cx, cy, rayon):
    """Dalles 1 km^2 dont l'emprise touche le disque (cx, cy, rayon)."""
    attendues = set()
    for X in range(int(cx // 1000) - int(rayon // 1000) - 1, int(cx // 1000) + int(rayon // 1000) + 2):
        for Y in range(int(cy // 1000) - int(rayon // 1000) - 1, int(cy // 1000) + int(rayon // 1000) + 3):
            px = min(max(cx, X * 1000), (X + 1) * 1000)
            py = min(max(cy, (Y - 1) * 1000), Y * 1000)
            if (px - cx) ** 2 + (py - cy) ** 2 <= rayon ** 2:
                attendues.add("%04d_%04d" % (X, Y))
    return sorted(attendues)


class zone:
    pass


lat, lon, _rayon = _lit_env()
zone.lat, zone.lon = lat, lon
zone.rayon = _rayon
zone.point_l93 = _wgs84_vers_l93(lat, lon)
zone.dalles = dalles_disque(*zone.point_l93, zone.rayon)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dalles"
    if cmd == "l93":
        print("%.2f %.2f" % zone.point_l93)
    elif cmd == "rayon":
        print(int(zone.rayon))
    elif cmd == "dalles":
        for d in zone.dalles:
            print(d)
    else:
        raise SystemExit(f"usage: zone.py [l93|rayon|dalles] (arg inconnu: {cmd})")
