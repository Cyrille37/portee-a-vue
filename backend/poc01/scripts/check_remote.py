#!/usr/bin/env python3
"""PoC01 - Croisement des tuiles avec l'API altimétrie IGN (vérité terrain).

Usage: make check-remote  (nécessite le réseau)

Pour un échantillon de points aléatoires dans la zone (reproductible :
graine fixe), compare la valeur du VRT 2 m max-poolé avec l'altimétrie
API (LiDAR HD 50 cm). Tolérance large : le max-pooling 2 m surestime
les Z en zone de pente/bâti ; on compare MNT (sol) qui est peu sensible.
"""
import json
import random
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from zone import zone

EUROPE_L93 = zone.point_l93
R = int(zone.rayon * 0.9)  # marge : rester dans le disque couvert
NB_POINTS = 10
TOLERANCE_M = 5.0

# L93 -> WGS84 pour l'API, via gdaltransform (gdal-bin, déjà requis)
def l93_to_wgs84(x, y):
    r = subprocess.run(["gdaltransform", "-s_srs", "EPSG:2154", "-t_srs", "EPSG:4326"],
                       input=f"{x} {y}\n", capture_output=True, text=True, check=True)
    try:
        lon, lat = r.stdout.split()[0:2]
        return float(lon), float(lat)
    except (IndexError, ValueError):
        raise RuntimeError(f"gdaltransform illisible: {r.stdout!r} / {r.stderr!r}")


def vrt_z(vrt, x, y):
    r = subprocess.run(["gdallocationinfo", "-geoloc", str(vrt), str(x), str(y)],
                       capture_output=True, text=True, check=True)
    try:
        return float(next(l.split(":")[1] for l in r.stdout.splitlines()
                          if l.strip().startswith("Value:")))
    except StopIteration:
        return None


def api_z(lon, lat):
    url = ("https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json"
           f"?lon={lon}&lat={lat}&resource=ign_lidar_hd_mnt_mono_wld")
    req = urllib.request.Request(url, headers={"User-Agent": "portee-a-vue-poc01"})
    with urllib.request.urlopen(req, timeout=30) as f:
        j = json.load(f)
    return j["elevations"][0]["z"]


def main():
    vrt = DATA / "mnt.vrt"
    if not vrt.exists():
        print("mnt.vrt absent: lancer make vrt", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(42)
    print(f"  {'L93 x':>10} {'L93 y':>11} {'z VRT':>8} {'z API':>8} {'écart':>7}")
    ecarts = []
    for _ in range(NB_POINTS):
        x = EUROPE_L93[0] + rng.uniform(-R, R)
        y = EUROPE_L93[1] + rng.uniform(-R, R)
        z_vrt = vrt_z(vrt, x, y)
        lon, lat = l93_to_wgs84(x, y)
        z_api = api_z(lon, lat)
        if z_vrt is None or z_vrt < -1000:
            print(f"  {x:10.2f} {y:11.2f}  hors données ({z_vrt})")
            continue
        e = z_vrt - z_api
        ecarts.append(abs(e))
        print(f"  {x:10.2f} {y:11.2f} {z_vrt:8.1f} {z_api:8.2f} {e:+7.2f}")

    if ecarts:
        print(f"\n  max |écart|: {max(ecarts):.2f} m, moyen: {sum(ecarts)/len(ecarts):.2f} m")
        if max(ecarts) > TOLERANCE_M:
            print("ECHEC: écart > tolérance", TOLERANCE_M, "m")
            sys.exit(1)
    print("Croisement API altimétrie : OK")


if __name__ == "__main__":
    main()
