#!/usr/bin/env bash
# PoC01 - Téléchargement des dalles LiDAR HD (MNS/MNT) via le service WMS-R
# Usage: scripts/download.sh <produit: MNS|MNT> <dalle: 0525_6705>
set -euo pipefail

produit="${1:?usage: download.sh <MNS|MNT> <XXXX_YYYY>}"
dalle="${2:?usage: download.sh <MNS|MNT> <XXXX_YYYY>}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
X="${dalle%%_*}"; Y="${dalle##*_}"

URL="https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&EXCEPTIONS=text/xml&REQUEST=GetMap"
URL+="&LAYERS=IGNF_LIDAR-HD_${produit}_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93"
URL+="&FORMAT=image/geotiff&STYLES=&CRS=EPSG:2154"
URL+="&BBOX=${X}999.75,${Y}000.25,$((10#${X}+1))999.75,$((10#${Y}+1))000.25"
URL+="&WIDTH=2000&HEIGHT=2000"
URL+="&FILENAME=LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"

dst="${ROOT}/data/downloads/LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"
mkdir -p "${ROOT}/data/downloads"

echo "Téléchargement ${produit} ${dalle} -> ${dst}"
curl --fail --silent --show-error --location --retry 3 \
  --output "${dst}" "${URL}"

ls -lh "${dst}"
