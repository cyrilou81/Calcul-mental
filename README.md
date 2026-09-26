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
