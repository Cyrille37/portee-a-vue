# Radio Mesh — Altitude d'un point (LiDAR)

Outil web vanilla JS + MapLibre GL : un clic sur la carte affiche
l'altitude du point à partir des données RGE ALTI® / LiDAR de l'IGN
(Géoplateforme) — altitude du sol (MNT), altitude surface (MNS) et
hauteur d'obstacle.

## Utilisation

1. Servir le dossier (`python3 -m http.server`) et ouvrir `http://localhost:8000`
   — le WMS IGN exige une origine http(s) ; en `file://` certains navigateurs
   bloquent les requêtes cross-origin.
2. Cliquer sur la carte : le panneau affiche les coordonnées, l'altitude du
   sol (MNT), l'altitude surface (MNS) et la hauteur d'obstacle (MNS − MNT).

## Architecture

```
index.html          carte plein écran + panneau
css/style.css
js/wmsDem.js        GetMap WMS-R IGN format image/x-bil;bits=32 (float32 LE)
                    -> altitude ponctuelle (requête BIL 1x1, CRS:84)
js/ui.js            formats FR, progression, statut
js/main.js          orchestration (clic, marqueur, erreurs, annulation)
```

## Données & technique

- **Fond de carte** : OSM France Humanitaire (`tile.openstreetmap.fr/hot`).
- **Altitudes** : WMS-Raster Géoplateforme `data.geopf.fr/wms-r`, couches
  `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES` (MNT 1 m) et
  `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS` (MNS), format
  `image/x-bil;bits=32` : une requête BIL 1x1 renvoie l'altitude en float32
  **little-endian**.

## Limites connues

- Couverture : France métropolitaine (RGE ALTI®). Hors zone, erreur explicite.
- L'historique du viewshed (calcul de surface de vue directe) est archivé
  dans la branche `archive-viewshed-r3-wang`.
