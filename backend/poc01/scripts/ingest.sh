#!/usr/bin/env bash
# PoC01 - Ingestion d'une dalle 50 cm en tuile 2 m Int16 (max-pooling)
# Usage: scripts/ingest.sh <produit: MNS|MNT> <dalle: 0525_6705>
set -euo pipefail

produit="${1:?usage: ingest.sh <MNS|MNT> <XXXX_YYYY>}"
dalle="${2:?usage: ingest.sh <MNS|MNT> <XXXX_YYYY>}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
X="${dalle%%_*}"; Y="${dalle##*_}"

src="${ROOT}/data/downloads/LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"
dst_dir="${ROOT}/data/${produit,,}"
dst="${dst_dir}/LHD_FXX_${X}_${Y}_${produit}_O_0M50_LAMB93_IGN69.tif"

[ -f "${src}" ] || { echo "Dalle source absente: ${src}"; exit 1; }
mkdir -p "${dst_dir}"

# sauter si la tuile existe deja (idempotence) ; sinon l'ingérer
# en une étape atomique: si gdalwarp ou gdal_edit echoue, la tuile
# partielle est supprimee pour ne pas empoisonner les relances
if [ -f "${dst}" ]; then
  echo "Tuile déjà présente, saut: ${dst}"
  exit 0
fi
trap 'rm -f "${dst}"' ERR

gdalwarp -r max -tr 2 2 -ot Int16 -ovr NONE -q \
  "${src}" "${dst}"

GDAL_EDIT="gdal_edit"
command -v gdal_edit >/dev/null || GDAL_EDIT="gdal_edit.py"

"${GDAL_EDIT}" -mo "SOURCE_PRODUIT=${produit}_LIDAR_HD" \
  -mo "SOURCE_DALLE=LHD_FXX_${X}_${Y}" \
  -mo "SOURCE_PAS=0.5m" \
  -mo "INGEST_DATE=$(date +%F)" \
  -mo "INGEST_OUTIL=gdalwarp $(gdalinfo --version | grep -o '[0-9.]*') / r=max, tr=2m, Int16" \
  "${dst}"

rm -f "${src}"
ls -lh "${dst}"
