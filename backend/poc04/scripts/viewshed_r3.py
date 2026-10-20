#!/usr/bin/env python3
"""PoC04 - Viewshed R3/Wang : surface de vue directe d'un observateur.

Usage:
    python3 scripts/viewshed_r3.py --lat 47.810322 --lon 0.983288 \
        [--rayon 40000] [--angle 0.1] [--hauteur 2.0] [--out viewshed.geojson]

Algorithme R3 (Wang, Robinson & White, 2000) : le disque d'analyse est
decoupe en rayons reguliers partant de l'observateur ; le long de chaque
rayon on avance du centre vers l'exterieur en memorisant la pente
tangente maximale rencontree (angle d'elevation), et un echantillon est
visible si son angle d'elevation depasse ce maximum courant. L'erreur de
R3 est asymetrique : une cellule entre deux rayons peut etre declaree
visible a tort (faux positif), presque jamais l'inverse — acceptable en
planification radio (mieux vaut une zone optimiste qu'un faux
« impossible »).

Courbure terrestre + refraction : chaque echantillon est corrige de
z_corr = z - d^2 / (2 * k * R_T) avec k = 7/6 (standard radio,
equivalent -cc 0.85714 de gdal_viewshed). Obligatoire a 20-40 km :
la depression de l'horizon vaut ~146 m a 40 km avec refraction.

Pas d'echantillonnage adaptatif : le pas croit lineairement de la
resolution de la grille pres du centre a --pas-loin au bord du disque
(la pente tangente max est une fonction lisse : un relief de 200 m de
large a 30 km est correctement echantillonne au pas 10-20 m).

Pipeline : lit la fenetre MNS carree [centre +- rayon] du VRT du PoC01
(une seule lecture, RAM bornée par la fenetre), calcule le viewshed par
rayons, le reporte sur la grille, et vectorise via gdal_polygonize
(même pipeline que le PoC03). Sortie GeoJSON WGS84 + visibilite par
anneau de distance.
"""
import argparse
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
DATA = ROOT / "data"
VRT_MNS = DATA / "mns.vrt"

R_TERRE = 6_371_000.0  # rayon terrestre moyen (m)
SIMPLIFIE_M = 5.0      # simplification geometrique a l'export GeoJSON
ANNEAUX_DEFAUT = (100, 500, 1000, 2000, 5000, 10000, 20000, 40000)


# ---------------------------------------------------------------------------
# Coeur R3 (pur numpy, testable sans GDAL)
# ---------------------------------------------------------------------------

def distances_pas_adaptatif(rayon, pas_proche, pas_loin):
    """Distances d'echantillonnage le long d'un rayon, pas croissant.

    Le pas croit lineairement de pas_proche (a d=0) a pas_loin (a d=rayon).
    Retourne un tableau numpy croissant strict, de ~pas_proche a <= rayon.
    """
    import numpy as np
    if rayon <= pas_loin:
        return np.array([rayon], dtype=np.float64)
    # nombre d'echantillons : integrale du pas lineairement croissant
    # pas(d) = pas_proche + (pas_loin - pas_proche) * d / rayon
    # n tel que somme des pas = rayon -> n = rayon / pas_moyen
    pas_moyen = (pas_proche + pas_loin) / 2.0
    n = max(int(math.ceil(rayon / pas_moyen)), 2)
    u = np.arange(1, n + 1, dtype=np.float64) / n  # 0 < u <= 1
    d = rayon * u
    # pas local a chaque d
    pas = pas_proche + (pas_loin - pas_proche) * d / rayon
    # re-echillonner pour que l'ecart reel entre points ~ pas local :
    # approximation simple : cumul des pas locaux normalises a rayon
    pas[0] = pas_proche
    cumul = np.cumsum(pas)
    d = cumul * (rayon / cumul[-1])
    d = d[d <= rayon]
    if d.size == 0 or d[-1] < rayon * 0.999:
        d = np.append(d, rayon)
    return d


def echantillonner_mns(mns, x0, y0, pas_grid, cx, cy, theta, distances):
    """Interpole bilineairement la MNS le long d'un rayon.

    mns : grille numpy (row 0 = y max, comme un raster), origine L93
    (x0, y0) = coin bas-gauche ; pas_grid = taille de cellule (m) ;
    (cx, cy) = position de l'observateur en coordonnees grille
    (colonnes, lignes, origine bas-gauche) ; theta en radians.
    Retourne z echantillonne aux distances donnees (numpy).
    """
    import numpy as np
    h, w = mns.shape
    gx = cx + distances * math.cos(theta) / pas_grid
    gy = cy + distances * math.sin(theta) / pas_grid
    # origine bas-gauche : row = h - 1 - gy
    g_row = (h - 1) - gy
    np.clip(gx, 0, w - 1, out=gx)
    np.clip(g_row, 0, h - 1, out=g_row)
    c0 = np.floor(gx).astype(np.int64)
    r0 = np.floor(g_row).astype(np.int64)
    c1 = np.minimum(c0 + 1, w - 1)
    r1 = np.minimum(r0 + 1, h - 1)
    fx = gx - c0
    fy = g_row - r0
    z00 = mns[r0, c0]
    z01 = mns[r0, c1]
    z10 = mns[r1, c0]
    z11 = mns[r1, c1]
    return (z00 * (1 - fx) * (1 - fy) + z01 * fx * (1 - fy)
            + z10 * (1 - fx) * fy + z11 * fx * fy)


def visibilite_rayon(z, d, z0, cible, k, r_terre=R_TERRE):
    """R3 le long d'un rayon : booleen visible par echantillon.

    z : altitudes echantillonnees ; d : distances (> 0) ; z0 : altitude
    de l'observateur. Courbure+refraction : z_corr = z - d^2/(2*k*R_T).
    Visible si (z_corr + cible - z0) / d > tan_max courant ; le tan_max
    est mis a jour avec ou sans la cible (l'obstacle est la surface nue).
    """
    import numpy as np
    z_corr = z - (d * d) / (2.0 * k * r_terre)
    tan_elev = (z_corr - z0) / d
    tan_max = np.maximum.accumulate(tan_elev[:-1])
    tan_max = np.concatenate(([tan_elev[0]], tan_max))
    visible = (z_corr + cible - z0) / d >= tan_max
    tan_max_suivant = np.maximum(tan_max, tan_elev)
    return visible, tan_max_suivant


def viewshed_r3(mns, x0, y0, pas_grid, cx, cy, rayon, angle_deg, z0,
                cible, k, pas_proche, pas_loin, annees=(), verbose=True):
    """Calcule le viewshed R3 et le reporte sur la grille.

    mns : grille numpy, coin bas-gauche L93 (x0, y0), row 0 = y max.
    (cx, cy) : observateur en coordonnees grille (colonnes, lignes,
    origine bas-gauche). Retourne (masque_visible, stats_anneaux).

    Report sur la grille (assignation inverse, standard R3) : chaque
    cellule du disque est evaluee par son rayon le plus proche — angle
    de la cellule -> index du rayon encadrant, distance de la cellule ->
    echantillon du rayon (les distances etant identiques pour tous les
    rayons, c'est une simple indexation vectorisee). L'erreur est celle
    de R3 : une cellule entre deux rayons herite du verdict du rayon
    voisin, donc plutot a faux positifs — acceptable en planification.
    """
    import numpy as np
    h, w = mns.shape
    n_rayons = max(int(round(360.0 / angle_deg)), 1)
    distances = distances_pas_adaptatif(rayon, pas_proche, pas_loin)
    n_ech = len(distances)
    if verbose:
        print(f"  rayons: {n_rayons}, echantillons/rayon: {n_ech}")

    # 1. visibilite par rayon : (n_rayons, n_ech)
    vis_ray = np.zeros((n_rayons, n_ech), dtype=bool)
    for i in range(n_rayons):
        theta = 2.0 * math.pi * i / n_rayons
        z = echantillonner_mns(mns, x0, y0, pas_grid, cx, cy, theta, distances)
        visible, _ = visibilite_rayon(z, distances, z0, cible, k)
        vis_ray[i] = visible

    # 2. assignation inverse : chaque cellule -> (rayon, echantillon)
    # decoupee en tuiles pour borner la RAM (meme tuiles 2D que la lecture)
    vis = np.zeros((h, w), dtype=bool)
    tuile = 8192
    for ry in range(0, h, tuile):
        th = min(tuile, h - ry)
        for rx in range(0, w, tuile):
            tw = min(tuile, w - rx)
            yy, xx = np.mgrid[ry:ry + th, rx:rx + tw]
            gx = xx.astype(np.float64) - cx
            gy = ((h - 1) - yy.astype(np.float64)) - cy
            d_cell = np.hypot(gx, gy) * pas_grid
            dans = d_cell <= rayon
            theta_cell = np.arctan2(gy, gx)
            theta_cell = np.where(theta_cell < 0,
                                  theta_cell + 2.0 * math.pi, theta_cell)
            r_idx = np.floor(theta_cell / (2.0 * math.pi / n_rayons))
            np.clip(r_idx, 0, n_rayons - 1, out=r_idx)
            r_idx = r_idx.astype(np.int64)
            s_idx = np.searchsorted(distances, d_cell, side="right") - 1
            ok = dans & (s_idx >= 0)
            v = np.zeros((th, tw), dtype=bool)
            v[ok] = vis_ray[r_idx[ok], s_idx[ok]]
            vis[ry:ry + th, rx:rx + tw] = v

    # observateur : sa cellule est visible
    row0 = int(round((h - 1) - cy))
    col0 = int(round(cx))
    if 0 <= row0 < h and 0 <= col0 < w:
        vis[row0, col0] = True

    stats_anneaux = stats_anneaux_distance(vis, x0, y0, pas_grid, cx, cy,
                                           rayon, annees)
    return vis, stats_anneaux


def stats_anneaux_distance(vis, x0, y0, pas_grid, cx, cy, rayon, annees):
    """Visibilite par anneau de distance (cumulatifs, dernier = reste)."""
    import numpy as np
    h, w = vis.shape
    yy, xx = np.mgrid[0:h, 0:w]
    # coordonnees grille origine bas-gauche
    gx = xx.astype(np.float64)
    gy = (h - 1) - yy.astype(np.float64)
    d_m = np.hypot(gx - cx, gy - cy) * pas_grid
    bornes = [a for a in annees if a < rayon] + [rayon]
    bornes = sorted(set(bornes))
    stats = []
    precedent = 0.0
    for b in bornes:
        sel = (d_m > precedent) & (d_m <= b)
        n = int(sel.sum())
        if n:
            nv = int((vis & sel).sum())
            stats.append({
                "de_m": int(precedent), "a_m": int(b),
                "cellules": n, "visibles": nv,
                "pct": round(100.0 * nv / n, 1),
            })
        precedent = b
    return stats


# ---------------------------------------------------------------------------
# Acces GDAL (VRT du PoC01) — meme approche que le PoC03
# ---------------------------------------------------------------------------

def gdalinfo_transforme(vrt):
    """Geotransform + taille du VRT via gdalinfo -json.

    Retourne (x0, pas_x, y1, pas_y, w, h) — x0/y1 coin haut-gauche.
    """
    r = subprocess.run(["gdalinfo", "-json", str(vrt)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        info = json.loads(r.stdout)
        w, h = info["size"]
        gt = info["geoTransform"]
    except (KeyError, TypeError, ValueError):
        return None
    return (gt[0], abs(gt[1]), gt[3], abs(gt[5]), w, h)


def wgs84_vers_l93(lat, lon):
    r = subprocess.run(
        ["gdaltransform", "-s_srs", "EPSG:4326", "-t_srs", "EPSG:2154"],
        input=f"{lon} {lat}", capture_output=True, text=True, check=True)
    x, y = (float(v) for v in r.stdout.split()[:2])
    return x, y


def l93_vers_wgs84(x, y):
    r = subprocess.run(
        ["gdaltransform", "-s_srs", "EPSG:2154", "-t_srs", "EPSG:4326"],
        input=f"{x} {y}", capture_output=True, text=True, check=True)
    lon, lat = (float(v) for v in r.stdout.split()[:2])
    return lat, lon


def lire_fenetre_mns(vrt, cx93, cy93, rayon, precision=1):
    """Lit la fenetre carree [centre +- rayon] du VRT -> (mns, x0, y0, pas).

    Retourne la grille numpy (row 0 = y max), le coin bas-gauche L93
    (x0, y0) et le pas (m). Une seule passe gdal_translate AAIGrid.
    """
    import numpy as np
    x_g, y_b = cx93 - rayon, cy93 - rayon
    x_d, y_h = cx93 + rayon, cy93 + rayon
    r = subprocess.run(
        ["gdal_translate", "-of", "AAIGrid", "-co", f"DECIMAL_PRECISION={precision}",
         "-projwin", str(x_g), str(y_h), str(x_d), str(y_b),
         str(vrt), "/vsistdout/"],
        capture_output=True, text=True, check=True)
    lignes = []
    for l in r.stdout.splitlines():
        l = l.strip()
        if not l or not (l[0].isdigit() or l[0] in "-+."):
            continue
        lignes.append([float(v) for v in l.split()])
    if not lignes:
        raise RuntimeError(f"AAIGrid illisible depuis {vrt}")
    largeur = len(lignes[0])
    if any(len(l) != largeur for l in lignes):
        raise RuntimeError("grille non rectangulaire")
    mns = np.array(lignes, dtype=np.float32)
    h, w = mns.shape
    pas_x = (x_d - x_g) / w
    pas_y = (y_h - y_b) / h
    if abs(pas_x - pas_y) > 1e-6:
        raise RuntimeError(f"grille non carree: {pas_x} x {pas_y}")
    return mns, x_g, y_b, pas_x


def ecrire_masque_gtiff(chemin, masque, x0, y1, pas):
    h, w = masque.shape
    with open(chemin.with_suffix(".pgm"), "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (w, h))
        f.write(masque.tobytes())
    subprocess.run(
        ["gdal_translate", "-of", "GTiff", "-ot", "Byte", "-a_srs", "EPSG:2154",
         "-a_ullr", str(x0), str(y1), str(x0 + w * pas), str(y1 - h * pas),
         str(chemin.with_suffix(".pgm")), str(chemin)],
        check=True, capture_output=True)


def aire_anneau(pts, kx, ky):
    import numpy as np
    x, y = pts[:, 0] * kx, pts[:, 1] * ky
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def aire_polygone(coordinates):
    """Aire d'un polygone GeoJSON WGS84 en m^2, trous deduits (cf. PoC03)."""
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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--rayon", type=float, default=10000,
                    help="rayon du disque d'analyse (m)")
    ap.add_argument("--angle", type=float, default=0.1,
                    help="angle de numerisation entre rayons (degres)")
    ap.add_argument("--hauteur", type=float, default=2.0,
                    help="hauteur d'antenne au-dessus du sol (m)")
    ap.add_argument("--cible", type=float, default=0.0,
                    help="hauteur ajoutee a chaque cellule observee (m)")
    ap.add_argument("--k", type=float, default=7.0 / 6.0,
                    help="coefficient de refraction effectif (R_eff = k R_T)")
    ap.add_argument("--pas-loin", type=float, default=10.0,
                    help="pas d'echantillonnage au bord du disque (m)")
    ap.add_argument("--aire-mini", type=float, default=0.0,
                    help="aire minimale d'un polygone visible (m^2)")
    ap.add_argument("--out", default="viewshed.geojson",
                    help="fichier GeoJSON de sortie")
    args = ap.parse_args()
    import numpy as np

    if not VRT_MNS.exists():
        print(f"{VRT_MNS} absent: lancer make -C ../poc01 vrt", file=sys.stderr)
        sys.exit(1)

    rayon = args.rayon
    if rayon > 50000:
        print("rayon > 50 km: hors bornes du socle (doc de besoin)", file=sys.stderr)
        sys.exit(1)

    print(f"  observateur: {args.lat}, {args.lon} (+{args.hauteur} m)")
    cx93, cy93 = wgs84_vers_l93(args.lat, args.lon)
    print(f"  centre L93: {cx93:.1f}, {cy93:.1f} — rayon {rayon / 1000:.0f} km")

    mns, x0, y0, pas = lire_fenetre_mns(VRT_MNS, cx93, cy93, rayon)
    h, w = mns.shape
    print(f"  fenetre MNS: {w} x {h} cellules de {pas:g} m "
          f"({(w * pas) / 1000:.0f} x {(h * pas) / 1000:.0f} km)")

    cx = (cx93 - x0) / pas
    cy = (cy93 - y0) / pas
    if not (0 <= cx < w and 0 <= cy < h):
        print("observateur hors couverture du VRT (zone PoC01)", file=sys.stderr)
        sys.exit(1)

    z_centre = echantillonner_mns(mns, x0, y0, pas, cx, cy, 0.0,
                                  np.array([0.0]))[0]
    z0 = float(z_centre) + args.hauteur
    print(f"  altitude MNS au centre: {z_centre:.1f} m — observateur a {z0:.1f} m NGF")

    vis, stats = viewshed_r3(mns, x0, y0, pas, cx, cy, rayon, args.angle,
                             z0, args.cible, args.k, pas, args.pas_loin,
                             annees=ANNEAUX_DEFAUT)
    n = int(vis.sum())
    print(f"  cellules visibles: {n} / {vis.size} ({100.0 * n / vis.size:.1f} %)")
    print("  visibilite par anneau de distance:")
    for s in stats:
        print(f"    {s['de_m']:>6} - {s['a_m']:>6} m: "
              f"{s['pct']:5.1f} % ({s['visibles']}/{s['cellules']})")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tif = td / "viewshed.tif"
        ecrire_masque_gtiff(tif, vis.view(np.uint8), x0, y0 + h * pas, pas)
        gpkg = td / "viewshed.gpkg"
        subprocess.run(["gdal_polygonize.py", str(tif), "-f", "GPKG",
                        str(gpkg), "viewshed", "DN"],
                       check=True, capture_output=True)
        gj = subprocess.run(
            ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326",
             "-simplify", str(SIMPLIFIE_M),
             "-where", "DN > 0", "-select", "DN",
             "/vsistdout/", str(gpkg)],
            check=True, capture_output=True, text=True).stdout
        fc = json.loads(gj)

    centre_lat, centre_lon = l93_vers_wgs84(cx93, cy93)
    run = {
        "date_generation": datetime.now().isoformat(timespec="seconds"),
        "centre_lat": round(centre_lat, 7),
        "centre_lon": round(centre_lon, 7),
        "rayon_m": rayon,
        "angle_deg": args.angle,
        "hauteur_antenne_m": args.hauteur,
        "altitude_observateur_m": round(z0, 1),
        "cible_m": args.cible,
        "k_refraction": round(args.k, 4),
        "pas_loin_m": args.pas_loin,
        "pas_grille_m": round(float(pas), 2),
        "aire_mini_m2": args.aire_mini,
        "anneaux": stats,
    }

    features = []
    for f in fc.get("features", []):
        geom = f.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon":
            polys = [coords]
        elif gtype == "MultiPolygon":
            polys = coords
        else:
            continue
        aire = sum(aire_polygone(p) for p in polys)
        if args.aire_mini > 0 and aire < args.aire_mini:
            continue
        features.append({
            "type": "Feature",
            "properties": {"aire_m2": round(aire, 1)},
            "geometry": geom,
        })

    out = {
        "type": "FeatureCollection",
        "properties": run,
        "features": features,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"  {len(features)} polygones visibles -> {args.out}")


if __name__ == "__main__":
    main()
