# PoC02 - Masque d'altitude
# Réutilise les données du PoC01 (backend/data/*.vrt)

SEUIL ?= 10
RAYON ?= 1000
OUT ?= masque.geojson
AIRE_MINI ?= 0

.PHONY: masque help

help:
	@echo "Cibles: masque [SEUIL=10] [RAYON=1000] [AIRE_MINI=0] [OUT=masque.geojson]"

masque:
	@python3 scripts/masque.py --seuil $(SEUIL) --rayon $(RAYON) --aire-mini $(AIRE_MINI) --out $(OUT)
