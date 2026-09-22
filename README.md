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
