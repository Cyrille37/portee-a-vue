# PoC01 - Makefile d'orchestration
# Zone definie dans zone.env (point WGS84 + rayon) ; la liste des dalles
# est calculee par scripts/zone.py (conversion WGS84->L93 + disque).
# Nom de dalle = coin NW (ouest X km, nord Y km).

PRODUITS := MNS MNT
DALLES := $(shell python3 scripts/zone.py dalles)

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
