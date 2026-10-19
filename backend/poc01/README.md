# Poc 01

Document de référence: [masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md](../../masque-d-altitude-&-profils-a↔b-socle-terrain-pour-répéteurs-meshcore.md)

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

