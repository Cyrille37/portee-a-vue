# PoC01 - Makefile d'orchestration
# Zone: quartier de l'Europe, Tours (47.422648, 0.683287) - L93: 525363.55 6705039.73
# Dalle centrale: 0525_6705 ; rayon 1 km = 7 dalles

PRODUITS := MNS MNT
DALLES := 0524_6704 0524_6705 0525_6704 0525_6705 0525_6706 0526_6704 0526_6705

.PHONY: doctor download ingest vrt clean help

help:
	@echo "Cibles: doctor | download | ingest | vrt | clean"

doctor:
	@command -v gdalinfo >/dev/null || { echo "GDAL manquant (apt install gdal-bin)"; exit 1; }
	@command -v curl >/dev/null   || { echo "curl manquant"; exit 1; }
	@gdalinfo --version
	@python3 -c "import numpy; print('numpy', numpy.__version__)"
	@sqlite3 --version
	@echo "OK"

download:
	@for p in $(PRODUITS); do \
	  for d in $(DALLES); do \
	    echo "== $$p $$d"; \
	    ./scripts/download.sh $$p $$d; \
	  done; \
	done

ingest:
	@for p in $(PRODUITS); do \
	  for d in $(DALLES); do \
	    echo "== $$p $$d"; \
	    ./scripts/ingest.sh $$p $$d; \
	  done; \
	done

vrt:
	@gdalbuildvrt ../data/mns.vrt ../data/mns/*.tif
	@gdalbuildvrt ../data/mnt.vrt ../data/mnt/*.tif
	@gdalinfo ../data/mns.vrt | head -20

clean:
	rm -f ../data/mns.vrt ../data/mnt.vrt
