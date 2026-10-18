# Radio Mesh — Altitude d'un point (LiDAR)

Outil web vanilla JS + MapLibre GL : un clic sur la carte affiche
l'altitude du point à partir des données LiDAR HD / RGE ALTI® de l'IGN
(Géoplateforme) — altitude du sol (MNT), altitude surface (MNS) et
hauteur d'obstacle (MNH).

## Utilisation

1. Servir le dossier (`python3 -m http.server`) et ouvrir `http://localhost:8000`
   — le WMS IGN exige une origine http(s) ; en `file://` certains navigateurs
   bloquent les requêtes cross-origin.
2. Cliquer sur la carte : le panneau affiche les coordonnées, l'altitude du
   sol (MNT), l'altitude surface (MNS) et la hauteur d'obstacle (MNH).

## Architecture

```
index.html          carte plein écran + panneau
css/style.css
js/alti.js           API Altimétrie Géoplateforme
                    (data.geopf.fr/altimetrie) : MNT + MNS + MNH
                    en une requête (LiDAR HD, repli RGE ALTI)
js/ui.js            formats FR, progression, statut
js/main.js          orchestration (clic, couverture, marqueur, erreurs, annulation)
```

## Données & technique

- **Fond de carte** : OSM France Humanitaire (`tile.openstreetmap.fr/hot`).
- **Altitudes** : API Altimétrie de la Géoplateforme
  `https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json`,
  ressource `ign_lidar_hd_mnx_mono_wld` (LiDAR HD, pas 50 cm) qui renvoie
  MNT, MNS et MNH en une seule requête (`measures=true`) ; repli sur
  `ign_rge_alti_wld` (MNT seul) hors couverture LiDAR HD.
- **Limite de service** : 5 requêtes/s par IP (largement suffisant pour
  des clics manuels).
- **Couverture LiDAR HD** : tuiles vectorielles TMS Géoplateforme
  `IGNF_LIDAR-HD_METADONNEE` (emprises des dalles 1×1 km diffusées,
  généralisées aux basses échelles), affichées en bleu translucide dès le
  zoom 6 (source vector MapLibre, schéma XYZ standard).
  Zone non couverte → repli RGE ALTI et « Hauteur : n.d. ».

## Limites connues

- Couverture : France métropolitaine (RGE ALTI®). Hors zone, erreur explicite.
- L'historique du viewshed (calcul de surface de vue directe) est archivé
  dans la branche `archive-viewshed-r3-wang`.
