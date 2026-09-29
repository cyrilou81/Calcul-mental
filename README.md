# Calcul mental

Application Flask + SQLite d'entraînement au calcul mental pour enfants.

## Lancer en local

```bash
pip install -r requirements.txt
python app.py
```

Application : http://127.0.0.1:5050

## Déploiement

Compatible Gunicorn / Render. La base est définie par `DB_PATH` (par défaut `calcul_mental.db`).

## Fonctionnement actuel

- Profils enfants et authentification parent.
- Entraînement configurable par catégories avec fréquence `weight`.
- Défi quotidien et progression par niveaux.
- Génération anti-doublon commune aux tests et aperçus : contrôle uniquement dans la même catégorie, avec 3 relances maximum.
- Statistiques séparées entre défis et entraînements.
- Récompenses et collections.

Le code ne conserve pas de compatibilité avec les anciennes catégories ou l'ancien système `pct`.


## V194
- Admin : export de tous les niveaux en JSON (configuration, ordre, état actif et couleurs de classe).
- Admin : import/restauration d'un export ; le fichier est validé intégralement avant de remplacer les niveaux actuels.
- Les données utilisateurs, séances et récompenses ne font pas partie de l'export.


## V195
- Suppression de la migration V180 de `round_tens_add`.
- Suppression du comportement de création de compte hérité de V28.
- Les deux grandes images intégrées en base64 ont été sorties de `index.html` vers des fichiers PNG statiques.
- Suppression des commentaires CSS historiques numérotés, sans modifier les règles CSS.
