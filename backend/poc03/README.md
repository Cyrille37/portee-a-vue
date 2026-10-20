# Poc 03 — Masque d'altitude absolue (relief + obstacles)

Réutilise le socle du [Poc 01](../poc01/README.md) (tuiles 2 m Int16, VRT)
pour produire un **GeoJSON de polygones avec trous** : l'emprise des
cellules dont l'**altitude absolue** (Z_MNS, NGF) dépasse le seuil
paramétré — relief (collines, crêtes), mais aussi bâtiments et forêt qui
culminent au-dessus du seuil.

## Différence avec le Poc 02

| | Poc 02 | Poc 03 |
|---|---|---|
| Test | `MNH > seuil` (hauteur **hors-sol** = MNS − MNT) | `MNS > altitude` (altitude **absolue** NGF) |
| Ce qui sort | uniquement les obstacles hors-sol (bâti, forêt) | le relief **et** les obstacles : tout ce qui dépasse `ALTITUDE` |
| Grilles lues | MNS + MNT | **MNS seule** (le MNT n'est jamais lu) |
| Sens physique | « où sont les objets hauts » | « tout ce qui est plus haut que l'observateur » — masque d'obstructions pour la portée radio |

`ALTITUDE` est typiquement l'altitude d'un observateur (site candidat
répéteur, éventuellement + hauteur d'antenne) : le masque dessine alors
les masses — collines ou bâtiments — qui dépassent cet horizon.

## Principe

1. **Entrée** : VRT MNS du Poc 01 (`backend/data/mns.vrt`). La zone
   d'exploration est l'emprise du VRT (celle définie par le `zone.env`
   du Poc 01).
2. **Masque binaire** : cellule dans le masque si `MNS > ALTITUDE`
   (paramètre), ou si `MNS <= ALTITUDE` en mode `--inverse` (voir plus
   bas). Le relief seul (MNH ≈ 0) est capté dès qu'il dépasse
   le seuil — c'est la différence avec le Poc 02.
3. **Vectorisation** : `gdal_polygonize` → MultiPolygon avec trous.
4. **Nettoyage** : optionnel, filtrage des polygones d'aire <
   `--aire-mini` (défaut **0 : tout conserver**) ; simplification
   Douglas-Peucker (5 m).
5. **Sortie** : GeoJSON WGS84 (`EPSG:4326`), prêt pour une couche
   `fill` MapLibre ; chaque polygone porte les attributs décrits
   ci-dessous, et la `FeatureCollection` embarque les paramètres du
   run (`altitude_m`, `zone_l93`, `aire_mini_m2`, `date_generation`,
   `centre_lat`, `centre_lon` — centre WGS84 de la zone analysée).

## Mode inverse (`--inverse` / `INVERSE=1`)

`make masque ALTITUDE=95 INVERSE=1` dessine l'exact opposé : les
features représentent **tout ce qui est en dessous de ALTITUDE** —
typiquement les zones qu'un observateur à cette altitude dominerait
(zones en contrebas, potentiellement servables), les masses
au-dessus devenant des trous du polygone dominant.

- **Complémentarité stricte** : le mode direct teste `MNS > ALTITUDE`,
  le mode inverse `MNS <= ALTITUDE` — une cellule exactement à
  ALTITUDE (fréquent avec des altitudes entières Int16) est comptée
  « en dessous ». La réunion des deux masques couvre 100 % de la zone.
- **Forme de la sortie** : à ALTITUDE proche du niveau moyen du terrain,
  le masque inverse est un **polygone dominant couvrant presque toute
  la zone**, parsemé de trous (les masses au-dessus) — le GeoJSON est
  plus volumineux que le masque direct.
- Les aires (`aire_m2`) déduisent les trous (anneaux internes).
- Les métadonnées de run embarquent `inverse: true|false`.

Note : le temps de traitement est proportionnel à la taille de la zone
ingérée dans le Poc 01 — c'est normal et attendu. La lecture MNS est
découpée en tuiles de 2048 x 2048 cellules pour que la RAM de lecture
reste bornée quelle que soit la taille de la zone. Seul le VRT MNS est
lu (pas de MNT) : le temps de lecture est moitié moindre que le Poc 02.

## Attributs des features

| Attribut | Description |
|---|---|
| `aire_m2` | Surface du polygone en m² — emprise au sol de la zone au-dessus du seuil. |
| `mns_min_m` | Altitude absolue (NGF) minimale des cellules du polygone — altitude à laquelle la masse « commence » au-dessus du seuil (proche du seuil si le terrain y pénètre doucement). |
| `mns_moy_m` | Altitude absolue moyenne des cellules — ordre de grandeur de la masse (colline, plateau urbain). |
| `mns_max_m` | Altitude absolue du point le plus haut — directement le candidat « point haut » pour un répéteur, comparable entre polygones. |

## Outils

Depuis `backend/poc03` :

```bash
make masque                       # ALTITUDE=200 par défaut
make masque ALTITUDE=250          # tout ce qui dépasse 250 m NGF
make masque ALTITUDE=215 OUT=test215.geojson   # fichier de sortie nommé
make masque ALTITUDE=95 INVERSE=1 # tout ce qui est en dessous de 95 m NGF
# ou directement :
python3 scripts/masque_altitude.py --altitude 215 --out masque.geojson
python3 scripts/masque_altitude.py --altitude 95 --inverse --out dessous.geojson
```

Paramètres :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `--altitude` | (obligatoire) | altitude absolue NGF (m) au-delà de laquelle une cellule est dans le masque (en dessous en mode inverse) |
| `--inverse` | (off) | masque inverse : cellules avec `MNS <= ALTITUDE` (tout ce qui est en dessous) |
| `--aire-mini` | 0 | aire minimale d'un polygone (m²), trous déduits — 0 = tout conserver |
| `--tuile` | 2048 | côté d'une tuile de lecture (cellules) — borne la RAM de lecture |
| `--out` | masque.geojson | fichier de sortie |

Note mémoire : la lecture et les stats sont découpées en tuiles, mais
les grilles MNS/masque restent en RAM (~6 octets/cellule, soit ~2,9 Go
pour la zone de test 36 x 54 km à 2 m — contre ~4,4 Go au Poc 02 qui
gardait aussi le MNH). C'est le pipeline minimal pour garder un GeoJSON
strictement identique (polygonize sur le masque complet, zones jamais
coupées entre tuiles).

## Prérequis

Ceux du Poc 01 (`make -C ../poc01 doctor`), plus `gdalinfo` et
`gdaltransform` (inclus dans `gdal-bin`).

Les données doivent être ingérées (`make -C ../poc01 download ingest vrt`).
