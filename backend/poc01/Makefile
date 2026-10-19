# PoC01 - Makefile d'orchestration
# Zone: quartier de l'Europe, Tours (47.422648, 0.683287) - L93: 525363.55 6705039.73
# Nom de dalle = coin NW (ouest X km, nord Y km). Dalle du point: 0525_6706
# rayon 1 km = 7 dalles

PRODUITS := MNS MNT
DALLES := 0524_6705 0524_6706 0525_6705 0525_6706 0525_6707 0526_6705 0526_6706

.PHONY: doctor download ingest vrt check check-remote clean help

help:
	@echo "Cibles: doctor | download | ingest | vrt | check | check-remote | clean"

doctor:
	@for t in gdalinfo gdalwarp gdalbuildvrt gdallocationinfo gdaltransform curl unzip; do \
	  command -v $$t >/dev/null || { echo "outil manquant: $$t (apt install gdal-bin curl unzip)"; exit 1; }; \
	done
	@command -v gdal_edit >/dev/null || command -v gdal_edit.py >/dev/null \
	  || { echo "outil manquant: gdal_edit ou gdal_edit.py (apt install gdal-bin)"; exit 1; }
	@python3 -c "import numpy; print('numpy', numpy.__version__)" \
	  || { echo "numpy manquant (apt install python3-numpy)"; exit 1; }
	@gdalinfo --version
	@sqlite3 --version || true
	@echo "OK"

download:
	@for p in $(PRODUITS); do \
	  for d in $(DALLES); do \
	    echo "== $$p $$d"; \
	    ./scripts/download.sh $$p $$d || exit 1; \
	  done; \
	done

ingest:
	@for p in $(PRODUITS); do \
	  for d in $(DALLES); do \
	    echo "== $$p $$d"; \
	    ./scripts/ingest.sh $$p $$d || exit 1; \
	  done; \
	done

vrt:
	@gdalbuildvrt ../data/mns.vrt ../data/mns/*.tif
	@gdalbuildvrt ../data/mnt.vrt ../data/mnt/*.tif
	@gdalinfo ../data/mns.vrt | head -20

check:
	@python3 scripts/check.py

check-remote:
	@python3 scripts/check_remote.py

clean:
	rm -f ../data/mns.vrt ../data/mnt.vrt
	rm -f ../data/mns/*.tif ../data/mns/*.tif.aux.xml
	rm -f ../data/mnt/*.tif ../data/mnt/*.tif.aux.xml
	rm -rf ../data/downloads/*
