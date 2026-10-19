# TODO

## À corriger (par ordre d'importance)

1. Le test de cohérence min est inversé — check.py:85 (bug latent).
check(sm <= sj + 2.0, f"{dalle}: min MNS {sm} > min MNT {sj} + 2 m")
Cela échoue si min MNS dépasse min MNT de > 2 m — c'est-à-dire dans la direction physiquement attendue (surface ≥ sol). Sur le secteur plat de Tours ça passe (j'ai sorti les vraies valeurs : min MNS − min MNT ∈ {0, 1 m} sur les 7 dalles), mais c'est orienté à l'envers. Concrètement : une tuile où le point le plus bas du MNS est une base de bâtiment à 105 m et le fond de vallée du MNT à 90 m → min MNS − min MNT = 15 > 2 → faux « ECHEC » sur des données parfaitement valides. Le bon invariant est min MNS ≥ min MNT (tolérance ~1 m pour nodata/arrondi) : check(sm >= sj - 1.0, ...). La vérif max (mm >= mj, ligne 83) est elle correcte.
→ Ça ne bloque pas le PoC actuel, mais le moment venu où tu ingères un relief réel ou un secteur boisé, ce test se mettra à hurler sur des tuiles saines.

2. Garde d'idempotence ingest.sh ≠ son propre commentaire (état « poison »).
Le commentaire (ligne 19) dit « sauter si la tuile existe déjà avec ses balises », mais le code ne teste que [ -f "$dst" ]. Si gdalwarp réussit puis gdal_edit échoue (ex. gdal_edit.py absent sur un setup où ni gdal_edit ni gdal_edit.py ne sont sur le PATH), on obtient une tuile sans balises ; les lances suivantes la sautent (dst présent), et make check rapporte « balise absente » en boucle — jamais corrigé.
→ Soit on supprime le dst partiel sur échec (trap), soit on fait du skip une vérification des balises.

3. Aucune intégrité post-téléchargement — download.sh:42.
Un WMS-R 400 ou un transfert coupé laisse un dst minuscule (le corps d'erreur, quelques Ko) ; la relance voit dst présent et saute → source corrompue verrouillée. Le ls -lh final le montrerait mais ne l'assert pas.
→ Ajouter un check de taille minimale (une dalle valide fait ~15–25 Mo ; le README note ~16 Mo) ou un gdalinfo de validation de l'en-tête avant de déclarer le succès. Le doc mentionne un checksum dans la table SQLite — rien n'est capté là non plus.