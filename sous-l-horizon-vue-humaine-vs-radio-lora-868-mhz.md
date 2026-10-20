# Sous l'horizon — vue humaine vs radio LoRa 868 MHz

## Question

Les zones basses lointaines qui « paraissent visibles » dans un masque d'altitude alors qu'elles sont sous l'horizon géodésique sont définitivement invisibles pour un œil humain. Qu'en est-il pour la radio LoRa 800–900 MHz (MeshCore, bande SRD 863–870 MHz) : l'horizon est-il une frontière, et à quel prix peut-on le franchir ? Conséquence attendue pour les outils « masque d'altitude » et « profil A↔B ».

## Synthèse

1. **L'œil est binaire, la radio est graduée.** À 868 MHz (λ ≈ 34,6 cm), l'onde se diffracte autour de la « bosse » terrestre et des obstacles : au-delà de l'horizon, le signal ne disparaît pas, il s'affaiblit progressivement — c'est une pénombre en dB, pas un mur (méthode de référence : [ITU-R P.526](https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.526-15-201910-S!!PDF-E.pdf)).
2. **L'horizon radio est ~15 % plus loin que l'horizon géodésique.** Avec la réfraction standard (k = 4/3), un point d'observation à 42 m porte à 26,7 km au lieu de 23,1 km ; une liaison 42 m ↔ 2 m à 32,5 km au lieu de 28,2 km.
3. **Le budget LoRa peut payer la pénombre.** Avec 14 dBm ERP et des sensibilités de −123 (SF7) à −137 dBm (SF12, BW 125 kHz), le budget vaut 137 à 151 dB ; l'affaiblissement en espace libre à 50 km n'étant que de ~125 dB, il reste **12 dB (SF7) à 26 dB (SF12) de marge** pour de la diffraction.
4. **Une obstruction franche coûte 6 à ~20 dB** (arête à ras : ~6 dB ; obstruction nette : 13–19 dB) : une zone basse *à peine* sous l'horizon reste donc joignable en SF12, rarement en SF7.
5. **Le prix caché est le débit et la robustesse.** Un lien sous-horizon passe en SF élevé : airtime ~1 s par petit paquet, duty cycle 1 % dans les sous-bandes 868 MHz, sensibilité accrue aux variations météo (k varie : sub-réfraction resserre l'horizon, ducting l'étend). La diffraction est une extension de couverture, pas un socle de design.
6. **Conséquence directe pour le profil A↔B :** le verdict doit être une **marge en dB par facteur d'étalement**, pas un booléen « dégagé/bloqué ».

## Méthodologie

- **Angles** : optique vs radio (réfraction, k effectif) ; diffraction au-delà de l'horizon (ITU-R P.526) ; budget de liaison LoRa (sensibilités constructeur, affaiblissement en espace libre) ; études expérimentales mesurées (liaisons sur eau de mer, réseau insulaire, records stratosphériques) ; cadre réglementaire SRD (ERC 70-03, limites de puissance/duty cycle) ; implications pour l'outillage en cours de spécification.
- **Types de sources** : recommandations ITU-R, articles évalués par pairs (MDPI, Radio Science, EURASIP), documentation réglementaire (ERC 70-03), calculateurs spécialisés, presse technique.
- **Limites** : les pertes de diffraction citées sont des valeurs de modèles (arête unique), pas des mesures sur vos terrains ; les sensibilités constructeur sont optimales (une mise en œuvre réelle, bruit RF compris, perd typiquement 5–15 dB) ; aucune mesure locale n'a été réalisée.

## Constats

### 1. Deux horizons différents pour deux ondes différentes

| Hauteur d'observation | Horizon géodésique (k = 1) | Horizon radio (k = 4/3) |
|---|---|---|
| 2 m | 5,0 km | 5,8 km |
| 10 m | 11,3 km | 13,0 km |
| 42 m (toit type) | 23,1 km | 26,7 km |
| 100 m | 35,7 km | 41,2 km |

Liaison 42 m ↔ 2 m : 28,2 km géodésique, **32,5 km en radio standard**. Formule : `d ≈ 3,57 × √(k·h)` km. Le k = 4/3 est le modèle usuel d'atmosphère standard ([Holleman 2013, Radio Science](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/rds.20030) ; [SATEL](https://www.satelusa.com/article-line-of-sight-radio-range-antenna-heights/)).

Pour la lumière (λ ≈ 0,5 µm), la diffraction est négligeable : sous l'horizon, c'est noir. Pour la radio (λ ≈ 34,6 cm à 868 MHz), la transition est continue.

### 2. Au-delà de l'horizon : une pénombre chiffrable

- **Diffraction d'arête** ([ITU-R P.526-15](https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.526-15-201910-S!!PDF-E.pdf)) : ~6 dB à ras d'obstruction, ~13 dB pour un paramètre v = 1, ~19 dB pour v = 2 — c'est l'ordre de grandeur d'un relief unique bien placé sur le trajet.
- La **bosse terrestre** au-delà de l'horizon se comporte comme une arête épaisse et continue : la perte croît avec la profondeur sous l'horizon et la distance — progressivement, sans seuil d'extinction.
- **k n'est pas une constante** : sub-réfraction (k < 1, horizon plus proche), super-réfraction et ducting (k ≫ 4/3, contacts anormaux à très longue distance) surviennent selon la météo ; k = 4/3 est un compromis de planification, pas une garantie.
- Ondes de sol et ionosphère : hors jeu à 868 MHz — la pénombre de diffraction et le troposcatter sont les seuls mécanismes « sous l'horizon ».

### 3. Combien de dB le budget LoRa peut-il payer ?

Hypothèses : 14 dBm ERP (SRD 868 MHz), antennes 0 dBi, FSPL = 32,44 + 20·log f(MHz) + 20·log d(km).

| Distance | FSPL 868 MHz | Marge SF7 (−123 dBm) | Marge SF9 (−129 dBm) | Marge SF12 (−137 dBm) |
|---|---|---|---|---|
| 10 km | 111 dB | 26 dB | 32 dB | 40 dB |
| 27 km | 120 dB | 17 dB | 23 dB | 31 dB |
| 40 km | 123 dB | 14 dB | 20 dB | 28 dB |
| 50 km | 125 dB | 12 dB | 18 dB | 26 dB |

Lecture : à 40–50 km, SF12 conserve ~26–28 dB de marge — de quoi traverser une arête franche (13–19 dB) et une pénombre modérée sous l'horizon ; SF7 ne traverse que le ras d'obstruction. La poche 869,4–869,65 MHz (500 mW ERP, duty cycle 10 %, cadre [ERC 70-03](https://www.readkong.com/page/erc-recommendation-70-03-1019047) analysé dans [EURASIP 2019](https://link.springer.com/article/10.1186/s13638-019-1502-5)) ajoute +3 dB : ~39 dB de marge SF12 à 50 km.

### 4. Observations mesurées

- Liaisons LoRa sur eau de mer : **22 km en LOS avec de simples antennes « rubber duck »** (SF 7–12, BW 125 kHz, 868 et 434 MHz) et **28 km en trajet obstroué** avec des antennes à gain ([MDPI Sensors 2018](https://www.mdpi.com/1424-8220/18/9/2853)).
- Réseau LoRaWAN insulaire (Açores) : couverture maritime de dizaines de kilomètres ([étude 2023](https://ncbi.nlm.nih.gov/pmc/articles/PMC10490279) ; [scénario marin 2021](https://doi.org/10.3390/jmse9111218)).
- Record LoRaWAN : **741 km** (ballon stratosphérique à 33 100 m, Lisbonne↔Zaragoza, 2019) — la borne haute du budget quand la géométrie est dégagée ([Gigazine](https://gigazine.net/gsc_news/en/20190801-lorawan-distance-world-record/)).

Ces mesures confirment que le budget LoRa dépasse largement le LOS pur — la pénombre de diffraction est réellement exploitable, mais elle est consommée sur la marge.

### 5. Le prix caché : SF élevé, airtime, duty cycle, météo

- SF12/BW125 : **airtime ~1 s par petit paquet** — en mesh multi-saut, chaque bond SF12 multiplie latence et consommation.
- **Duty cycle 1 %** dans les sous-bandes 868 MHz usuelles (0,1 % sur certaines) : un lien SF12 ne peut pas porter un trafic dense ([EURASIP 2019](https://link.springer.com/article/10.1186/s13638-019-1502-5)).
- Un lien qui ne passe *que* par diffraction est au plancher de budget : saison de végétation, pluie, sub-réfraction (k < 1) peuvent le faire tomber. Les sensibilités réelles des modules (bruit de bord, implémentation) sont typiquement 5–15 dB moins bonnes que le datasheet.

### 6. Ce que ça change pour vos deux outils

- **Masque d'altitude : inchangé.** La correction de courbure k = 4/3 déjà intégrée au seuil place correctement les masses d'obstacles ; les zones basses sous l'horizon n'y sont pas des obstacles — exact.
- **Profil A↔B : à faire évoluer du booléen vers le dB.** Sortir la marge restante par SF (et si possible la perte de diffraction de l'obstacle dominant, méthode arête de P.526) : « bloqué » devient « 8 dB de marge en SF12, 0 dB en SF9 ». Un même profil répond alors à la fois à la planification répéteur↔répéteur (LOS strict + Fresnel 0,6·r1) et à la couverture des objets bas (diffraction tolérable en SF12).
- **Zone servable > zone visible.** Un répéteur en point haut dessert une couronne de zones sous son horizon par diffraction — pertinent pour les capteurs au sol (vaches GNSS, sondes) qui n'exigent pas de débit.

## Défi du plan (examen critique)

1. **« L'horizon est une frontière »** — *risque* : transposer au radio le réflexe optique. Le verdict d'outil « sous l'horizon = impossible » crée des faux négatifs (zones desservables en SF12) ; « LOS dégagé = OK » crée des faux positifs (SF7 sans marge). La seule monnaie fidèle est le dB de marge.
2. **« k = 4/3, figé »** — *risque* : la météo fait varier k (sub-réfraction un matin, ducting une soirée) ; un lien dimensionné exactement à k = 4/3 sans marge tombera statistiquement. k = 4/3 doit rester une hypothèse de design *avec* marge, jamais une promesse.
3. **« SF12 pour franchir l'horizon »** — *risque* : un réseau MeshCore dont les liens de base vivent en diffraction SF12 sera lent (~1 s/paquet), contraint par le duty cycle, et fragile au premier changement de saison. La diffraction doit couvrir les *dernières* zones, pas être le régime nominal.
4. **« Le masque dit le vrai »** — *risque* : un obstacle hors du trajet A↔B ne bloque rien, et un obstacle *sur* le trajet ne bloque pas tout (6 dB au ras) ; le masque reste un outil de repérage, le profil décide — en dB.
5. **Question derrière la question** : cherchez-vous la **couverture de nœuds bas** (la pénombre de diffraction est alors une vraie ressource) ou la **colonne vertébrale répéteur↔répéteur** (LOS + Fresnel stricts, la pénombre est un plan B) ? Les deux usages justifient des critères différents — un seul outil doit les distinguer explicitement.

## Notes sur les sources

| Source | Fiabilité | Dernière mise à jour |
|---|---|---|
| [ITU-R P.526-15 — Propagation par diffraction](https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.526-15-201910-S!!PDF-E.pdf) | 5/5 | 2019 |
| [Holleman 2013 — modèle de rayon effectif k = 4/3, Radio Science](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/rds.20030) | 4/5 | 2013 |
| [SATEL — ligne de vue et rayon effectif](https://www.satelusa.com/article-line-of-sight-radio-range-antenna-heights/) | 3/5 | - |
| [Étude expérimentale LoRa sur eau de mer — MDPI Sensors](https://www.mdpi.com/1424-8220/18/9/2853) | 4/5 | 2018 |
| [Connectivité LoRaWAN en scénario marin — MDPI JMSE](https://doi.org/10.3390/jmse9111218) | 4/5 | 2021 |
| [Couverture océanique LoRaWAN (Açores) — PMC](https://ncbi.nlm.nih.gov/pmc/articles/PMC10490279) | 4/5 | 2023 |
| [Record de distance LoRaWAN 741 km — Gigazine](https://gigazine.net/gsc_news/en/20190801-lorawan-distance-world-record/) | 3/5 | 2019 |
| [Calculateur de budget de liaison LoRa — rftools.io](https://rftools.io/calculators/iot/lora-link-budget/) | 3/5 | - |
| [Impact des limites duty cycle/puissance SRD — EURASIP](https://link.springer.com/article/10.1186/s13638-019-1502-5) | 4/5 | 2019 |
| [ERC 70-03 — dispositifs SRD](https://www.readkong.com/page/erc-recommendation-70-03-1019047) | 4/5 | - |

Conflits et réserves : les pertes de diffraction (6–19 dB) sont des valeurs de modèle d'arête, pas des mesures sur vos terrains ; la sensibilité SF12 −137 dBm est la valeur datasheet (les études citent jusqu'à −148 dBm en conditions optimales) — une implémentation réelle perd typiquement 5–15 dB ; les distances des records stratosphériques ne sont pas transposables au sol, elles ne bornent que le budget.

## Questions ouvertes

- **Perte de diffraction réelle sur vos trajets** : seule une campagne de mesure (un nœud mobile contre un point haut de Tours, SF7 vs SF12, 20/30/40 km) remplacera les modèles d'arête par vos chiffres.
- **k local de design** : statistiques du gradient d'indice de réfraction en France (ITU-R P.453) pour arbitrer entre k = 4/3 nominal et un k pire-cas pour les liens critiques.
- **SF cible de MeshCore** : si le design nominal est SF7–SF9 (débit/latence), la pénombre sous-horizon devient quasi inutilisable — quel SF assumez-vous pour les liens de bord ?
- **Poche 869,4–869,65 MHz (500 mW / 10 %)** : MeshCore l'exploite-t-il ? +3 dB de budget et un duty cycle dix fois plus large changent le calcul.

## Recommandations

1. **Garder LOS + Fresnel 0,6·r1 comme critère de design principal** (colonne vertébrale répéteur↔répéteur) ; traiter la diffraction comme extension chiffrée de couverture, jamais comme régime nominal.
2. **Faire évoluer la spécification du profil A↔B** : sortie = marge en dB par SF (et perte de diffraction de l'obstacle dominant), plutôt qu'un booléen. « Sous l'horizon » devient un graduel.
3. **Un bench réel d'une journée** : point haut de Tours ↔ zone basse sous l'horizon à 30–40 km, deux SF, deux heures de créneaux météo différents — il validera (ou démentira) les 12–26 dB de marge du modèle.
4. **Documenter la variabilité de k** dans l'outillage : k = 4/3 pour le masque (cohérence), avec avertissement explicite que la météo déplace l'horizon réel de part et d'autre.