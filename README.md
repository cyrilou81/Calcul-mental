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


## v238
- Source pédagogique unique dans `static/pedagogy.js`, partagée par le test et `/admin`.
- `/admin` affiche directement le texte et le rendu produits par le même moteur que le test.
- Aide et correction utilisent la même méthode ; seule la question fournie diffère.
- Dans la fenêtre d’aide, l’explication verte est placée avant le schéma/exemple.

## v239
- Aide sans boucle : suppression du tirage serveur pouvant chercher jusqu'à 200 exemples.
- Source de vérité pédagogique consolidée dans `static/pedagogy.js` : branche, exemple d'aide et rendu utilisent le même moteur côté interface.
- Compléments > 10 : exemple garanti dans la même branche, avec passage par la dizaine supérieure.
- Moitiés vérifiées : 30/50/70/90 utilisent la dizaine précédente + moitié de 10 ; les autres branches restent distinctes.
- La route `/help` ne fait plus que mémoriser l'utilisation de l'aide.

## v240
- Répare le bouton Aide : l'affichage est désormais immédiat et n'attend plus l'appel statistique /help.
- Le marquage help_used est asynchrone et ne peut plus bloquer l'interface.
- Garde pedagogy.js comme source unique pour Aide, Correction et /admin.
- Ordre visuel corrigé : méthode verte avant l'exemple orange.
- Vérification conservée de la branche moitié des dizaines impaires (30/50/70/90).

## v241
- Aide pédagogique : pools explicites d'exemples par branche.
- Le test tire un seul exemple au hasard dans le pool de la branche, après exclusion de la question identique ; aucune boucle de recherche.
- /admin affiche directement les pools réellement utilisés par le test : source unique de vérité.
- Correction et Aide utilisent toujours le même moteur pédagogique ; seule la valeur d'entrée change.


## v242
- Corrige le chargement du moteur pédagogique partagé : Flask sert les fichiers statiques à la racine (`/pedagogy.js`), pas sous `/static`.
- Le bouton Aide et /admin chargent désormais la même source pédagogique réelle.


## v243
- Sur tablettes et écrans tactiles de plus de 480 px, le bloc question + clavier est remonté d'environ 50 à 78 px selon la hauteur d'écran.
- Les règles iPhone (<=480 px) restent inchangées.

## v250
- Multiplications : séparation des tables 1–20 et des multiplicateurs 10/100/1000/10000, avec plages de 2e facteur indépendantes.
- Migration des anciens réglages 100/1000 vers la nouvelle famille.
- Moitiés : ajout des options « centaines rondes » et « milliers ronds ».

## v256
- Aide Moitiés : nouvelle branche « Dizaine paire : 20 / 40 / 60 / 80 » avec moitié du chiffre des dizaines puis ajout du zéro.
- Aide Moitiés : branche impaire 30 / 50 / 70 / 90 conservée.
- Aide Doubles des dizaines rondes : consigne reformulée « Calcule le double du chiffre des dizaines et ajoute le zéro des unités. »
