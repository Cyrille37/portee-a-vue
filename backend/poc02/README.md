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
5. **Nettoyage** : optionnel, filtrage des polygones d'aire <
   `--aire-mini` (défaut **0 : tout conserver** — tout ce qui dépasse le
   seuil est gardé, y compris un arbre isolé de quelques cellules 2 m) ;
   simplification Douglas-Peucker (5 m).
6. **Sortie** : GeoJSON WGS84 (`EPSG:4326`), prêt pour une couche
   `fill` MapLibre ; chaque polygone porte les attributs décrits
   ci-dessous, et la `FeatureCollection` embarque les paramètres du
   run (`seuil_m`, `rayon_m`, `aire_mini_m2`, `date_generation`,
   `centre_lat`, `centre_lon`).

## Attributs des features

| Attribut | Description |
|---|---|
| `aire_m2` | Surface du polygone en m² — taille de l'emprise au sol de l'obstacle. |
| `mnh_min_m` | Hauteur hors-sol minimale des cellules du polygone — pour un arbre, départ de la canopée ; pour un bâtiment, niveau de sa base. |
| `mnh_max_m` | Hauteur hors-sol maximale des cellules du polygone — le point le plus haut de l'objet (cime, faitage, antenne). |
| `mnh_moy_m` | Hauteur hors-sol moyenne des cellules du polygone — ordre de grandeur de l'objet, utile pour qualifier bâti élevé vs canopée. |
| `mns_max_m` | Altitude absolue (NGF) du point le plus haut de l'objet — directement comparable au futur masque-observateur, et candidat « point haut » pour un répéteur. |

## Outils

Depuis `backend/poc02` :

```bash
make masque                     # seuil 10 m par défaut
make masque SEUIL=20           # obstacles de plus de 20 m
make masque SEUIL=5 RAYON=500  # seuil 5 m, rayon 500 m
make masque SEUIL=15 OUT=test15.geojson   # fichier de sortie nommé

# ou directement :
python3 scripts/masque.py --seuil 15 --rayon 1000 --out masque.geojson
```

```bash
python3 scripts/masque.py --seuil 10 --rayon 1000 --out masque.geojson
```

Paramètres :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `--seuil` | 10 | hauteur hors-sol (m) au-delà de laquelle une cellule est un obstacle |
| `--rayon` | 1000 | rayon du disque analysé (m) autour du point Europe |
| `--aire-mini` | 0 | aire minimale d'un polygone (m²) — 0 = tout conserver |
| `--out` | masque.geojson | fichier de sortie |

## Prérequis

Ceux du Poc 01 (`make -C ../poc01 doctor`), plus rien d'autre.
Les données doivent être ingérées (`make -C ../poc01 download ingest vrt`).
