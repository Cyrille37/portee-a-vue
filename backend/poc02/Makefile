# PoC02 - Masque d'altitude
# Réutilise les données du PoC01 (backend/data/*.vrt)
# La zone d'exploration = l'emprise des VRT (plus de centre/rayon en dur)

SEUIL ?= 10
OUT ?= masque.geojson
AIRE_MINI ?= 0

.PHONY: doctor masque help

help:
	@echo "Cibles: doctor | masque [SEUIL=10] [AIRE_MINI=0] [OUT=masque.geojson]"

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
	@python3 scripts/masque.py --seuil $(SEUIL) --aire-mini $(AIRE_MINI) --out $(OUT)
