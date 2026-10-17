# Radio Mesh — Visibilité directe

Outil web vanilla JS + MapLibre GL qui calcule et dessine, à la manière d'un
isochrone, la **surface de vue directe (viewshed)** d'une antenne placée par
clic sur la carte, à partir des altitudes RGE ALTI® / LiDAR de l'IGN
(Géoplateforme).

## Utilisation

1. Servir le dossier (`python3 -m http.server`) et ouvrir `http://localhost:8000`
   — le WMS IGN exige une origine http(s) ; en `file://` certains navigateurs
   bloquent les requêtes cross-origin.
2. Cliquer sur la carte : altitude du sol affichée, surface visible calculée
   dans le rayon courant.
3. Régler :
   - **Hauteur d'antenne** (m au-dessus du sol) puis « Recalculer » — instantané,
     la grille reste en mémoire.
   - **Rayon** : curseur logarithmique de 100 m à 30 km.
   - **Obstacles** : MNT (terrain nu) ou MNS (végétation + bâtiments inclus).

## Architecture

```
index.html          carte plein écran + panneau
css/style.css
js/wmsDem.js        GetMap WMS-R IGN format image/x-bil;bits=32 (float32 BE)
                    -> Float32Array ; cache LRU par (couche, centre, rayon)
js/viewshed.js      viewshed radial (pente maximale apparente par azimut)
                    + lissage du masque
js/render.js        masque -> canvas -> source "image" MapLibre (EPSG:3857)
js/ui.js            slider log 100 m-30 km, formats FR, progression
js/main.js          orchestration (clic, recalcul, erreurs, annulation)
```

## Données & technique

- **Fond de carte** : OSM France Humanitaire (`tile.openstreetmap.fr/hot`).
- **Altitudes** : WMS-Raster Géoplateforme `data.geopf.fr/wms-r`, couches
  `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES` (MNT 1 m) et
  `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS` (MNS), format
  `image/x-bil;bits=32` : une requête HTTP renvoie toute la grille en
  float32 **little-endian** (≈16 Mo pour 2000² cellules). De 1 km à 30 km de
  rayon : 1 à 2 requêtes, indépendant du rate-limit de l'API altimétrique.
  Attention : le flux est bien little-endian (validé sur points de contrôle
  — Mont Blanc ≈ 4757 m, Tour Eiffel ≈ 33,8 m) ; un décodage big-endian
  donne des altitudes aberrantes (10²⁰ m).
- **Viewshed** : balayage radial (pente apparente maximale depuis le sommet
  de l'antenne), densité angulaire proportionnelle au rapport rayon/pas pour
  éviter les trous ; masque lissé (rendu isochrone doux).
- **Rendu** : masque en canvas (1 px = 1 cellule), injecté comme image
  géoréférencée EPSG:3857 — zéro reprojection.
- **Correction Mercator** : les distances réelles sont converties via
  1/cos(latitude) ; le pas affiché est le pas réel au sol.

## Limites connues

- Couverture : France métropolitaine (RGE ALTI®). Hors zone, erreur explicite.
- Grille plafonnée à 4000² cellules : le pas croît avec le rayon
  (~1 m sous 2 km, ~15 m à 30 km).
- MNS sur grandes zones : un seul arbre masque une cellule ; le rendu
  représente le « haut des obstacles ».
- Pas de Web Worker en v1 : le calcul reste sous la seconde pour 4000² ;
  bascule prévue en v2 si nécessaire.
