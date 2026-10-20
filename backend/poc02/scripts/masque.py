#!/usr/bin/env python3
"""PoC02 - Masque d'altitude : polygones des obstacles hors-sol (MNH > seuil).

Usage:
    python3 scripts/masque.py [--seuil 10] [--out masque.geojson]

Pipeline : lit les VRT MNS/MNT du PoC01 (leur emprise EST la zone
d'exploration), calcule MNH = MNS - MNT, produit un masque binaire
(MNH > seuil), vectorise via gdal_polygonize, nettoie (micro-polygones)
et sort un GeoJSON WGS84.

La lecture MNS/MNT et les stats zonales sont decoupees en tuiles
(defaut 2048 x 2048 cellules) pour que la RAM reste raisonnable meme
sur une grande zone (le texte AAIGrid d'une tuile tient en memoire,
jamais celui de toute la zone).
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
TUILE_DEFAUT = 2048  # cote d'une tuile de lecture (cellules)


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


def gdal_read_array(vrt, x0, y0, x1, y1, w, h, precision=1):
    """Lit la fenêtre L93 [x0,y0,x1,y1] du VRT -> array numpy (float).

    Utilise gdal_translate -> /vsistdout/ en AAIGrid (texte, robuste).
    """
    r = subprocess.run(
        ["gdal_translate", "-of", "AAIGrid", "-co", f"DECIMAL_PRECISION={precision}",
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


def l93_vers_wgs84(x, y):
    """Convertit un point L93 en WGS84 (lat, lon) via gdaltransform."""
    r = subprocess.run(
        ["gdaltransform", "-s_srs", "EPSG:2154", "-t_srs", "EPSG:4326"],
        input=f"{x} {y}", capture_output=True, text=True, check=True)
    lon, lat = (float(v) for v in r.stdout.split()[:2])
    return lat, lon


def lire_mns_mnt_masque(vrt_mns, vrt_mnt, x0, y0, x1, y1, w, h, pas_x, pas_y,
                        seuil, tuile, mns_full, mnh_full, masque):
    """Remplit mns_full/mnh_full/masque tuile par tuile (RAM bornée).

    mns_full et mnh_full sont fournis pré-alloués (float32, h x w) car
    les stats zonales en auront besoin après la vectorisation ; seule
    la lecture (le goulot texte AAIGrid) est découpée.
    """
    n_tuiles = ((w + tuile - 1) // tuile) * ((h + tuile - 1) // tuile)
    faite = 0
    for ry in range(0, h, tuile):
        th = min(tuile, h - ry)
        y_bot = y1 - (ry + th) * pas_y
        y_haut = y1 - ry * pas_y
        for rx in range(0, w, tuile):
            tw = min(tuile, w - rx)
            x_g = x0 + rx * pas_x
            x_d = x0 + (rx + tw) * pas_x
            mns_t = gdal_read_array(vrt_mns, x_g, y_bot, x_d, y_haut, tw, th)
            mnt_t = gdal_read_array(vrt_mnt, x_g, y_bot, x_d, y_haut, tw, th)
            if mns_t.shape != mnt_t.shape:
                raise RuntimeError(
                    f"formes MNS/MNT incohérentes sur la tuile "
                    f"[{rx}:{rx + tw}, {ry}:{ry + th}]: "
                    f"{mns_t.shape} vs {mnt_t.shape}")
            mns_full[ry:ry + th, rx:rx + tw] = mns_t
            mnh_t = mns_t - mnt_t
            mnh_full[ry:ry + th, rx:rx + tw] = mnh_t
            masque[ry:ry + th, rx:rx + tw] = mnh_t > seuil
            faite += 1
            print(f"\r  lecture/seuillage: tuile {faite}/{n_tuiles}",
                  end="", flush=True)
    print()


def accumuler_stats_tuile(ids_t, mnh_t, mns_t, acc):
    """Accumule dans acc (gid -> [n, somme, mn, mx, mns_max]) les stats
    zonales d'une tuile du raster d'identifiants."""
    import numpy as np
    ids_flat = ids_t.ravel()
    if ids_flat.size == 0:
        return
    ordre = np.argsort(ids_flat, kind="stable")
    ids_tri = ids_flat[ordre]
    mnh_tri = mnh_t.ravel()[ordre]
    mns_tri = mns_t.ravel()[ordre]
    bornes = np.flatnonzero(np.diff(ids_tri)) + 1
    debut = np.r_[0, bornes]
    fin = np.r_[bornes, ids_tri.size]
    gids = ids_tri[debut]
    n = fin - debut
    somme = np.add.reduceat(mnh_tri, debut)
    mn = np.minimum.reduceat(mnh_tri, debut)
    mx = np.maximum.reduceat(mnh_tri, debut)
    mns_mx = np.maximum.reduceat(mns_tri, debut)
    for i, gid in enumerate(gids.tolist()):
        gid = int(gid)
        e = acc.get(gid)
        if e is None:
            acc[gid] = [int(n[i]), float(somme[i]), float(mn[i]),
                        float(mx[i]), float(mns_mx[i])]
        else:
            e[0] += int(n[i])
            e[1] += float(somme[i])
            e[2] = min(e[2], float(mn[i]))
            e[3] = max(e[3], float(mx[i]))
            e[4] = max(e[4], float(mns_mx[i]))


def lire_ids_et_stats(tif_id, mns_full, mnh_full, forme,
                      x0, y0, x1, y1, pas_x, pas_y, tuile):
    """Lit le raster d'identifiants tuile par tuile -> dict de stats.

    Retourne (ids_dispo, stats) : ids_dispo=False si le raster n'a pas
    pu être produit ou lu (le masque sortira sans stats, non bloquant).
    """
    import numpy as np
    acc = {}
    h, w = forme
    for ry in range(0, h, tuile):
        th = min(tuile, h - ry)
        y_bot = y1 - (ry + th) * pas_y
        y_haut = y1 - ry * pas_y
        for rx in range(0, w, tuile):
            tw = min(tuile, w - rx)
            x_g = x0 + rx * pas_x
            x_d = x0 + (rx + tw) * pas_x
            r = subprocess.run(
                ["gdal_translate", "-of", "AAIGrid", "-co", "DECIMAL_PRECISION=0",
                 "-projwin", str(x_g), str(y_haut), str(x_d), str(y_bot),
                 "-outsize", str(tw), str(th), str(tif_id), "/vsistdout/"],
                capture_output=True, text=True)
            if r.returncode != 0:
                return False, {}
            lignes = []
            for l in r.stdout.splitlines():
                l = l.strip()
                if not l or not (l[0].isdigit() or l[0] in "-+."):
                    continue
                try:
                    lignes.append([int(float(v)) for v in l.split()])
                except ValueError:
                    return False, {}
            if not lignes or len(lignes) != th or any(len(l) != tw for l in lignes):
                return False, {}
            ids_t = np.array(lignes, dtype=np.int64)
            accumuler_stats_tuile(ids_t,
                                  mnh_full[ry:ry + th, rx:rx + tw],
                                  mns_full[ry:ry + th, rx:rx + tw], acc)
    stats = {}
    for gid, (n, somme, mn, mx, mns_mx) in acc.items():
        stats[gid] = {
            "mnh_min_m": round(mn, 1),
            "mnh_max_m": round(mx, 1),
            "mnh_moy_m": round(somme / n, 1),
            "mns_max_m": round(mns_mx, 1),
        }
    return True, stats


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
    ap.add_argument("--tuile", type=int, default=TUILE_DEFAUT,
                    help=f"côté d'une tuile de lecture en cellules (défaut: {TUILE_DEFAUT})")
    args = ap.parse_args()

    import numpy as np

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
    go = (w * h) / 1_000_000_000 * 9
    print(f"  memoire de travail attendue: ~{go:.1f} Go "
          f"(grilles MNS/MNH/masque en RAM)")

    # grilles pré-allouées : mns et mnh sont gardées pour les stats zonales
    mns_full = np.empty((h, w), dtype=np.float32)
    mnh_full = np.empty((h, w), dtype=np.float32)
    masque = np.empty((h, w), dtype=bool)

    lire_mns_mnt_masque(vrt_mns, vrt_mnt, x0, y0, x1, y1, w, h, pas_x, pas_y,
                        args.seuil, args.tuile, mns_full, mnh_full, masque)

    masque_u8 = masque.view(np.uint8)  # 0/1, compatible PGM/GTiff Byte
    n = int(masque.sum())
    print(f"  cellules obstacle (MNH > {args.seuil:.1f} m): {n} / {masque.size}"
          f" ({100.0 * n / masque.size:.1f} % de la fenêtre)")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tif = td / "masque.tif"
        ecrire_masque_gtiff(tif, masque_u8, x0, y1, pas_x, pas_y)

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
        stats = {}
        if r_rast.returncode == 0:
            ok, stats = lire_ids_et_stats(tif_id, mns_full, mnh_full,
                                          masque_u8.shape,
                                          x0, y0, x1, y1, pas_x, pas_y,
                                          args.tuile)
            if not ok:
                print("  avertissement: stats MNH indisponibles "
                      "(raster d'identifiants illisible)")
        else:
            print("  avertissement: stats MNH indisponibles"
                  f" (gdal_rasterize: {r_rast.stderr.strip()[:120]})")

        # les grilles full ne servent plus: liberer avant l'export
        del mns_full, mnh_full, masque, masque_u8

        # export GeoJSON : uniquement les obstacles (DN > 0 — le fond
        # DN=0 n'est pas un obstacle), sans les attributs techniques
        gj = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
             "-simplify", str(SIMPLIFIE_M),
             "-where", "DN > 0", "-select", "DN",
             "/vsistdout/", str(gpkg)],
            check=True, capture_output=True, text=True).stdout

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
