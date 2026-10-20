# Poc 01

Document de référence: [masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md](../../masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md)

**Zone du PoC** : quartier de l'Europe, Tours — définie dans **`zone.env`**
(point central WGS84 `LAT`/`LON` + rayon `RAYON_M`). La liste des dalles
n'est plus écrite nulle part : `scripts/zone.py` convertit le point en
Lambert-93 (via `gdaltransform`, fallback `pyproj`) et calcule les dalles
1 km² dont l'emprise touche le disque de rayon `RAYON_M` — avec le point
actuel (47.422648 / 0.683287, rayon 1 km) cela redonne les 7 dalles
`0524_6705 … 0526_6706`.

**Changer de zone ou de superficie** = éditer `zone.env` (2 valeurs :
point + rayon) puis relancer `make download ingest vrt check` — le
Makefile, `check.py` et `check_remote.py` consomment tous `scripts/zone.py`
(source unique).

**Convention de carroyage (validée sur les données)** : le nom d'une dalle
encode son coin **NW** — ouest `X*1000`, nord `Y*1000`. D'où le BBOX WMS-R :
`{X}999.75,{Y-1}000.25,{X+1}999.75,{Y}000.25`
(ex. `0525_6706` → `524999.75,6705000.25,525999.75,6706000.25`).

## Prérequis

Tous les outils sont gratuits et standard ; rien d'autre n'est indispensable
pour ce PoC (pas de Node/MapLibre — frontend existant hors périmètre, ni de
WhiteboxTools — points hauts = plus tard, ni de PostgreSQL/QGIS — même si QGIS
est pratique pour inspecter visuellement les tuiles).

| Outil | Rôle dans le PoC | Version mini |
|---|---|---|
| **GDAL** (`gdalwarp`, `gdalbuildvrt`, `gdallocationinfo`, `gdaltransform`, `gdal_edit`/`gdal_edit.py`) | Ingestion 2 m, VRT, échantillonnage, reprojection, balises | ≥ 3.4 (testé 3.4.1) |
| **Python 3** | Scripts de calcul (carroyage, profil, Fresnel, tests) | ≥ 3.10 (testé 3.10) |
| **numpy** (paquet Python) | Calcul vectorisé des seuils/profils | ≥ 1.21 (testé 1.21.5) |
| **sqlite3** | Base métadonnées (étape suivante) | 3.x (testé 3.37.2) |
| **curl** | Téléchargement des dalles (WMS-R) | système |

Installation selon l'OS :

- **Debian/Ubuntu** : `sudo apt install gdal-bin python3 python3-numpy sqlite3 curl unzip`
- **macOS (Homebrew)** : `brew install gdal python numpy sqlite3 curl`
- **Windows** : installateur OSGeo4W (GDAL officiel, inclut Python) — ou WSL2 + commandes Debian ci-dessus

Vérification :

```bash
gdalinfo --version                    # GDAL 3.x
python3 -c "import numpy; print(numpy.__version__)"
sqlite3 --version
```

À partir des sources :

| Produit | Rôle dans le PoC | Accès | Volumétrie constatée |
|---|---|---|---|
| **MNS LiDAR HD (50 cm)** — surface : bâti + végétation | Source principale du socle : obstacles des profils, sursol | WMS-R (voir section suivante) | dalle 1 km² ≈ 16 Mo |
| **MNT LiDAR HD (50 cm)** — sol nu | Altitude du sol aux sites A/B (base du mât), séparation relief/sursol | WMS-R (même canal, couche MNT) | dalle 1 km² ≈ 16 Mo |

## De la dalle IGN à votre tuile

Les tuiles 2 m sont des **produits dérivés** ; les MNS/MNT 50 cm sont leurs **sources** :

1. téléchargement d'une dalle IGN (GeoTIFF 1 km², ~16 Mo, 2 000×2 000 px, float32) ;
2. transformation `gdalwarp -r max -tr 2 2 -ot Int16 -ovr NONE` → tuile dérivée 500×500 px, ~491 Ko, même emprise ;
3. suppression de la source 50 cm ;
4. la tuile garde le nom et l'emprise de la dalle IGN — le carroyage national devient l'index.

MNS et MNT sont ingérés de la même façon dans des sous-répertoires (`mns/`, `mnt/`) sur le même carroyage ; le MNH n'est jamais stocké : il se calcule à la demande par différence (MNS − MNT).

## Téléchargement des dalles (découverte clé)

Les produits MNS/MNT LiDAR HD **ne sont pas diffusés via l'API Atom**
`data.geopf.fr/telechargement` (seuls les nuages de points y figurent,
dataset `LiDARHD-NUALID`). L'accès programme aux dalles MNS/MNT passe par :

- le **WFS `IGNF_LIDAR-HD_METADONNEE:metadata`**
  (`https://data.geopf.fr/wfs/ows`) qui liste les 524 687 dalles avec,
  pour chacune, les attributs `url_mns`, `url_mnt`, `url_mnh`, `url_npl`,
  `code_mission`, dates d'acquisition, capteur… ;
- le **service WMS-R** (`https://data.geopf.fr/wms-r`) qui sert chaque dalle
  en GeoTIFF (2000×2000 px, pas 50 cm, float32, nodata −9999) via un GetMap
  dérivé par arithmétique du carroyage (coin NW) :
  `BBOX = {X}999.75,{Y-1}000.25,{X+1}999.75,{Y}000.25`
  (ex. `0525_6706` → `524999.75,6705000.25,525999.75,6706000.25`).

Les tuiles sont donc téléchargées par WMS-R direct (moins d'indirection),
le WFS métadonnées restant la source des attributs de traçabilité (mission,
dates de vol).

## Outils du PoC

Depuis `backend/poc01` :

- `make doctor` — vérifie les prérequis ;
- `make download` — télécharge les 7 dalles MNS + MNT (~16 Mo chacune)
  dans `backend/data/downloads/` (flux « une dalle à la fois ») ;
- `make ingest` — transforme chaque dalle en tuile 2 m Int16
  (`gdalwarp -r max -tr 2 2 -ot Int16 -ovr NONE`) avec balises de
  traçabilité, supprime la source 50 cm ;
- `make vrt` — assemble `backend/data/mns.vrt` et `mnt.vrt` ;
- `make check` — contrôle qualité hors-ligne des 14 tuiles : 500×500 px,
  pas 2 m, Int16, origine alignée sur la dalle 1 km², balises
  `SOURCE_*`/`INGEST_*`, cohérence MNS ≥ MNT, couverture du disque 1 km
  sans trou (géométrie recalculée depuis le point Europe), et altitude au
  point Europe via `gdallocationinfo` sur les VRT (s'ils sont construits) ;
- `make check-remote` — croisement en ligne avec l'API altimétrie IGN
  (vérité terrain) : 10 points aléatoires reproductibles dans la zone,
  comparaison VRT 2 m max-poolé vs LiDAR HD 50 cm, tolérance 5 m ;
- scripts unitaires : `scripts/download.sh <MNS|MNT> <XXXX_YYYY>`,
  `scripts/ingest.sh <MNS|MNT> <XXXX_YYYY>`.

## Balises de traçabilité

Posées après le `gdalwarp` par `gdal_edit -mo`
(sur Ubuntu 22.04 le binaire s'appelle `gdal_edit.py` — le script gère
le fallback) :

```text
SOURCE_PRODUIT=MNS_LIDAR_HD
SOURCE_DALLE=LHD_FXX_0525_6706
SOURCE_PAS=0.5m
INGEST_DATE=2026-10-19
INGEST_OUTIL=gdalwarp 3.4.1 / r=max, tr=2m, Int16
```

Vérification : `gdalinfo ../data/mns/LHD_FXX_0525_6706_MNS_O_0M50_LAMB93_IGN69.tif | grep -E "SOURCE|INGEST"`

## Notes d'exécution (retours réels)

- volumétrie constatée : dalle 50 cm ≈ 16 Mo ; tuile 2 m Int16 ≈ 491 Ko ;
  14 dalles (7 MNS + 7 MNT) ingérées sans erreur ;
- le WMS-R peut renvoyer une `400` transitoire (limite de débit) : le
  `curl --retry-all-errors --retry 3` la rejoue ; si une dalle manque,
  relancer `make download` (idempotent) ;
- attention : `gdalwarp` ne connaît pas `-mo` (erreur `ERROR 6: Unknown
  option name '-mo'`) — d'où le `gdal_edit` séparé ;
- les boucles `download`/`ingest` du Makefile sont *fail-fast* : une dalle
  manquante arrête l'ingestion plutôt que de supprimer une source non
  transformée ;
- `gdalinfo -stats` (donc `make check`) dépose des `.tif.aux.xml` à côté des
  tuiles : cache GDAL des statistiques, régénérable, ignoré par git,
  supprimé par `make clean` ;
- `download.sh` et `ingest.sh` sont **idempotents** : une dalle déjà
  téléchargée (ou déjà ingérée en tuile) est sautée — relancer `make
  download` / `make ingest` ne re-télécharge rien et ne surcharge pas le
  service IGN ; `make clean` ne supprime que sur demande explicite.

## Vérifications faites sur la dalle du point (0525_6706, BBOX
524999.75–525999.75 / 6705000.25–6706000.25)
GeoTIFF 2000×2000 float32, z sol = 99,35 m NGF au point Europe
(MNS = MNT : point en rue, pas de sursol), max MNS 129 m (bâti),
max MNT 103 m — croisé avec l'API altimétrie IGN : 99,33 m.

⚠ Correction de convention : le nom de dalle encode le coin **NW**
(ouest X km, nord Y km), pas le coin sud-ouest. La première version des
scripts décalait le BBOX de +1 km en X et Y ; les dalles étaient
téléchargées 1 km trop à l'est et au nord. Corrigé et validé par croisement
tuile / API altimétrie (99,35 vs 99,33 m).

## Résultat du croisement `make check-remote` (réel, 2026-10-19)

10 points aléatoires dans la zone, VRT 2 m max-poolé vs API altimétrie
IGN (LiDAR HD 50 cm) : **écart max 0,65 m, moyen 0,33 m** — attendu,
le max-pooling 2 m et l'arrondi Int16 expliquant l'ordre de grandeur.
Le socle (téléchargement → ingestion → VRT → lecture) est donc validé
de bout en bout sur la zone du PoC.

`make doctor` vérifie tous les binaires requis : `gdalinfo`, `gdalwarp`,
`gdalbuildvrt`, `gdallocationinfo`, `gdaltransform`, `gdal_edit`/`gdal_edit.py`,
`curl`, `python3`+`numpy`.

