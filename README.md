# Calcul mental — v280

- Correctif performance : stats et conseil étoile relisaient toute la table des questions à chaque séance (aucun index en base) — « Mes progrès » gelait et tout le site ralentissait dès que l'historique grandissait. Index SQLite ix_questions_session(session_id,status) et ix_sessions_level(profile_id,mode,challenge_level_id), requête agrégée unique pour les scores du conseil, et affichage de « Mes progrès » qui n'attend plus la carte conseil (elle apparaît en tâche de fond). Mesuré : star-advice 829 ms → 5 ms sur une base de 126 000 questions.
