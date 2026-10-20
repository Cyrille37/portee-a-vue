# Poc 04 — Viewshed R3/Wang (rayons radiaux)

Réutilise le socle du [Poc 01](../poc01/README.md) (tuiles 2 m Int16, VRT)
pour calculer la **surface de vue directe** (viewshed) d'un observateur :
l'ensemble des cellules du MNS visibles depuis un point central, sur un
**grand rayon** (20 à 40 km) adapté à la radio LoRa — quand la géométrie
le permet, un lien LoRa se cale sur des portées de plusieurs dizaines de
kilomètres, d'où la contrainte de rayon qui distingue ce PoC d'un
viewshed « cartographique » classique.

Algorithme : **R3** (Wang, Robinson & White, 2000) — l'observateur est le
centre d'un disque d'analyse découpé en **rayons réguliers** ; le long de
chaque rayon on avance du centre vers l'extérieur en mémorisant la
**pente tangente maximale** rencontrée (angle d'élévation), et une cellule
est visible si son angle d'élévation dépasse ce maximum courant. O(nb_rayons ×
pas), très rapide, et le coût mémoire est borné par la seule fenêtre
MNS du disque.

Visible si (z_cellule + cible − z_observateur) / d ≥ tan_max_courant
- `--cible 0` : visibilité du sol nu (c'est le viewshed cartographique classique) ;
- `--cible 1.5` : visibilité d'un pair LoRa posé au sol, antenne à 1,5 m — décalage de tout le disque de 1,5 m vers le haut ;
- `--cible 30` : couverture d'abonnés avec mât de 30 m.

## Paramètres

| Paramètre | Défaut | Rôle |
|---|---|---|
| `--lat` `--lon` | (obligatoire) | point central de l'observateur (WGS84) |
| `--hauteur` | 2.0 | hauteur de l'antenne au-dessus du sol (m) — l'altitude MNS au centre est lue dans le VRT, `Z0 = MNS_centre + hauteur` |
| `--rayon` | 10000 | rayon du disque d'analyse (m) — jusqu'à 40 km pour la LoRa |
| `--angle` | 0.1 | angle de numérisation Δθ entre deux rayons (degrés) — voir « Choix de l'angle » |
| `--cible` | 0.0 | hauteur ajoutée à chaque cellule observée (m) — ex. 1.5 pour un pair LoRa posé au sol |
| `--k` | 1.1667 (7/6) | coefficient de réfraction effectif appliqué à la courbure : `R_eff = k·R_T` (7/6 ≈ 1.1667 = standard radio, équivalent `-cc 0.85714` de `gdal_viewshed` ; k = 1.0 → aucune correction) |
| `--pas-loin` | 10.0 | pas d'échantillonnage au bord du disque (m) — le pas croît linéairement de la résolution de la grille près du centre à `--pas-loin` à `--rayon` |
| `--aire-mini` | 0.0 | aire minimale d'un polygone visible en m², trous déduits — 0 = tout conserver |
| `--out` | viewshed.geojson | fichier GeoJSON de sortie |

## Choix de l'angle (précision)

L'erreur de R3 au bord du disque vaut environ `R·Δθ` (corde entre deux
rayons) et est **asymétrique** : une cellule entre deux rayons peut être
déclarée visible à tort (faux positif), presque jamais l'inverse. Pour de
la planification radio c'est l'erreur la moins pénalisante — mieux vaut
une zone optimiste qu'un faux « impossible ».

La règle : **Δθ < largeur_minimale_obstacle / R**. Un obstacle qui peut
vraiment bloquer un lien à 30 km (crête, bourg, lisière) fait
100–200 m de large :

| Rayon | Obstacle ≥ 200 m | Marge ×2 | Rayons (360/Δθ) |
|---|---|---|---|
| 20 km | Δθ ≤ 0.57° | Δθ ≤ 0.29° | ~1 250 |
| 40 km | Δθ ≤ 0.29° | Δθ ≤ 0.14° | ~2 500 |

Défaut **0.1°** (3 600 rayons) : dans la zone utile, sans coût déraisonnable.
En dessous de ~0.05° on ne gagne plus rien de physique ; au-dessus de
~0.3° apparaissent les artefacts en étoile (faux positifs en éventail
entre les rayons). Le test de sensibilité recommandé : relancer le même
centre à 0.3° / 0.1° / 0.05° et comparer les taux de visibilité par
anneau de distance — quand ils se stabilisent, l'angle est bon pour ce
terrain.

## Principe

1. **Entrée** : VRT MNS du Poc 01 (`backend/data/mns.vrt`) ; observateur
   défini par `--lat/--lon` (converti en Lambert-93), son altitude est
   lue dans le MNS au point central.
2. **Fenêtre** : lecture de la fenêtre MNS carrée `[centre ± rayon]`
   au pas de la grille (2 m) — c'est la seule lecture raster, et le masque
   de sortie est aligné sur cette même grille. La RAM de travail reste
   bornée : MNS float32 + masque (environ 5 octets/cellule, soit ~5 Go
   pour une fenêtre 40 km × 40 km à 2 m — la fenêtre excédant la couverture
   du VRT est lue comme nodata et reste invisible).
3. **Rayons** : pour chaque angle `θ = 0, Δθ, 2Δθ, …`, on échantillonne
   le MNS le long du rayon du centre (`d = 0`) au bord (`d = R`) avec un
   **pas croissant** (`résolution` → `--pas-loin`), interpolation
   bilinéaire ; chaque échantillon est corrigé de la courbure terrestre
   avec réfraction : `z_corr = z − d²/(2·k·R_T)`.
4. **Marquage** : l'échantillon est **visible** si `(z + cible − z0) / d >
   tan_max_courant` ; sinon invisible. Dans tous les cas
   `tan_max_courant = max(tan_max, (z − z0) / d)`. Le rayon contribue
   à un masque binaire (échantillons visibles → cellules marquées).
5. **Fusion sur la grille** : chaque cellule du disque est évaluée par son
   rayon le plus proche à sa distance (assignation inverse, standard R3,
   vectorisée NumPy et découpée en tuiles pour borner la RAM) — l'erreur
   R3 étant à faux positifs, une cellule entre deux rayons hérite du
   verdict du rayon voisin, ce qui majore légèrement la zone visible,
   mais c'est cohérent avec l'usage planification.
6. **Vectorisation** : `gdal_polygonize` sur le masque binaire
   (cellules visibles), reprojection en WGS84, simplification
   Douglas-Peucker (5 m) — même pipeline que le Poc 03.
7. **Sortie** : GeoJSON WGS84 prêt pour une couche `fill` MapLibre, avec
   les paramètres du run dans la `FeatureCollection` (voir ci-dessous),
   plus un tableau de **visibilité par anneau de distance** (100 m,
   500 m, 1 km, 5 km, 10 km, 20 km…) imprimé et embarqué — le tableau
   de bord utile en LoRa.

### Courbure terrestre + réfraction : obligatoire à 20–40 km

La dépression de l'horizon vaut `d²/(2·R_T)` (~125 m à 40 km seul,
~146 m avec réfraction k = 7/6) : **sans correction, le viewshed à
grande distance est complètement faux** — des zones basses lointaines
paraissent visibles alors qu'elles sont sous l'horizon géodésique.
C'est exactement la correction `-cc 0.85714` de `gdal_viewshed`
(équivalent : `k = 7/6`). À titre d'horizon radio : un observateur à
30 m voit l'horizon géodésique (avec réfraction) à ~20 km.

### Pas d'échantillonnage adaptatif

La pente tangente max est une fonction lisse : un relief de 200 m de
large à 30 km est correctement échantillonné au pas 20 m. Le pas croît
linéairement de la résolution de la grille (2 m) près du centre à
`--pas-loin` (défaut 10 m) au bord du disque — le nombre d'échantillons
par rayon passe de `R/2` à ~`R/6` à 40 km, et le coût total reste en
quelques secondes (R3 vectorisé NumPy).

## Attributs des features

| Attribut | Description |
|---|---|
| `aire_m2` | Surface du polygone visible en m², trous déduits |
| `anneaux` | (dans les propriétés de la FeatureCollection) visibilité par anneau de distance : `[{distance, cellules_visibles, cellules_total, pct}]` |

## Outils

Depuis `backend/poc04` :

```bash
make viewshed LAT=47.810322 LON=0.983288 RAYON=40000 ANGLE=0.1
make viewshed LAT=47.810322 LON=0.983288 RAYON=20000 HAUTEUR=30 OUT=test20k.geojson
# sensibilité de l'angle :
make viewshed ... ANGLE=0.3 OUT=vs_03.geojson
make viewshed ... ANGLE=0.05 OUT=vs_005.geojson
# ou directement :
python3 scripts/viewshed_r3.py --lat 47.810322 --lon 0.983288 --rayon 40000
```

## Différence avec le Poc 03 (masque d'altitude)

| | Poc 03 | Poc 04 |
|---|---|---|
| Question | « où sont les masses plus hautes que l'observateur ? » | « quelles zones au sol sont vues par l'observateur ? » |
| Test par cellule | `MNS > ALTITUDE` (statique, une seule comparaison) | comparaison à la **ligne de vue** depuis le centre (géométrie, courbure) |
| Sortie | obstacles (masque) | surface visible (viewshed) |
| Coût | lecture complète de la zone + polygonize | fenêtre du disque + rayons + polygonize |
| Complémentarité | les zones du masque Poc 03 (relief haut) sont **a priori** les bords du viewshed Poc 04 | idem |

Les deux répondent au même besoin radio (où placer un répéteur) avec des
angles différents : le masque dit **ce qui bloque**, le viewshed dit
**ce qui est servi**. Le viewshed R3 avait été écarté en octobre 2026
(cf. le doc de besoin) au profit du masque ; ce PoC le réintroduit
volontairement pour valider l'algorithme R3 sur le même socle —
l'archive de l'implémentation précédente (branche `archive-viewshed-r3-wang`)
n'est plus poussée sur le remote.

## Comparaison avec `gdal_viewshed` (test croisé)

`gdal_viewshed` est une implémentation R3 validée — un test croisé sur
la même fenêtre vérifie l'implémentation maison : aux mêmes paramètres,
les deux masques doivent être quasi identiques (écarts attendus sur les
bords : angle de numérisation interne différent, échantillonnage
adaptatif maison).

Correspondance des paramètres (notre implémentation → `gdal_viewshed`) :

| Notre paramètre | Équivalent `gdal_viewshed` | Note |
|---|---|---|
| `--hauteur` (antenne) | `-oz` = altitude du centre + hauteur | le run maison affiche « observateur à Z m NGF » — reprendre ce Z pour `-oz` |
| `--cible` (hauteur cible) | `-tz` | 0 = sol |
| `--k` = 7/6 (réfraction) | `-cc` = 6/7 ≈ 0.85714 | `-cc` = 1/k : 0.85714 est exactement k = 7/6 |
| `--rayon` | `-r` | mètres (coordonnées terrain) |
| position du centre | `-ox`/`-oy` | en **pixels** depuis le coin haut-gauche (pas en coordonnées terrain) |

Commandes — depuis `backend/poc04`, après un run du script qui affiche
l'altitude de l'observateur (`observateur à Z m NGF`, ligne à reprendre
pour `-oz`) :

```bash
# 1. l'implémentation maison (sortie: viewshed.geojson + stats par anneau)
#    — note la ligne « observateur à Z m NGF » : reprendre Z pour -oz ci-dessous
make viewshed LAT=47.810322 LON=0.983288 RAYON=40000 HAUTEUR=30 OUT=vs40k.geojson

# 2. la fenêtre MNS du disque, même géométrie que la maison :
#    centre L93 (affiché par le run) +- RAYON — adapter ulx uly lrx lry
gdal_translate -projwin <CX-R> <CY+R> <CX+R> <CY-R> \
  ../data/mns.vrt fenetre40k.tif

# 3. gdal_viewshed sur la même fenêtre — -ox/-oy en PIXELS depuis le
#    coin haut-gauche : R / pas (ex. 40000 / 2 = 20000)
gdal_viewshed fenetre40k.tif vs40k_gdal.tif \
  -ox 20000 -oy 20000 \
  -oz 127 -tz 0 \
  -cc 0.85714 -r 40000 \
  -om NORMAL
```

Notes :

- `-ox/-oy` sont en **pixels** depuis le coin haut-gauche (pas en
  coordonnées terrain) : pour un centre à `R` du bord, c'est `-ox R/pas
  -oy R/pas` (ex. 40 km / 2 m = 20000) ; `-oz` en unités du MNT (m NGF).
- `gdal_viewshed` utilise le **MNS** qu'on lui donne : la même fenêtre
  `fenetre40k.tif` est donc la référence commune aux deux runs.
- `-om NORMAL` donne 1 = visible / 0 = invisible, comparable au masque
  binaire de la maison avant polygonisation.
- Le désaccord attendu se concentre près des frontières de visibilité
  (cellules limites) et aux grands angles entre rayons de la maison
  (fusion « au moins un rayon » légèrement optimiste) ; un taux de
  désaccord global de quelques % valide l'implémentation.

## Prérequis

Ceux du Poc 01 (`make -C ../poc01 doctor`), `gdalinfo` et `gdaltransform`
(inclus dans `gdal-bin`), `numpy` (non fourni par `gdal-bin` :
`apt install python3-numpy`), et `gdal_viewshed` pour le test croisé
(ci-dessus).

Les données doivent être ingérées (`make -C ../poc01 download ingest vrt`).
