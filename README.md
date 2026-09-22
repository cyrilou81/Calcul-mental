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
