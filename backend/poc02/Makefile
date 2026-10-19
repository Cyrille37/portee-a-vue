# PoC02 - Masque d'altitude
# Réutilise les données du PoC01 (backend/data/*.vrt)

SEUIL ?= 10
RAYON ?= 1000
OUT ?= masque.geojson

.PHONY: masque help

help:
	@echo "Cibles: masque [SEUIL=10] [RAYON=1000] [OUT=masque.geojson]"

masque:
	@python3 scripts/masque.py --seuil $(SEUIL) --rayon $(RAYON) --out $(OUT)
