# PoC03 - Masque d'altitude absolue
# Réutilise les données du PoC01 (backend/data/mns.vrt)
# La zone d'exploration = l'emprise du VRT

ALTITUDE ?= 200
INVERSE ?= 0
OUT ?= masque.geojson
AIRE_MINI ?= 0

.PHONY: doctor masque help

help:
	@echo "Cibles: doctor | masque [ALTITUDE=200] [INVERSE=0] [AIRE_MINI=0] [OUT=masque.geojson]"

doctor:
	@for t in gdal_translate gdalinfo gdal_rasterize ogr2ogr gdaltransform python3; do \
	  command -v $$t >/dev/null || { echo "outil manquant: $$t (apt install gdal-bin python3)"; exit 1; }; \
	done
	@command -v gdal_polygonize >/dev/null || command -v gdal_polygonize.py >/dev/null \
	  || { echo "outil manquant: gdal_polygonize ou gdal_polygonize.py (apt install gdal-bin)"; exit 1; }
	@python3 -c "import numpy; print('numpy', numpy.__version__)" \
	  || { echo "numpy manquant (apt install python3-numpy)"; exit 1; }
	@gdalinfo --version
	@echo "OK"

masque:
	@if [ "$(INVERSE)" = "1" ]; then INV="--inverse"; else INV=""; fi; \
	 python3 scripts/masque_altitude.py --altitude $(ALTITUDE) $$INV --aire-mini $(AIRE_MINI) --out $(OUT)
