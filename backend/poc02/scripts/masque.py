#!/usr/bin/env python3
"""PoC02 - Masque d'altitude : polygones des obstacles hors-sol (MNH > seuil).

Usage:
    python3 scripts/masque.py [--seuil 10] [--rayon 1000] [--out masque.geojson]

Pipeline : lit les VRT MNS/MNT du PoC01, calcule MNH = MNS - MNT à la
demande, produit un masque binaire (MNH > seuil), vectorise via
gdal_polygonize, nettoie (micro-polygones) et sort un GeoJSON WGS84.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
DATA = ROOT / "data"
EUROPE_L93 = (525363.55, 6705039.73)
AIRE_MINI_M2 = 100.0
SIMPLIFIE_M = 5.0
PAS = 2.0  # résolution des tuiles PoC01


def gdal_read_array(vrt, x0, y0, x1, y1):
    """Lit la fenêtre L93 [x0,y0,x1,y1] du VRT -> array numpy (float).

    Utilise gdal_translate -> /vsistdout/ en AAIGrid (texte, robuste).
    """
    w = max(1, int(round((x1 - x0) / PAS)))
    h = max(1, int(round((y1 - y0) / PAS)))
    r = subprocess.run(
        ["gdal_translate", "-of", "AAIGrid", "-co", "DECIMAL_PRECISION=1",
         "-projwin", str(x0), str(y1), str(x1), str(y0),
         "-outsize", str(w), str(h), str(vrt), "/vsistdout/"],
        capture_output=True, text=True, check=True)
    import numpy as np
    lines = [l for l in r.stdout.splitlines() if l and not l.startswith(("ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "NODATA_value"))]
    return np.array([[float(v) for v in l.split()] for l in lines], dtype=np.float32)


def ecrire_masque_gtiff(chemin, masque, x0, y1):
    """Écrit le masque binaire en GeoTIFF (via PGM binaire, lu par GDAL)."""
    h, w = masque.shape
    with open(chemin.with_suffix(".pgm"), "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        f.write(masque.tobytes())
    subprocess.run(
        ["gdal_translate", "-of", "GTiff", "-ot", "Byte", "-a_srs", "EPSG:2154",
         "-a_ullr", str(x0), str(y1), str(x0 + w * PAS), str(y1 - h * PAS),
         str(chemin.with_suffix(".pgm")), str(chemin)],
        check=True, capture_output=True)


def aire_polygone(ring):
    """Aire d'un anneau L93 (lacet), en m²."""
    import numpy as np
    pts = np.asarray(ring)
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seuil", type=float, default=10.0,
                    help="hauteur hors-sol (m) au-delà de laquelle une cellule est obstacle (défaut: 10)")
    ap.add_argument("--rayon", type=float, default=1000.0,
                    help="rayon du disque analysé (m) autour du point Europe (défaut: 1000)")
    ap.add_argument("--out", default="masque.geojson", help="fichier GeoJSON de sortie")
    args = ap.parse_args()

    vrt_mns, vrt_mnt = DATA / "mns.vrt", DATA / "mnt.vrt"
    for v in (vrt_mns, vrt_mnt):
        if not v.exists():
            print(f"{v} absent: lancer make -C ../poc01 vrt", file=sys.stderr)
            sys.exit(1)

    cx, cy = EUROPE_L93
    x0, x1 = cx - args.rayon, cx + args.rayon
    y0, y1 = cy - args.rayon, cy + args.rayon

    mns = gdal_read_array(vrt_mns, x0, y0, x1, y1)
    mnt = gdal_read_array(vrt_mnt, x0, y0, x1, y1)
    if mns.shape != mnt.shape:
        print(f"formes MNS/MNT incohérentes: {mns.shape} vs {mnt.shape}", file=sys.stderr)
        sys.exit(1)

    import numpy as np
    mnh = mns - mnt
    masque = (mnh > args.seuil).astype(np.uint8)

    n = int(masque.sum())
    print(f"  cellules obstacle (MNH > {args.seuil:.1f} m): {n} / {masque.size}"
          f" ({100.0 * n / masque.size:.1f} % de la fenêtre)")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tif = td / "masque.tif"
        ecrire_masque_gtiff(tif, masque, x0, y1)

        gpkg = td / "masque.gpkg"
        subprocess.run(["gdal_polygonize.py", str(tif), "-f", "GPKG",
                        str(gpkg), "obstacles", "DN"],
                       check=True, capture_output=True)

        gj = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
             "-simplify", str(SIMPLIFIE_M), "/vsistdout/", str(gpkg)],
            check=True, capture_output=True, text=True).stdout

    fc = json.loads(gj)
    gardes = []
    for f in fc.get("features", []):
        if f["geometry"]["type"] != "Polygon":
            continue
        aire = aire_polygone(f["geometry"]["coordinates"][0])
        if aire >= AIRE_MINI_M2:
            f["properties"]["aire_m2"] = round(aire, 1)
            gardes.append(f)
    fc["features"] = gardes
    print(f"  polygones gardés (aire >= {AIRE_MINI_M2:.0f} m²): {len(gardes)}")

    Path(args.out).write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
