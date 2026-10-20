#!/usr/bin/env bash
# PoC01 - Téléchargement des dalles LiDAR HD (MNS/MNT) via le service WMS-R
# Usage: scripts/download.sh <produit: MNS|MNT> <dalle: 0525_6705>
set -euo pipefail

produit="${1:?usage: download.sh <MNS|MNT> <XXXX_YYYY>}"
dalle="${2:?usage: download.sh <MNS|MNT> <XXXX_YYYY>}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
X="${dalle%%_*}"; Y="${dalle##*_}"   # nom = coin NW (ouest X km, nord Y km)

# BBOX numerique : jamais de concatenation de chaine sur les noms paddes
# (0524 -> 0524999.75 serait lu 524999.75, i.e. +1 km).
west=$(awk -v x=$((10#${X}))     'BEGIN{printf "%.2f", x*1000-0.25}')
east=$(awk -v x=$((10#${X}+1))   'BEGIN{printf "%.2f", x*1000-0.25}')
south=$(awk -v y=$((10#${Y}-1))  'BEGIN{printf "%.2f", y*1000+0.25}')
north=$(awk -v y=$((10#${Y}))    'BEGIN{printf "%.2f", y*1000+0.25}')

URL="https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&EXCEPTIONS=text/xml&REQUEST=GetMap"
URL+="&LAYERS=IGNF_LIDAR-HD_${produit}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93"
URL+="&FORMAT=image/geotiff&STYLES=&CRS=EPSG:2154"
URL+="&BBOX=${west},${south},${east},${north}"
URL+="&WIDTH=2000&HEIGHT=2000"
URL+="&FILENAME=LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"

dst="${ROOT}/data/downloads/LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"
mkdir -p "${ROOT}/data/downloads"

# sauter si la tuile est deja ingeree (evite de surcharger l'IGN)
tuile="${ROOT}/data/${produit,,}/LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"
if [ -f "${tuile}" ]; then
  echo "Déjà ingérée, saut: ${tuile}"
  exit 0
fi

# Limites d'usage de la Géoplateforme : le WMS-R est limite a 40 req/s par IP,
# reponse HTTP 429 (blocage 5 s) au-dela. Throttling : requetes sequentielles
# + pause inter-dalles + retry curl avec backoff sur les erreurs transitoires.
PAUSE_S="${DOWNLOAD_PAUSE_S:-1}"

if [ -f "${dst}" ]; then
  echo "Déjà téléchargée, saut: ${dst}"
  exit 0
fi

echo "Téléchargement ${produit} ${dalle} -> ${dst}"
curl --fail --silent --show-error --location --retry 5 --retry-delay 2 --retry-all-errors \
  --output "${dst}" "${URL}"
sleep "${PAUSE_S}"

# integrite minimale: une dalle valide fait ~15-25 Mo ; un corps d'erreur
# WMS-R n'en fait que quelques Ko et ne doit jamais etre accepte
TAILLE_MIN=10000000  # 10 Mo
if [ "$(stat -c%s "${dst}")" -lt "${TAILLE_MIN}" ]; then
  echo "Dalle suspecte (${dst} trop petite), suppression" >&2
  rm -f "${dst}"
  exit 1
fi

ls -lh "${dst}"
