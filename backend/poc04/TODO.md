# Verdict global

Le PoC est solide et l'algorithme est correct. La plus grande valeur de ce que j'ai fait : j'ai validé le cœur R3 contre gdal_viewshed (l'implémentation de référence) → 99,7 % d'accord. C'est exactement le « quelques % » que le README promet. La réutilisation du socle PoC01 est propre et cohérente avec le pipeline PoC03 (même lecture AAIGrid, même PGM→GTiff→polygonize→GeoJSON, même aire_polygone).

Ce que j'ai vérifié :
- R3 sur terrain plat : observateur à +30 m → 100 % visible dans le disque de 10 km, cohérent avec l'horizon géodésique + réfraction (~21 km). ✓
- Test croisé gdal_viewshed (terrain synthétique, relief 15–45 m) : 99,73 % d'accord, 0,27 % de désaccord (0,03 % faux-positifs + 0,23 % faux-négatifs) concentré aux frontières. ✓

Mais il y a deux problèmes concrets que j'ai pu reproduire, et le premier est important.

🔴 Problème n°1 (critique) : le protocole de test croisé du README est faux

C'est le plus important. Le README dit, dans le tableau de correspondance :

--hauteur (antenne) → -oz = altitude du centre + hauteur … « reprend ce Z pour -oz »

Or gdal_viewshed -oz signifie « height of the observer ABOVE the DEM surface » (hauteur au-dessus du sol, défaut 2 m), pas l'altitude absolue NGF. J'ai reproduit les deux cas :

-oz transmis	Résultat du test croisé
Altitude NGF absolue (~231 m), comme le README	37 % de désaccord, quasi tous en faux-négatifs (gdal voit bien plus)
--hauteur (30 m), la bonne valeur	99,73 % d'accord ✓

En transmettant l'altitude absolue, on place l'observateur GDAL ~200 m trop haut → il voit presque tout → le test conclut à tort que l'implémentation est cassée. L'implémentation est bonne ; c'est la recette de validation documentée qui a un bug. Il y a même un deuxième bug dans ce tableau : --rayon → -r, mais gdal_viewshed n'a pas d'option -r (c'est -md, qui par ailleurs crashe sur GDAL 3.4.1 : « Attempt to create 3000x-4999 dataset »). La façon robuste est de dimensionner la fenêtre à 2×rayon et d'omettre -md — c'est ce que j'ai fait, et ça donne les 99,73 %.

À corriger dans le README : -oz = --hauteur (pas l'altitude NGF), et --rayon → -md (ou fenêtre 2×rayon sans -md).

🟠 Problème n°2 : le « 20–40 km » n'est pas atteignable avec le chemin I/O actuel (mémoire + temps)

La fenêtre est [centre ± rayon] = un carré de 2×rayon. Pour rayon=40 km → fenêtre 80×80 km = 40 000×40 000 = 1,6 milliard de cellules. La lecture AAIGrid-texte fait [float(v) for v in l.split()] dans une liste Python de floats : ~50–60 Go transitoires → OOM sur une machine de 31 Go. J'ai mesuré l'échelle (~R²) : R=2 km→1 s, R=4 km→4 s, R=6 km→8,4 s. Donc :

- rayon 20 km (40×40 km, 4×10⁸ cellules) : ~15 Go, ~10 min — à la limite.
- rayon 40 km : ~60 Go → OOM, et ~35 min de parse si ça tenait.

Le plafond réaliste est ~20 km (marginal), pas 40. Et l'estimation mémoire du README (« ~5 Go pour une fenêtre 40 km × 40 km à 2 m ») est incohérente : une fenêtre 40×40 km = 2×10⁴²… non, 20 000² cellules ≈ 2 Go (pas 5), et la fenêtre pour rayon=40 km est 80×80 km, pas 40×40.

Correctif : lire le raster directement dans un tableau numpy via les bindings Python GDAL (osgeo), en évitant le détour texte AAIGrid. Gain ×10 en mémoire et en vitesse. (À noter : le doctor vérifie les outils CLI GDAL, pas osgeo.)

🟠 Problème n°3 : stats_anneaux_distance fait un mgrid plein-cadre non tuilé

Le reste du pipeline est tuilé (tuile=8192) pour borner la RAM, mais la fonction de stats par anneau fait np.mgrid[0:h, 0:w] sur toute la grille d'un coup (3–4 tableaux full float64/int64). C'est un point OOM caché, indépendant de la lecture — j'ai OOM à 25 000×25 000. À tuiler comme le reste (ou calculer les anneaux pendant la passe de report déjà tuilée).

Points mineurs
- « R3 vectorisé NumPy / quelques secondes » : les rayons sont en fait une boucle Python de 3 600 itérations (vectorisé le long de chaque rayon seulement). Correct pour ≤10 km ; c'est le 2ᵉ goulot après la lecture à 20 km. La formulation survendant un peu.
- Biais R3 : le README insiste sur un biais « faux-positifs, presque jamais l'inverse ». Le résidu mesuré (0,27 %) est un petit mélange (0,03 % FP + 0,23 % FN) — négligeable en pratique, mais la direction décrite n'est pas celle mesurée.
- ANNEAUX_DEFAUT (…20000, 40000) est silencieusement tronqué quand rayon est plus petit (le run à 10 km livré ne montre que des anneaux jusqu'à 10 km). Pas un bug, juste à savoir.

Ce qui est vraiment bon
- Cœur R3 validé (99,7 % vs référence), courbure+réfraction k=7/6 correct (j'ai confirmé que la formule GDAL cc·d²/(2R) avec cc=6/7 donne la même R_eff=7R/6 que notre k=7/6).
- Bon paramétrage LoRa (--cible pair au sol vs mât d'abonné, --k, pas adaptatif).
- Les stats par anneau de distance sont une sortie réellement utile pour la planification LoRa.
- Documentation physique soignée ; l'idée du test croisé est excellente — il suffit de corriger la recette.
