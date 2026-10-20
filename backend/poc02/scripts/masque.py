#!/usr/bin/env python3
"""PoC02 - Masque d'altitude : polygones des obstacles hors-sol (MNH > seuil).

Usage:
    python3 scripts/masque.py [--seuil 10] [--out masque.geojson]

Pipeline : lit les VRT MNS/MNT du PoC01 (leur emprise EST la zone
d'exploration), calcule MNH = MNS - MNT, produit un masque binaire
(MNH > seuil), vectorise via gdal_polygonize, nettoie (micro-polygones)
et sort un GeoJSON WGS84.
"""
import argparse
import json
from datetime import datetime
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
DATA = ROOT / "data"
SIMPLIFIE_M = 5.0  # simplification geometrique a l'export GeoJSON


def gdalinfo_extent(vrt):
    """Emprise L93 + taille + pas d'un VRT via gdalinfo -json.

    Retourne (x0, y0, x1, y1, largeur, hauteur, pas_x, pas_y) ou None
    si le VRT ne peut pas etre lu.
    """
    r = subprocess.run(["gdalinfo", "-json", str(vrt)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        info = json.loads(r.stdout)
        w, h = info["size"]
        ul = info["cornerCoordinates"]["upperLeft"]
        lr = info["cornerCoordinates"]["lowerRight"]
        gt = info["geoTransform"]
    except (KeyError, TypeError, ValueError):
        return None
    return (ul[0], lr[1], lr[0], ul[1], w, h, abs(gt[1]), abs(gt[5]))


def gdal_read_array(vrt, x0, y0, x1, y1, w, h):
    """Lit la fenêtre L93 [x0,y0,x1,y1] du VRT -> array numpy (float).

    Utilise gdal_translate -> /vsistdout/ en AAIGrid (texte, robuste).
    """
    r = subprocess.run(
        ["gdal_translate", "-of", "AAIGrid", "-co", "DECIMAL_PRECISION=1",
         "-projwin", str(x0), str(y1), str(x1), str(y0),
         "-outsize", str(w), str(h), str(vrt), "/vsistdout/"],
        capture_output=True, text=True, check=True)
    import numpy as np
    # ne garder que les lignes numeriques (l'AAIGrid vers stdout embarque
    # aussi l'en-tete et une ligne de projection)
    lignes = []
    for l in r.stdout.splitlines():
        l = l.strip()
        if not l or not (l[0].isdigit() or l[0] in "-+."):
            continue
        lignes.append([float(v) for v in l.split()])
    if not lignes:
        raise RuntimeError(f"AAIGrid illisible depuis {vrt}: {r.stdout[:200]!r}")
    largeur = len(lignes[0])
    if any(len(l) != largeur for l in lignes):
        raise RuntimeError(f"grille non rectangulaire depuis {vrt}")
    return np.array(lignes, dtype=np.float32)


def ecrire_masque_gtiff(chemin, masque, x0, y1, pas_x, pas_y):
    """
    Écrit le masque binaire en GeoTIFF (via PGM binaire, lu par GDAL).
    """
    h, w = masque.shape
    with open(chemin.with_suffix(".pgm"), "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        f.write(masque.tobytes())
    subprocess.run(
        ["gdal_translate", "-of", "GTiff", "-ot", "Byte", "-a_srs", "EPSG:2154",
         "-a_ullr", str(x0), str(y1), str(x0 + w * pas_x), str(y1 - h * pas_y),
         str(chemin.with_suffix(".pgm")), str(chemin)],
        check=True, capture_output=True)


def _lire_pgm_ou_gtiff(chemin, forme_attendue):
    """Lit le raster d'identifiants en array int, ou None si illisible."""
    import numpy as np
    r = subprocess.run(["gdal_translate", "-of", "AAIGrid", "-co", "DECIMAL_PRECISION=0",
                        str(chemin), "/vsistdout/"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    lignes = []
    for l in r.stdout.splitlines():
        l = l.strip()
        if not l or not (l[0].isdigit() or l[0] in "-+."):
            continue
        try:
            lignes.append([int(float(v)) for v in l.split()])
        except ValueError:
            return None
    if not lignes:
        return None
    a = np.array(lignes, dtype=np.int64)
    return a if a.shape == forme_attendue else None


def l93_vers_wgs84(x, y):
    """Convertit un point L93 en WGS84 (lat, lon) via gdaltransform."""
    r = subprocess.run(
        ["gdaltransform", "-s_srs", "EPSG:2154", "-t_srs", "EPSG:4326"],
        input=f"{x} {y}", capture_output=True, text=True, check=True)
    lon, lat = (float(v) for v in r.stdout.split()[:2])
    return lat, lon


def aire_polygone(ring):
    """Aire d'un anneau en WGS84, convertie en m² (échelle locale).

    Le GeoJSON a été reprojeté en EPSG:4326 : le lacet donne des degrés²,
    qu'on convertit avec le facteur local degrés->mètres autour du centroïde
    (1° lat ≈ 111 320 m ; 1° lon ≈ 111 320·cos(lat)). Précision suffisante
    pour un filtre d'ordre de grandeur sur ~1 km.
    """
    import math
    import numpy as np
    pts = np.asarray(ring)
    lat0 = float(pts[:, 1].mean())
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 111320.0
    x, y = pts[:, 0] * kx, pts[:, 1] * ky
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seuil", type=float, default=10.0,
                    help="hauteur hors-sol (m) au-delà de laquelle une cellule est obstacle (défaut: 10)")
    ap.add_argument("--out", default="masque.geojson", help="fichier GeoJSON de sortie")
    ap.add_argument("--aire-mini", type=float, default=0.0,
                    help="aire minimale d'un polygone en m² (défaut: 0 = tout "
                         "conserver — tout ce qui dépasse le seuil est gardé)")
    args = ap.parse_args()

    vrt_mns, vrt_mnt = DATA / "mns.vrt", DATA / "mnt.vrt"
    for v in (vrt_mns, vrt_mnt):
        if not v.exists():
            print(f"{v} absent: lancer make -C ../poc01 vrt", file=sys.stderr)
            sys.exit(1)

    # la zone d'exploration = l'emprise des VRT (intersection MNS/MNT)
    ext_mns = gdalinfo_extent(vrt_mns)
    ext_mnt = gdalinfo_extent(vrt_mnt)
    if ext_mns is None or ext_mnt is None:
        print("emprise des VRT illisible (gdalinfo -json)", file=sys.stderr)
        sys.exit(1)
    x0 = max(ext_mns[0], ext_mnt[0])
    y0 = max(ext_mns[1], ext_mnt[1])
    x1 = min(ext_mns[2], ext_mnt[2])
    y1 = min(ext_mns[3], ext_mnt[3])
    if x1 <= x0 or y1 <= y0:
        print("VRT MNS et MNT sans zone commune", file=sys.stderr)
        sys.exit(1)
    pas_x = min(ext_mns[6], ext_mnt[6])
    pas_y = min(ext_mns[7], ext_mnt[7])
    w = max(1, int(round((x1 - x0) / pas_x)))
    h = max(1, int(round((y1 - y0) / pas_y)))
    if (w, h) != (ext_mns[4], ext_mns[5]):
        print(f"avertissement: emprises MNS/MNT differentes, "
              f"analyse limitee a l'intersection L93 [{x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f}]")

    print(f"  zone d'exploration (emprise des VRT): {w} x {h} cellules de "
          f"{pas_x:g} m ({(x1 - x0):.0f} x {(y1 - y0):.0f} m)")

    mns = gdal_read_array(vrt_mns, x0, y0, x1, y1, w, h)
    mnt = gdal_read_array(vrt_mnt, x0, y0, x1, y1, w, h)
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
        ecrire_masque_gtiff(tif, masque, x0, y1, pas_x, pas_y)

        gpkg = td / "masque.gpkg"
        subprocess.run(["gdal_polygonize.py", str(tif), "-f", "GPKG",
                        str(gpkg), "obstacles", "DN"],
                       check=True, capture_output=True)

        # raster d'identifiants: chaque polygone polygonise remplace ses
        # cellules par son index (attribut DN) -> stats zonales directes.
        # -te/-tr explicites: gdal_rasterize ne peut pas deviner la grille.
        # En cas d'echec, le masque est produit sans stats (non bloquant).
        tif_id = td / "ids.tif"
        r_rast = subprocess.run(
            ["gdal_rasterize", "-a", "DN", "-l", "obstacles",
             "-te", str(x0), str(y0), str(x1), str(y1),
             "-tr", str(pas_x), str(pas_y), "-ot", "Int32",
             str(gpkg), str(tif_id)],
            capture_output=True, text=True)
        ids = None
        if r_rast.returncode == 0:
            ids = _lire_pgm_ou_gtiff(tif_id, masque.shape)
        else:
            print("  avertissement: stats MNH indisponibles"
                  f" (gdal_rasterize: {r_rast.stderr.strip()[:120]})")

        # export GeoJSON : uniquement les obstacles (DN > 0 — le fond
        # DN=0 n'est pas un obstacle), sans les attributs techniques
        gj = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
             "-simplify", str(SIMPLIFIE_M),
             "-where", "DN > 0", "-select", "DN",
             "/vsistdout/", str(gpkg)],
            check=True, capture_output=True, text=True).stdout

    # stats zonales par polygone (identifiant = valeur DN du GPKG) :
    # mnh min/max/moy et mns max, pour qualifier chaque obstacle
    stats = {}
    if ids is not None and ids.shape == mnh.shape:
        ordre = np.argsort(ids, axis=None)
        ids_tri = ids.flatten()[ordre]
        mnh_tri = mnh.flatten()[ordre]
        mns_tri = mns.flatten()[ordre]
        bornes = np.flatnonzero(np.diff(ids_tri)) + 1
        for debut, fin in zip(np.r_[0, bornes], np.r_[bornes, ids_tri.size]):
            gid = int(ids_tri[debut])
            vals = mnh_tri[debut:fin]
            stats[gid] = {
                "mnh_min_m": round(float(vals.min()), 1),
                "mnh_max_m": round(float(vals.max()), 1),
                "mnh_moy_m": round(float(vals.mean()), 1),
                "mns_max_m": round(float(mns_tri[debut:fin].max()), 1),
            }

    fc = json.loads(gj)
    total = len(fc.get("features", []))
    gardes = []
    for f in fc.get("features", []):
        if f["geometry"]["type"] != "Polygon":
            continue
        aire = aire_polygone(f["geometry"]["coordinates"][0])
        if aire >= args.aire_mini:
            props = {"aire_m2": round(aire, 1)}
            props.update(stats.get(f["properties"].get("DN"), {}))
            f["properties"] = props
            gardes.append(f)
    fc["features"] = gardes

    centre_lat, centre_lon = l93_vers_wgs84((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    # parametres du run au niveau de la FeatureCollection
    fc["properties"] = {
        "seuil_m": args.seuil,
        "zone_l93": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
        "aire_mini_m2": args.aire_mini,
        "date_generation": datetime.now().isoformat(timespec="seconds"),
        "centre_lat": round(centre_lat, 6),
        "centre_lon": round(centre_lon, 6),
    }
    fc.pop("name", None)
    print(f"  polygones obstacles vectorisés: {total}, "
          f"gardés (aire >= {args.aire_mini:.0f} m²): {len(gardes)}")

    Path(args.out).write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
