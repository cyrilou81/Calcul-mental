# Calcul mental — v282

- Stats bornées : /api/stats accepte ?limit=N — le front envoie la période affichée (5 ou 10 derniers tests, « Tous » reste complet) et « Mes progrès » ne charge que les 8 dernières séances pour son graphe. Le bouton Stats ouvre l'écran immédiatement avec un « Chargement… » au lieu d'attendre le serveur. L'export CSV garde l'historique complet. Fini le recalcul de tout l'historique d'entraînements à chaque clic et à chaque rafraîchissement automatique.
