# Poc 02 — Masque d'altitude (obstacles hors-sol)

Réutilise le socle du [Poc 01](../poc01/README.md) (tuiles 2 m Int16, VRT)
pour produire un **GeoJSON de polygones avec trous** : l'emprise des
cellules contenant un obstacle dont la **hauteur hors-sol** (MNH =
Z_MNS − Z_MNT, calculée à la demande, jamais stockée) dépasse le seuil
paramétré — bâti, forêt, ouvrages d'art.

## Principe

1. **Entrée** : VRT MNS + VRT MNT du Poc 01 (`backend/data/*.vrt`),
   emprise = disque de rayon `R` autour du point Europe
   (47.422648 / 0.683287, L93 525363.55 / 6705039.73).
2. **MNH à la demande** : `MNH = MNS − MNT` en mémoire, cellule par
   cellule (pas de fichier MNH).
3. **Masque binaire** : cellule = obstacle si `MNH > seuil` (paramètre,
   ex. 10 m). Le relief seul (MNH ≈ 0) n'est jamais obstacle.
4. **Vectorisation** : `gdal_polygonize` → MultiPolygon avec trous.
5. **Nettoyage** : suppression des micro-polygones (aire < 100 m²),
   simplification Douglas-Peucker (5 m).
6. **Sortie** : GeoJSON WGS84 (`EPSG:4326`), prêt pour une couche
   `fill` MapLibre ; chaque polygone porte son aire et la hauteur
   MNH max/moyenne qu'il contient.

## Outils

Depuis `backend/poc02` :

- `make masque SEUIL=10` — produit `masque.geojson` (seuil MNH en
  mètres, défaut 10) ;
- le script appelle `scripts/masque.py` qui peut aussi se lancer
  directement :

```bash
python3 scripts/masque.py --seuil 10 --rayon 1000 --out masque.geojson
```

Paramètres :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `--seuil` | 10 | hauteur hors-sol (m) au-delà de laquelle une cellule est un obstacle |
| `--rayon` | 1000 | rayon du disque analysé (m) autour du point Europe |
| `--out` | masque.geojson | fichier de sortie |

## Prérequis

Ceux du Poc 01 (`make -C ../poc01 doctor`), plus rien d'autre.
Les données doivent être ingérées (`make -C ../poc01 download ingest vrt`).
