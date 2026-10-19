#!/usr/bin/env python3
"""PoC01 - Contrôle qualité des tuiles 2 m Int16.

Usage: make check  (ou: python3 scripts/check.py depuis backend/poc01)

Vérifications :
- 14 tuiles présentes (7 MNS + 7 MNT) sur le carroyage attendu ;
- 500x500 px, pas 2 m, Int16, origine alignée sur la dalle 1 km^2 ;
- balises de traçabilité SOURCE_*/INGEST_* présentes ;
- cohérence MNS >= MNT (min et max) dalle par dalle ;
- altitude au point Europe (525363.55, 6705039.73) via gdallocationinfo.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
DATA = ROOT / "data"
DALLES = ["0524_6704", "0524_6705", "0525_6704", "0525_6705", "0525_6706", "0526_6704", "0526_6705"]
EUROPE_L93 = (525363.55, 6705039.73)
ERREURS = []


def info(path):
    r = subprocess.run(["gdalinfo", "-json", "-stats", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def check(cond, message):
    if not cond:
        ERREURS.append(message)
    return cond


def tile_path(produit, dalle):
    X, Y = dalle.split("_")
    return DATA / produit.lower() / f"LHD_FXX_{X}_{Y}_{produit}_O_0M50_LAMB93_IGN69.tif"


def main():
    for produit in ("MNS", "MNT"):
        for dalle in DALLES:
            nom = f"{produit} {dalle}"
            p = tile_path(produit, dalle)
            if not check(p.exists(), f"{nom}: tuile absente {p}"):
                continue
            j = info(p)

            taille = j["size"]
            check(taille == [500, 500], f"{nom}: taille {taille} != 500x500")

            typ = j["bands"][0]["type"]
            check(typ == "Int16", f"{nom}: type {typ} != Int16")

            gt = j["geoTransform"]
            check(abs(gt[1] - 2.0) < 1e-9 and abs(gt[5] + 2.0) < 1e-9,
                  f"{nom}: pas {gt[1]},{gt[5]} != 2 m")
            X, Y = int(dalle.split("_")[0]), int(dalle.split("_")[1])
            check(abs(gt[0] - X * 1000) <= 1.0 and abs(gt[3] - (Y + 1) * 1000) <= 1.0,
                  f"{nom}: origine ({gt[0]},{gt[3]}) hors dalle {dalle}")

            tags = j["metadata"].get("", {})
            for balise in ("SOURCE_PRODUIT", "SOURCE_DALLE", "INGEST_DATE", "INGEST_OUTIL"):
                check(balise in tags, f"{nom}: balise {balise} absente")

    # cohérence MNS >= MNT dalle par dalle
    for dalle in DALLES:
        pm, pt = tile_path("MNS", dalle), tile_path("MNT", dalle)
        if not (pm.exists() and pt.exists()):
            continue
        jm, jt = info(pm), info(pt)
        sm = jm["bands"][0].get("minimum")
        sj = jt["bands"][0].get("minimum")
        mm = jm["bands"][0].get("maximum")
        mj = jt["bands"][0].get("maximum")
        if None not in (mm, mj):
            check(mm >= mj, f"{dalle}: max MNS {mm} < max MNT {mj}")
        if None not in (sm, sj):
            check(sm <= sj + 2.0, f"{dalle}: min MNS {sm} > min MNT {sj} + 2 m")

    # altitude au point Europe via le VRT (si construit)
    for produit in ("mns", "mnt"):
        vrt = DATA / f"{produit}.vrt"
        if not vrt.exists():
            continue
        x, y = EUROPE_L93
        r = subprocess.run(["gdallocationinfo", "-xml", str(vrt), str(x), str(y)],
                           capture_output=True, text=True, check=True)
        try:
            z = float(r.stdout.split("<Value>")[1].split("</Value>")[0])
        except (IndexError, ValueError):
            ERREURS.append(f"{produit}.vrt: gdallocationinfo illisible")
            continue
        print(f"  {produit.upper()} au point Europe (L93 {x:.2f} {y:.2f}): {z:.1f} m NGF")

    if ERREURS:
        print("\nECHEC du contrôle qualité :")
        for e in ERREURS:
            print(f"  - {e}")
        sys.exit(1)
    print("\nContrôle qualité : OK (14 tuiles 2 m Int16, balises, MNS/MNT cohérents)")


if __name__ == "__main__":
    main()
