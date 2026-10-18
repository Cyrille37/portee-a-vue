# Altitude d'un point (LiDAR)

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

## Sources de données complémentaires

Référence des services de la Géoplateforme (IGN) exploitables pour de
prochaines évolutions. Tous sont accessibles sans clé, en open data
(Licence Ouverte Etalab 2.0) — vérifier les limites d'usage par service.

### Caractéristiques des produits altimétriques

| Produit | Pas (résolution) | Précision | Contenu | Couverture |
|---|---|---|---|---|
| **LiDAR HD** (nuage de points) | ≥ 10 impulsions/m² (5 au-dessus de 3 200 m) | altimétrique ~10 cm, planimétrique ~5 cm (classification) | points classés sol/eau/végétation/bâtiments/ponts | France métrop. + DROM (hors Guyane), programme completé d'ici 2026 |
| **MNT LiDAR HD** | maillage 50 cm | « Pas de 50 cm » | terrain nu (points sol + eau + virtuels) | suit la diffusion LiDAR HD |
| **MNS LiDAR HD** | maillage 50 cm | « Pas de 50 cm » | terrain + végétation, bâtiments, ouvrages d'art | suit la diffusion LiDAR HD |
| **MNH LiDAR HD** | maillage 50 cm | « Pas de 50 cm » | hauteur surface−sol (MNS−MNT) | suit la diffusion LiDAR HD |
| **RGE ALTI®** | maillage 1 m | ~1 m (selon source) | MNT terrain nu | France entière (métropole + DOM/COM), stable |

Autres caractéristiques utiles :

- **Dalles de diffusion** : 1×1 km (Lambert-93 pour la métropole,
  RGR92UTM40S pour La Réunion) ; identifiées par `coordonnees_nw` ;
  téléchargeables en GeoTIFF par dalle (cf. URLs dans les métadonnées).
- **Systèmes de référence** : altimétrie IGN69 / IGN78 (normale),
  géopositionnement RGF93 / Lambert-93 (métropole).
- **Reprojection** : les ressources `_mono_wld` « avec interpolation » sont
  reprojettées en projection mondiale — des valeurs interpolées peuvent
  apparaître aux transitions zones sans/avec données.
- **Bbox des ressources** : approximatives — la disponibilité réelle se
  constate par la sentinelle `z = -99999` ou la couche de couverture.

### Altimétrie ponctuelle — API Altimétrie (utilisée)

- `https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json`
  (GET/POST, JSON/XML ; **5 req/s par IP**) ; `zonly`, `measures`,
  `elevationLine` (profil en long, `sampling` jusqu'à 5000 points,
  `profile_mode=accurate`).
- Ressources : `ign_lidar_hd_mnx_mono_wld` (LiDAR HD 50 cm, MNT+MNS+MNH en
  une requête, avec interpolation), `ign_rge_alti_wld` (RGE ALTI 1 m, MNT
  seul, couverture France entière), `ign_lidar_hd_mnt_mono_wld`, …
- Liste complète : `https://data.geopf.fr/altimetrie/resources`.
  Hors couverture : sentinelle `z = -99999`.
- Cas particulier : `IGNF_LIDARHD_MNX_WLD` et `ALTIMETRIE` (sans
  interpolation) renvoient `-99999` sur des zones incluses dans leur bbox
  déclarée — la bbox ne préjuge pas de la disponibilité réelle.

### Couverture LiDAR HD — tuiles vectorielles TMS (utilisées)

- `https://data.geopf.fr/tms/1.0.0/IGNF_LIDAR-HD_METADONNEE/{z}/{x}/{y}.pbf`
  (MVT, EPSG:3857, tuiles 256 px, **schéma XYZ standard** origine
  haut-gauche malgré le nom « TMS** — l'inversion `{-y}` renvoie 404).
  Zooms 6 à 14+, couche interne `metadata` (dalle = feature 1×1 km avec
  `code_mission`, `date_*`, `coordonnees_nw`, URLs de téléchargement).
- Catalogue TMS : `https://data.geopf.fr/tms/1.0.0/` (826 TileMaps).
- Variantes par produit : `IGNF_MNT-LIDAR-HD-produit` (dalles MNT),
  `IGNF_MNS-LIDAR-HD-produit`, `IGNF_MNH-LIDAR-HD-produit`,
  `IGNF_NUAGES-DE-POINTS-LIDAR-HD-produit`, `*-chantier` (blocs),
  `PLANIGN.LIDAR.TERRAIN` (fond de carte dérivé du LiDAR HD).

### Couverture LiDAR HD — WFS équivalent

- `https://data.geopf.fr/wfs` — `TYPENAMES=IGNF_LIDAR-HD_METADONNEE:metadata`
  (`GetFeature` JSON, `BBOX` en ordre **lat,lon** avec
  `SRSNAME=EPSG:4326`, **sans** suffixe CRS dans le BBOX ; `COUNT`/`STARTINDEX`
  pour paginer — troncature spatiale silencieuse si `COUNT` trop petit).
- Utile pour un test ponctuel « ce point est-il couvert ? » ou télécharger
  les emprises d'une zone précise.

### Grilles d'altitude — WMS-Raster (utilisé précédemment, archivé)

- `https://data.geopf.fr/wms-r` — GetMap format `image/x-bil;bits=32`
  (float32 **little-endian**, 1 valeur/pixel ; WMS 1.3.0 : première ligne =
  bord sud). Couches : `ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES` (MNT 1 m),
  `...HIGHRES.MNS` (MNS), `IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.*`
  (MNT/MNS/MNH LiDAR HD, variantes LAMB93/RGR92UTM40S/SHADOW/WGS84G),
  `IGNF_LIDAR-HD_CLASS`, `IGNF_LIDAR-HD_DENSITE-SOL`/`-SURSOL`.
- Les features `metadata` du WFS/TMS embarquent aussi des URLs
  `image/geotiff` de téléchargement direct par dalle (MNT/MNS/MNH/NPL).
- Un GetMap avec `LAYERS` multiples (MNT+MNS) n'a **pas** été validé —
  à tester avant usage.

### Divers

- Carte officielle d'avancement LiDAR HD : macarte.ign.fr
  (`diffusionMNxLiDARHD`, `Avancement-Programme-LIDAR-HD`) — s'appuie sur
  les flux ci-dessus.
- Nuages de points LiDAR HD (classification, densité) : couches WMS-R
  `IGNF_LIDAR-HD_*` et TMS `IGNF_NUAGES-DE-POINTS-LIDAR-HD-*` ; fiche :
  geoservices.ign.fr/lidarhd.
- Ordre des axes : WFS 2.0/EPSG:4326 = (lat, lon) ; WMS 1.3.0/EPSG:4326 =
  (lat, lon) — d'où CRS:84 pour les requêtes ponctuelles ; TMS = XYZ (lon
  puis lat, origine haut-gauche).

## Limites connues

- Couverture : France métropolitaine (RGE ALTI®). Hors zone, erreur explicite.
- L'historique du viewshed (calcul de surface de vue directe) est archivé
  dans la branche `archive-viewshed-r3-wang`.
