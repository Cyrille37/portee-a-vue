# Poc 01

Document de référence: [masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md](../../masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md)

## Prérequis

Tous les outils sont gratuits et standard ; rien d'autre n'est indispensable
pour ce PoC (pas de Node/MapLibre — frontend existant hors périmètre, ni de
WhiteboxTools — points hauts = plus tard, ni de PostgreSQL/QGIS — même si QGIS
est pratique pour inspecter visuellement les tuiles).

| Outil | Rôle dans le PoC | Version mini |
|---|---|---|
| **GDAL** (`gdalwarp`, `gdalbuildvrt`, `gdallocationinfo`, `gdal_polygonize`) | Ingestion 2 m, VRT, échantillonnage, vectorisation | ≥ 3.4 (testé 3.4.1) |
| **Python 3** | Scripts de calcul (carroyage, profil, Fresnel, tests) | ≥ 3.10 (testé 3.10) |
| **numpy** (paquet Python) | Calcul vectorisé des seuils/profils | ≥ 1.21 (testé 1.21.5) |
| **sqlite3** | Base métadonnées | 3.x (testé 3.37.2) |
| **curl** + **unzip** | Téléchargement dalles via l'API Atom | système |

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

| **MNS LiDAR HD (50 cm)** — surface : bâti + végétation | **Source principale du socle** : masque d'altitude, obstacles des profils | À la carte `cartes.gouv.fr/telechargement/IGNF_MNS-LIDAR-HD` ou API Atom `https://data.geopf.fr/telechargement` (10 req/s) | Dalles 1 km², ~24 Mo ; 126–190 Go pour un disque de 50 km |
| **MNT LiDAR HD (50 cm)** — sol nu | Altitude du sol aux sites A/B (base du mât), séparation relief/sursol | Même canal (`IGNF_MNT-LIDAR-HD`) | ~24 Mo/dalle 50 cm (version 5 m : ~0,5 Mo) |

## De la dalle IGN à votre tuile

Les tuiles 2 m sont des **produits dérivés** ; les MNS/MNT 50 cm sont leurs **sources** :

1. téléchargement d'une dalle IGN (GeoTIFF 1 km², ~24 Mo, 2 000×2 000 px) ;
2. transformation `gdalwarp -r max -tr 2 2 -ot Int16 -ovr NONE` → tuile dérivée 500×500 px, 0,5 Mo, même emprise ;
3. suppression de la source 50 cm ;
4. la tuile garde le nom et l'emprise de la dalle IGN — le carroyage national devient l'index.

MNS et MNT sont ingérés de la même façon dans des sous-répertoires (`mns/`, `mnt/`) sur le même carroyage ; le MNH n'est jamais stocké : il se calcule à la demande par différence (MNS − MNT).

