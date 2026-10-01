Calcul Mental v212

- Graphe réellement raccourci à droite (réserve SVG augmentée de 220 à 285).
- Falaise/panda élargis de 32% à 38% (42% mobile).
- Voile blanc et décor synthétique du graphe rendus nettement plus transparents.


## v219
- Graphe des progrès trié chronologiquement : dernier test à droite.
- Rechargement forcé des stats sans cache à chaque ouverture de Mes progrès.


## v224
- Une seule victoire spéciale par défi terminé.
- Si une étoile est gagnée, la fenêtre Nouveau record est supprimée pour cette partie.
- Même priorité pour un changement de niveau/couleur : aucune fenêtre record supplémentaire.


## v234
Stats live fiables depuis v229 : séances rewarded=0 visibles comme EN COURS, polling 2 s sans cache, détail live, index.html servi en no-store pour éviter une ancienne UI en cache.

## v235
- Aide « moitié » améliorée pour les dizaines impaires : ex. moitié de 70 = moitié de 60 + moitié de 10 = 30 + 5 = 35.
- Aide « compléments » améliorée lorsque l'écart dépasse 10 : passage visuel par la dizaine supérieure (ex. 45 → 50 → 60, +5 puis +10).

## v236
- Aide « Compléments » : lorsqu'une question a un écart strictement supérieur à 10, l'exemple proposé est désormais forcé à avoir lui aussi un écart strictement supérieur à 10 afin de rendre visible la méthode en deux sauts via la dizaine supérieure.

## v237
- Refonte de /admin > Aides pédagogiques en arbre de méthodes : une méthode unique par cas, avec Aide = autre exemple de la même branche et Correction = question réelle.
- Ajout explicite des branches Compléments (écart <=10 / >10) et Moitiés (partage simple / dizaine impaire / décomposition paire).
- Le backend force désormais les exemples d’aide à rester dans la même branche pédagogique que la question, notamment pour les deux branches de compléments et les différentes stratégies de moitié.
