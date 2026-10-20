# PoC04 - Viewshed R3/Wang (rayons radiaux)
# Réutilise les données du PoC01 (backend/data/mns.vrt)

LAT ?=
LON ?=
RAYON ?= 10000
ANGLE ?= 0.1
HAUTEUR ?= 2.0
CIBLE ?= 0.0
K ?= 1.1667
PAS_LOIN ?= 10.0
AIRE_MINI ?= 0
OUT ?= viewshed.geojson

.PHONY: doctor viewshed help

help:
	@echo "Cibles: doctor | viewshed LAT=.. LON=.. [RAYON=10000] [ANGLE=0.1] [HAUTEUR=2.0]"
	@echo "        [CIBLE=0.0] [K=1.1667] [PAS_LOIN=10.0] [AIRE_MINI=0] [OUT=viewshed.geojson]"

doctor:
	@for t in gdal_translate gdalinfo gdaltransform gdal_rasterize ogr2ogr python3; do \
	  command -v $$t >/dev/null || { echo "outil manquant: $$t (apt install gdal-bin python3)"; exit 1; }; \
	done
	@command -v gdal_polygonize >/dev/null || command -v gdal_polygonize.py >/dev/null \
	  || { echo "outil manquant: gdal_polygonize ou gdal_polygonize.py (apt install gdal-bin)"; exit 1; }
	@python3 -c "import numpy; print('numpy', numpy.__version__)" \
	  || { echo "numpy manquant (apt install python3-numpy)"; exit 1; }
	@gdalinfo --version
	@echo "OK"

viewshed:
	@if [ -z "$(LAT)" ] || [ -z "$(LON)" ]; then \
	  echo "LAT et LON sont obligatoires: make viewshed LAT=47.810322 LON=0.983288"; exit 1; fi
	python3 scripts/viewshed_r3.py --lat $(LAT) --lon $(LON) --rayon $(RAYON) \
	  --angle $(ANGLE) --hauteur $(HAUTEUR) --cible $(CIBLE) --k $(K) \
	  --pas-loin $(PAS_LOIN) --aire-mini $(AIRE_MINI) --out $(OUT)
