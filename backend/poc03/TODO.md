# Verdict global

Le socle est bon : README clair, mode --inverse bien pensé, lecture tuilée pour borner la RAM, .gitignore des artefacts, section PMTiles argumentée. Mais les attributs de stats sont faux dans les deux artefacts livrés, et le masque inverse est empoisonné par le nodata. Dans l'état actuel, mns_min_m / mns_moy_m / mns_max_m sont inutilisables.

## Bug 1 (bloquant) : toutes les features partagent les mêmes stats

Preuve dans masque-sup95.geojson : 14 621 features, 1 seul tuple de stats distinct — (96.0, 131.6, 197.0). Je l'ai re-produit : c'est exactement le min/moy/max zone entière des cellules MNS > 95 (96.0 / 131.6 / 197.0). Idem en inverse : toutes les features affichent (-9999.0, -5580.2, 95.0), soit les stats du masque inverse global.

Cause racine : le commentaire de masque_altitude.py:306 dit « chaque polygone polygonisé remplace ses cellules par son index (attribut DN) ». Faux : gdal_polygonize.py met dans le champ DN la valeur du raster (0 ou 1 pour un masque binaire), pas un identifiant unique par polygone. gdal_rasterize -a DN produit donc un raster d'ids ne contenant que {0, 1}, et l'accumulation par id fusionne tout en un seul bucket. Vérifié sur un crop : 86 features dans le GPKG, mais le raster d'ids ne contient que 2 valeurs distinctes.

Corrections possibles :
- A. Style CLI (minimal, suit la convention poc01/02) : générer un champ unique avant rasterisation, ex. ogr2ogr -sql "SELECT rowid AS id, DN FROM masque" → gdal_rasterize -a id ; exporter avec -select "id, DN" et indexer les stats par id. (+1 subprocess, zéro nouvelle dépendance. Note : gdal_rasterize -a FID ne marche pas, testé.)
- B. python-gdal (plus propre + plus vite) : gdal.Polygonize(band, None, callback=cb) retourne directement le raster d'ids en mémoire et le callback collecte les géométries — ça supprime le GPKG→rasterize→relecture-entière en AAIGrid. Dépendance python3-gdal (déjà installée ici, osgeo 3.4.1 ; à ajouter au doctor).

## Bug 2 (bloquant en --inverse) : le nodata est compté « en dessous du seuil »

La zone contient 19,5 % de nodata (-9999) (21,5 M cellules — typiquement eau / non-couvert en LHD). Le seuillage mns_t <= altitude laisse passer le -9999 :

- 56,2 % de l'aire du masque inverse livré est du nodata (86 km² d'« inconnu » présentés comme « en contrebas de 95 m », sur 153 km² totaux) ;
- les stats des features inverses sont de la merde (mns_moy_m: -5580.2) — aujourd'hui masqué par le bug 1, visible par feature dès qu'il sera corrigé ;
- le mode direct est correct par accident (-9999 > 95 = false) — mais c'est du hasard, pas du design : un jeu de données avec un autre nodata (0, -32768…) le contaminerait.
- La promesse README « complémentarité stricte, couverture 100 % » tient seulement parce que le nodata est compté « en dessous ».

Correction : lire le noDataValue dans gdalinfo -json (déjà appelé pour l'emprise), valide = mns != nodata, masque = valide & (mns > alt) / valide & (mns <= alt). Après correction, direct ∪ inverse couvre 80,5 % de la zone (les cellules valides), pas 100 % — README à mettre à jour, le nodata devient un troisième état explicite (« inconnu »).

## Points mineurs

1. MultiPolygons silencieux	type != "Polygon": continue (ligne 346) jette sans compter. Mes tests (diagonale, « pinch ») n'ont produit que des Polygon, donc risque faible — mais c'est une perte silencieuse ; au moins compter et avertir.
2. gdal_read_array	valide la largeur des lignes mais pas len(lignes) == h (le lecteur d'ids, lui, le fait). Un décalage crasherait sur l'affectation — acceptable, mais incohérent.
3. aire_m2 approximative	calculée sur la géo simplifiée en WGS84 (shoelace + facteur local), pas sur l'emprise réelle des cellules. OK pour un filtre d'ordre de grandeur (le docstring l'avoue), mais avec un pipeline d'ids corrigé, l'aire exacte = nb_cellules × 4 m² — plus juste et gratuit.
4. Membre crs du GeoJSON	non conforme RFC 7946 (il ne doit pas exister ; WGS84 par défaut). MapLibre l'accepte, mais fc.pop("crs") fait propre.
5. date_generation	sans fuseau horaire — datetime.now(timezone.utc).
6. README en dérive	« zone 36 × 54 km / 2,9 Go / 12 126 polygones / 8,4 Mo » — la zone actuelle fait 21 × 21 km (10 500 × 10 500 cellules), ~0,7 Go de grilles, et les artefacts livrés font 10 127 features / 7,3 Mo (inf95) et 14 621 / 7,9 Mo (sup95).

## Performance (à noter, pas bloquant)

Le goulot est la passe texte : deux passages complets des 110 M cellules via gdal_translate → /vsistdout/ en AAIGrid + parsing float/int en Python (la lecture MNS et la relecture du raster d'ids). La tuilage borne bien la RAM, c'est le texte qui coûte. Si la dépendance python3-gdal est acceptable (déjà présente ici), ReadAsArray(xoff, yoff, w, h) garde le même bornage RAM et est un ordre de grandeur plus rapide — et le raster d'ids offert par gdal.Polygonize supprime la 2ᵉ passe entièrement. Si on reste 100 % CLI (convention des poc01/02), l'état actuel est acceptable pour un PoC — le README documente honnêtement le temps.
