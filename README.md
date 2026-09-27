# Calcul mental — V1 locale

Application familiale locale de calcul mental.

## Fonctionnalités
- Profils enfants persistants
- 50 questions / 5 minutes de temps actif
- Doubles, additions, multiplications, divisions, compléments à 10, ajout de dizaines
- Pourcentages configurables (total 100 %)
- Sélection explicite des tables de multiplication et division
- Ajout de +10 seul ou sélection de multiples de 10
- Calculs affichés en ligne (`56 : 7 = __`)
- Pavé numérique à l'écran + clavier
- Correction rouge pendant 1,8 s ; le chronomètre est suspendu pendant la correction
- Seules les réponses fausses sont reprises à la séance suivante ; les non-réponses ne le sont pas
- Les reprises gardent exactement leur présentation
- Statistiques par séance et catégorie, temps médian, reprises
- Données brutes conservées dans SQLite (`calcul_mental.db`)

## Lancer sur macOS
Dans Terminal :

    cd /chemin/vers/calcul-mental
    ./start.sh

Puis ouvrir : http://127.0.0.1:5050

Le premier lancement crée l'environnement Python et installe Flask. Les suivants réutilisent cet environnement.

## Arrêter
Dans le Terminal : `Ctrl+C`.

## Données
La base SQLite est créée dans le dossier du projet. Pour sauvegarder toutes les données, il suffit de copier `calcul_mental.db`.



## Comptes utilisateurs

L’application utilise maintenant des comptes (identifiant + mot de passe) plutôt qu’un code d’accès global. Chaque profil appartient au compte qui l’a créé. Le premier compte créé dans une base provenant d’une ancienne version récupère les profils historiques. Les mots de passe sont hachés avec Werkzeug et ne sont jamais stockés en clair.

En production, définissez `SECRET_KEY` avec une valeur longue et aléatoire. La base SQLite doit rester hors de Git et être placée sur le disque persistant du serveur via `DB_PATH`.


## V30 — Gestionnaire de mots de passe
Le formulaire de connexion expose `name=username`, `autocomplete=username`, `name=password` et `autocomplete=current-password` afin que Safari, Chrome et les gestionnaires de mots de passe puissent proposer l’enregistrement et le remplissage automatique des identifiants.


## V32 — Déploiement Render
La base SQLite peut être déplacée via la variable d'environnement `DB_PATH`.

Configuration Render recommandée :
- Build Command : `pip install -r requirements.txt`
- Start Command : `gunicorn app:app`
- Persistent Disk mount path : `/var/data`
- Environment variable : `DB_PATH=/var/data/calcul_mental.db`

En local, sans `DB_PATH`, l'application continue d'utiliser `calcul_mental.db` à côté de `app.py`.


## Test de fumée

Après `pip install -r requirements.txt` :

`python tests/smoke_v99.py`


## V145b (rebase V144 utilisateur)
- Multiplications : ajout de 1000 aux choix de tables.
- Aide doubles 10–100 : décomposition explicite en dizaines et unités (ex. 15+15).
- Repart strictement de la V144 fournie par l’utilisateur pour éviter les régressions de V145.


## V148
- Statistiques : une bonne réponse obtenue au 2e essai est indiquée explicitement.
- Récompenses : fenêtre de victoire quand une image est terminée, avec son nom et l'image débloquée.
- Pavé numérique : ordre 1-2-3 / 4-5-6 / 7-8-9.
- Aide double de dizaines : « Calcule le double pour les dizaines et ajoute le zéro des unités. »

### V149
- Une question fausse au premier essai reste comptée comme une erreur, même si le deuxième essai est correct.
- Le détail des statistiques indique désormais « 2e essai réussi » ou « 2e essai échoué » pour ces erreurs.
- Suppression de la colonne « Essais » dans les tableaux de détail des statistiques.

## V151
- Défis enfant : les noms scolaires sont remplacés par des médailles numérotées ; toutes les médailles d'une même classe utilisent la même couleur.
- Administration : couleur configurable indépendamment pour CP, CE1, CE2, CM1 et CM2.
- Récompenses : un seul toucher sur l'image agrandie dépense automatiquement jusqu'à 10 pièces par case et révèle toutes les cases finançables, sans dépasser les cases restantes. Le reliquat de pièces est conservé.
- Si le solde est inférieur à 10 pièces, toucher l'image agrandie ferme immédiatement la vue et revient aux images en cours / révélées.

## V152
- Défis enfant : simples ronds colorés numérotés (plus de badges/médailles).
- Départ défi : une classe sous la classe réelle (CP reste CP), y compris migration unique des profils existants.
- Un niveau situé sous la classe réelle ne demande qu'une étoile ; à partir de la classe réelle, trois étoiles.
- +10 pièces pour une étoile, +20 pièces supplémentaires lors d'un changement de niveau, avec barres dédiées à l'écran de fin.
- Passage de couleur : fenêtre de victoire avec les deux couleurs et le message de transition.


## V153
- Admin : dans « Gérer les niveaux », les boutons CP/CE1/CE2/CM1/CM2 utilisent la couleur configurée pour chaque classe. Ce changement est limité à cette fenêtre.


## V154
- Fenêtre de changement de niveau : suppression de la classe (ex. CP-2). Seul le numéro du niveau est affiché dans un rond de la couleur de sa classe/palier.


## V155
- Admin : case « Actif » par niveau, cochée par défaut. Un niveau inactif conserve toute sa configuration mais est ignoré par les joueurs et par la progression des défis.


## V156
- Génération : évite les doublons par type d’opération ; si les possibilités sont épuisées, répartit les doublons avant d’autoriser des triplons, etc.
- Admin : bouton Supprimer restauré directement dans la liste des niveaux, en plus de la case Actif.

## V157
- Stats Défi : lors d'un passage au niveau suivant, l'historique statistique du niveau précédent est remis à zéro. Les stats Entraînement sont conservées.
- La séance qui déclenche la promotion est conservée uniquement comme marqueur du défi quotidien, mais n'apparaît pas dans les stats du nouveau niveau.

## V158
- Compléments de dizaines : cibles 10 à 100 et 1000, deux formulations.
- Valeur de position : m/c/d/u, probabilité d'absence 0–80 % par pas de 10.
- Addition à 3 termes, triple, quadruple, tiers et quart.


## V159
- Victoire de niveau : numéro du nouveau niveau centré.
- Victoire de couleur : suppression du rond de niveau, transition de couleurs uniquement.
- Fenêtre de victoire : hauteur adaptative sans barre de défilement ; illustration et espacements se réduisent selon la hauteur disponible.


## V160
- Fusion Triple/Quadruple en « Multiple de » avec choix Triple/Quadruple (au moins un).
- Fusion Tiers/Quart en « Fraction » avec choix Tiers/Quart (au moins un).
- Les deux catégories fusionnées sont placées en bas de la liste.
- « Compléments de dizaines » est placé juste après « Moitié de dizaine ».
- Migration transparente des anciennes configurations V159.

V161
- Écran de fin réorganisé en deux colonnes sur écran large : illustration à gauche, jauges de récompense à droite.
- Les jauges utilisent désormais la largeur disponible au lieu de s’empiler sous l’illustration.
- Retour automatique à une colonne sur mobile ; adaptation supplémentaire pour les écrans peu hauts.


## V162
- Correction V160/V161 : `multiple_of` et `fraction` sont maintenant réellement présents dans `DEFAULT.categories`, donc visibles dans « Autres exercices ».
- Suppression des quatre anciennes catégories techniques du DEFAULT ; leur migration reste prise en charge par `merged_cfg`.


## V163
- Compléments de dizaines : suppression de l'option Affichage ; format unique `X + __ = cible`, comme Compléments à 10.
- Nouvelle option compacte `Écart de [min] à [max]`, valeurs par défaut 5 à 20.
- La génération respecte cet écart pour toutes les cibles sélectionnées.


## V164
- Suppression de l'ancienne catégorie `Compléments à 10`.
- `Compléments de dizaines` est renommé `Complément`.
- Les anciens niveaux intégrés qui utilisaient `complement10` utilisent désormais `complement_tens` avec cible 10 et écart 1 à 9.


## V165
- Libellés : Compléments, Fractions, Moitiés de dizaines, Additions de dizaines, Multiples.
- Valeur de position déplacée juste sous Moitiés de dizaines.
- Nouvelle catégorie `round_tens_add` : Ajout à dizaine ronde.
- Premier terme sélectionnable parmi 10,20,...,90 ; second terme configurable par intervalle min/max.


## V166
- Correction de l'aperçu des catégories : un aperçu isolé force désormais la catégorie testée à 100 %, ce qui supprime le faux `Réglages à vérifier`.
- Validation explicite de `Ajout à dizaine ronde` (au moins une dizaine cochée et intervalle du second terme cohérent).


## V167
- Les points de fréquence (`weight`, 1 à 5) deviennent la source de vérité de la répartition.
- Le serveur normalise automatiquement les poids ; `pct` n'est plus qu'une valeur dérivée de compatibilité.
- Suppression de la validation historique imposant un total manuel de 100 %.
- Le nombre exact de questions est réparti directement au prorata des points.


## V168
- Basée sur V167. Correction des aperçus : une carte est prévisualisée seule, sans validation parasite des autres catégories.


## V169
- Correction des anciens niveaux enregistrés contenant encore `complement10`.
- Migration automatique de `complement10` vers `complement_tens` avec cible 10.
- L'aperçu isolé désactive désormais toutes les catégories présentes dans la config, y compris les anciens identifiants qui ne figurent plus dans l'interface.


## V170
- Correction du démarrage Entraînement après un Défi.
- Le report des erreurs cherche désormais uniquement la dernière séance d'entraînement, jamais le dernier Défi.
- La configuration est validée/normalisée au démarrage d'une séance.
- Une erreur de démarrage est désormais affichée au lieu de donner l'impression que le bouton ne fait rien.


## V171
- Moitiés : plage configurable des valeurs paires hors dizaines rondes, par défaut 2 à 10.
- Option Dizaines indépendante : ajoute 10,20,...,100 sans être limitée par la plage.
- Anti-doublons renforcé : catalogue de candidats par catégorie et tirage au niveau d'utilisation minimal.
- Catalogues exhaustifs pour Moitiés, Doubles, Ajout à dizaine ronde et Compléments ; réserve unique élargie pour les catégories complexes.


## V172
- Moitiés : menu Hors dizaines / Dizaines / Les deux ; plage dynamique masquée en mode Dizaines.


## V173
- Correction des aperçus « Autres exercices » affichant parfois « Réglages à vérifier », notamment avec les anciennes configurations de Moitiés.
- Les exercices non sélectionnés disposent maintenant eux aussi du bouton Configurer.
- La configuration d'un exercice dans « Autres exercices » ne l'ajoute pas automatiquement : Ajouter reste une action séparée.
- Correction du masquage dynamique de la plage des Moitiés dans la vraie fenêtre `.cf-params`.


## V174
- Moitiés : en mode Dizaines ou Les deux, choix individuel des dizaines 10 à 100.
- Toutes les dizaines sont cochées par défaut.
- Le sélecteur de dizaines est masqué en mode Hors dizaines.
- En mode Dizaines, la plage hors dizaines reste masquée ; en mode Les deux, les deux réglages sont visibles.


## V175
- Les cartes d'exercices affichent désormais 4 exemples au lieu de 5.
- La zone « Autres exercices » utilise toute la largeur disponible.
- Les cartes « Autres exercices » sont disposées sur 2 colonnes sur grand écran.
- Dans chaque carte non sélectionnée, les 4 exemples sont affichés en grille 2 × 2 sous le titre/configuration.
- Les titres des cartes « Autres exercices » restent sur une seule ligne sur grand écran.
- Sur petit écran, retour automatique à une carte par ligne.


## V176
- Correction du preview des Moitiés : les dizaines décochées ne peuvent plus réapparaître dans l'aperçu.
- L'aperçu de la fenêtre de configuration utilise immédiatement la sélection courante des cases 10 à 100.
- L'aperçu de configuration affiche désormais lui aussi 4 exemples.


## V177
- Correction réelle du bug des dizaines dans Moitiés : le générateur standard utilisait encore en dur 10,20,...,100.
- Il utilise maintenant exclusivement `tensValues`, donc uniquement les dizaines cochées.
- Le catalogue anti-doublons utilisait déjà `tensValues`; les deux chemins de génération sont désormais cohérents.


## V178
- Ajout à dizaine ronde : le premier terme propose Hors dizaines / Dizaines / Les deux.
- Hors dizaines affiche une plage configurable (1 à 99 par défaut) et exclut les multiples de 10.
- Dizaines conserve le choix individuel 10 à 90.
- Les deux affiche la plage hors dizaines et les cases de dizaines.
- Les options sont affichées/masquées dynamiquement.
- Le générateur et l'anti-doublons respectent ce nouveau réglage.


## V179
- Suppression de la catégorie séparée « Double de dizaines ».
- « Doubles » propose maintenant Hors dizaines / Dizaines / Les deux.
- Défaut : Hors dizaines, plage 1 à 9.
- En mode Dizaines ou Les deux, choix individuel des dizaines 10 à 100.
- Réglages affichés dynamiquement selon le mode.
- Migration des anciennes configurations « Double de dizaines » vers « Doubles ».
