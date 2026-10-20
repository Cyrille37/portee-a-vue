#!/usr/bin/env python3
"""PoC03 - Masque d'altitude absolue : polygones des zones au-dessus (ou,
en mode --inverse, au-dessous) de ALTITUDE.

Usage:
    python3 scripts/masque_altitude.py --altitude 200 [--inverse] [--out masque.geojson]

Pipeline : lit le VRT MNS du PoC01 (son emprise EST la zone d'exploration),
produit un masque binaire (MNS > altitude, altitude absolue NGF) et
vectorise via gdal_polygonize. Contrairement au PoC02 (MNH = hors-sol),
le test est sur l'altitude absolue de la surface : le relief seul est
capté, ainsi que les batiments et la vegetation qui depassent le seuil.
Le MNT n'est pas lu (la MNS couvre deja sol + obstacles).

Mode --inverse : le masque devient MNS <= altitude (complementaire
strict du mode direct — les cellules exactement à ALTITUDE sont
« en dessous ») : les features representent alors tout ce que l'observateur
dominerait, un polygone dominant avec les masses au-dessus en trous.

La lecture MNS et les stats zonales sont decoupees en tuiles
(defaut 2048 x 2048 cellules) pour que la RAM de lecture reste bornee
meme sur une grande zone (le texte AAIGrid d'une tuile tient en memoire,
jamais celui de toute la zone).
"""
import argparse
import json
from datetime import datetime, timezone
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

    Retourne (x0, y0, x1, y1, largeur, hauteur, pas_x, pas_y, nodata)
    ou None si le VRT ne peut pas etre lu. nodata = valeur sentinel du
    raster (None si non declaree).
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
        nodata = info["bands"][0].get("noDataValue")
    except (KeyError, TypeError, ValueError):
        return None
    return (ul[0], lr[1], lr[0], ul[1], w, h, abs(gt[1]), abs(gt[5]), nodata)


def gdal_read_array(vrt, x0, y0, x1, y1, w, h, precision=1):
    """Lit la fen\u00eatre L93 [x0,y0,x1,y1] du VRT -> array numpy (float).

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
    if len(lignes) != h:
        raise RuntimeError(f"grille de {len(lignes)} lignes, {h} attendues, "
                           f"depuis {vrt}")
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


def lire_mns_masque(vrt_mns, x0, y0, x1, y1, w, h, pas_x, pas_y,
                    altitude, inverse, nodata, tuile, mns_full, masque,
                    valide_full):
    """Remplit mns_full/masque tuile par tuile (RAM de lecture bornee).

    mns_full est fourni pre-alloue (float32, h x w) car les stats zonales
    en auront besoin apres la vectorisation ; seule la lecture (le goulot
    texte AAIGrid) est decoupee.
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
            mns_full[ry:ry + th, rx:rx + tw] = mns_t
            valide_t = np.ones(mns_t.shape, dtype=bool) if nodata is None \
                else mns_t != nodata
            valide_full[ry:ry + th, rx:rx + tw] = valide_t
            if inverse:
                masque[ry:ry + th, rx:rx + tw] = valide_t & (mns_t <= altitude)
            else:
                masque[ry:ry + th, rx:rx + tw] = valide_t & (mns_t > altitude)
            faite += 1
            print(f"\r  lecture/seuillage: tuile {faite}/{n_tuiles}",
                  end="", flush=True)
    print()


def accumuler_stats_tuile(ids_t, mns_t, acc):
    """Accumule dans acc (gid -> [n, somme, mn, moy_acc, mx]) les stats
    zonales d'une tuile du raster d'identifiants.
    """
    import numpy as np
    ids_flat = ids_t.ravel()
    if ids_flat.size == 0:
        return
    ordre = np.argsort(ids_flat, kind="stable")
    ids_tri = ids_flat[ordre]
    mns_tri = mns_t.ravel()[ordre]
    bornes = np.flatnonzero(np.diff(ids_tri)) + 1
    debut = np.r_[0, bornes]
    fin = np.r_[bornes, ids_tri.size]
    gids = ids_tri[debut]
    n = fin - debut
    somme = np.add.reduceat(mns_tri, debut)
    mn = np.minimum.reduceat(mns_tri, debut)
    mx = np.maximum.reduceat(mns_tri, debut)
    for i, gid in enumerate(gids.tolist()):
        gid = int(gid)
        e = acc.get(gid)
        if e is None:
            acc[gid] = [int(n[i]), float(somme[i]), float(mn[i]),
                        float(mx[i])]
        else:
            e[0] += int(n[i])
            e[1] += float(somme[i])
            e[2] = min(e[2], float(mn[i]))
            e[3] = max(e[3], float(mx[i]))


def lire_ids_et_stats(tif_id, mns_full, forme,
                      x0, y0, x1, y1, pas_x, pas_y, tuile):
    """Lit le raster d'identifiants tuile par tuile -> dict de stats.

    Retourne (ids_dispo, stats) : ids_dispo=False si le raster n'a pas
    pu etre produit ou lu (le masque sortira sans stats, non bloquant).
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
                                  mns_full[ry:ry + th, rx:rx + tw], acc)
    stats = {}
    for gid, (n, somme, mn, mx) in acc.items():
        stats[gid] = {
            "n_cellules": int(n),
            "mns_min_m": round(mn, 1),
            "mns_moy_m": round(somme / n, 1),
            "mns_max_m": round(mx, 1),
        }
    return True, stats


def aire_anneau(pts, kx, ky):
    """Aire absolue d'un anneau en WGS84 converti en mètres (échelle locale)."""
    import numpy as np
    x, y = pts[:, 0] * kx, pts[:, 1] * ky
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))

def aire_polygone(coordinates):
    """Aire d'un polygone GeoJSON en WGS84, convertie en m\u00b2 (échelle locale),
    trous déduits.

    Le GeoJSON a été reprojeté en EPSG:4326 : le lacet donne des degrés²,
    qu'on convertit avec le facteur local degrés->mètres autour du centroïde
    (1° lat ≈ 111 320 m ; 1° lon ≈ 111 320·cos(lat)). Précision suffisante
    pour un filtre d'ordre de grandeur sur ~1 km. Le premier anneau est
    l'extérieur, les suivants sont des trous (déduits) — indispensable
    en mode inverse où le polygone dominant est troué.
    """
    import math
    import numpy as np
    pts0 = np.asarray(coordinates[0])
    lat0 = float(pts0[:, 1].mean())
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 111320.0
    aire = aire_anneau(pts0, kx, ky)
    for ring in coordinates[1:]:
        aire -= aire_anneau(np.asarray(ring), kx, ky)
    return max(aire, 0.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--altitude", type=float, required=True,
                    help="altitude absolue NGF (m) au-delà de laquelle une cellule est dans le masque")
    ap.add_argument("--inverse", action="store_true",
                    help="masque inverse : cellules avec MNS <= altitude (tout ce qui est en dessous)")
    ap.add_argument("--out", default="masque.geojson", help="fichier GeoJSON de sortie")
    ap.add_argument("--aire-mini", type=float, default=0.0,
                    help="aire minimale d'un polygone en m² (défaut: 0 = tout "
                         "conserver — tout ce qui dépasse le seuil est gardé)")
    ap.add_argument("--tuile", type=int, default=TUILE_DEFAUT,
                    help=f"côté d'une tuile de lecture en cellules (défaut: {TUILE_DEFAUT})")
    args = ap.parse_args()
    import numpy as np

    vrt_mns = DATA / "mns.vrt"
    if not vrt_mns.exists():
        print(f"{vrt_mns} absent: lancer make -C ../poc01 vrt", file=sys.stderr)
        sys.exit(1)

    # la zone d'exploration = l'emprise du VRT MNS
    ext = gdalinfo_extent(vrt_mns)
    if ext is None:
        print("emprise du VRT illisible (gdalinfo -json)", file=sys.stderr)
        sys.exit(1)
    x0, y0, x1, y1, w, h, pas_x, pas_y, nodata = ext
    print(f"  zone d'exploration (emprise du VRT): {w} x {h} cellules de "
          f"{pas_x:g} m ({(x1 - x0):.0f} x {(y1 - y0):.0f} m)")
    if nodata is not None:
        print(f"  valeur nodata du raster: {nodata:g} (cellules "
              f"\u00ab inconnues \u00bb exclues du masque, direct comme inverse)")

    go = (w * h) / 1_000_000_000 * 6
    print(f"  memoire de travail attendue: ~{go:.1f} Go "
          f"(grilles MNS/masque en RAM)")

    # grilles pre-allouees : mns gardee pour les stats zonales ;
    # valide_full marque les cellules non-nodata (le masque inverse ne
    # doit jamais contenir le nodata)
    mns_full = np.empty((h, w), dtype=np.float32)
    masque = np.empty((h, w), dtype=bool)
    valide_full = np.empty((h, w), dtype=bool)
    lire_mns_masque(vrt_mns, x0, y0, x1, y1, w, h, pas_x, pas_y,
                    args.altitude, args.inverse, nodata, args.tuile,
                    mns_full, masque, valide_full)

    masque_u8 = masque.view(np.uint8)  # 0/1, compatible PGM/GTiff Byte
    n = int(masque.sum())
    n_inconnues = int((~valide_full).sum())
    sens = "en dessous de (<=)" if args.inverse else "au-dessus de (>)"
    print(f"  cellules {sens} {args.altitude:.1f} m NGF: {n} / {masque.size}"
          f" ({100.0 * n / masque.size:.1f} % de la fenêtre) ;"
          f" nodata: {n_inconnues} ({100.0 * n_inconnues / masque.size:.1f} %)")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tif = td / "masque.tif"
        ecrire_masque_gtiff(tif, masque_u8, x0, y1, pas_x, pas_y)
        gpkg = td / "masque.gpkg"
        subprocess.run(["gdal_polygonize.py", str(tif), "-f", "GPKG",
                       str(gpkg), "masque", "DN"],
                       check=True, capture_output=True)

        # champ d'identifiant unique par polygone : le DN polygonise vaut
        # la valeur du raster (0/1), PAS un id par polygone. Plutot que de
        # copier via ogr2ogr -sql (les dialectes OGR ont des pieges
        # recurrents : alias promu en FID, geometrie implicite perdue),
        # on ajoute la colonne DIRECTEMENT dans le GPKG via SQLite — le
        # GPKG est une base SQLite, le fid de la table est unique par
        # polygone. Aucune copie, aucune geometrie manipulée.
        import sqlite3
        con = sqlite3.connect(gpkg)
        try:
            tables = [r[0] for r in con.execute(
                "SELECT table_name FROM gpkg_contents")]  # ex. ["masque"]
            table = tables[0]
            pk = [r[1] for r in con.execute(
                f"PRAGMA table_info({table})") if r[5]][0]
            con.execute(f"ALTER TABLE {table} ADD COLUMN poly_id INTEGER")
            con.execute(f"UPDATE {table} SET poly_id = {pk}")
            con.commit()
        finally:
            con.close()
        gpkg_id = gpkg

        # raster d'identifiants : chaque cellule prend l'id de son polygone
        # -> stats zonales par feature. -te/-tr explicites : gdal_rasterize
        # ne peut pas deviner la grille. En cas d'echec, le masque sort
        # sans stats (non bloquant).
        tif_id = td / "ids.tif"
        r_rast = subprocess.run(
            ["gdal_rasterize", "-a", "poly_id", "-l", "masque",
             "-te", str(x0), str(y0), str(x1), str(y1),
             "-tr", str(pas_x), str(pas_y), "-ot", "Int32",
             str(gpkg_id), str(tif_id)],
            capture_output=True, text=True)
        stats = {}
        if r_rast.returncode == 0:
            ok, stats = lire_ids_et_stats(tif_id, mns_full,
                                          masque_u8.shape,
                                          x0, y0, x1, y1, pas_x, pas_y,
                                          args.tuile)
            if not ok:
                print("  avertissement: stats MNS indisponibles "
                      "(raster d'identifiants illisible)")
        else:
            print("  avertissement: stats MNS indisponibles"
                  f" (gdal_rasterize: {r_rast.stderr.strip()[:120]})")

        # les grilles full ne servent plus: liberer avant l'export
        del mns_full, masque, masque_u8

        # export GeoJSON : uniquement les zones au-dessus du seuil (DN > 0),
        # sans les attributs techniques
        gj = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
             "-simplify", str(SIMPLIFIE_M),
             "-where", "DN > 0", "-select", "poly_id, DN",
             "/vsistdout/", str(gpkg_id)],
            check=True, capture_output=True, text=True).stdout

    fc = json.loads(gj)
    total = len(fc.get("features", []))
    n_multi = 0
    n_nulles = 0
    gardes = []
    for f in fc.get("features", []):
        # la simplification Douglas-Peucker (SIMPLIFIE_M) peut effondrer un
        # petit polygone : OGR exporte alors geometry: null
        if f.get("geometry") is None:
            n_nulles += 1
            continue
        if f["geometry"]["type"] != "Polygon":
            n_multi += 1
            continue
        st = stats.get(f["properties"].get("poly_id"), {})
        # aire exacte des cellules (nb x pas^2) quand les stats sont
        # disponibles ; sinon repli sur le lacet de la geometrie simplifiee
        if "n_cellules" in st:
            aire = st["n_cellules"] * pas_x * pas_y
        else:
            aire = aire_polygone(f["geometry"]["coordinates"])
        if aire >= args.aire_mini:
            props = {"aire_m2": round(aire, 1)}
            props.update(st)
            props.pop("n_cellules", None)
            props.pop("poly_id", None)
            f["properties"] = props
            gardes.append(f)
    if n_nulles:
        print(f"  avertissement: {n_nulles} geometrie(s) nulle(s) apres simplification "
              f"({SIMPLIFIE_M:g} m) ignoree(s) — reduire SIMPLIFIE_M pour les conserver")
    if n_multi:
        print(f"  avertissement: {n_multi} feature(s) MultiPolygon ignoree(s) "
              f"(attendu: aucune en pratique)")
    fc["features"] = gardes

    centre_lat, centre_lon = l93_vers_wgs84((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    # parametres du run au niveau de la FeatureCollection
    fc["properties"] = {
        "altitude_m": args.altitude,
        "inverse": bool(args.inverse),
        "zone_l93": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
        "aire_mini_m2": args.aire_mini,
        "date_generation": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "centre_lat": round(centre_lat, 6),
        "centre_lon": round(centre_lon, 6),
    }
    fc.pop("name", None)
    fc.pop("crs", None)  # RFC 7946: WGS84 par defaut, pas de membre crs
    print(f"  polygones vectoris\u00e9s: {total}, "
          f"gard\u00e9s (aire >= {args.aire_mini:.0f} m\u00b2): {len(gardes)}")
    Path(args.out).write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {args.out}")


if __name__ == "__main__":
    main()
