# Validation du paquet — 17 novembre 2026

## Exécuté avec succès

- Téléchargement des contours officiels GeoJSON depuis la ressource du catalogue Météo-France sur data.gouv : 37 massifs au total, dont 23 alpins.
- Récupération et analyse de vrais bulletins XML d'archive : Belledonne du 15/02/2025 et du 15/11/2026, ainsi que les autres bulletins disponibles des Alpes pour le 15/11/2026. Le bulletin 2023 joint par Météo-France est un échantillon de test, traité séparément.
- Téléchargement d'un PDF historique Belledonne et des PDF du 15/11/2026 de Belledonne, Chartreuse, Grandes-Rousses, Oisans et Vercors ; signature PDF reconnue et extraction textuelle de contrôle pour Belledonne, Chartreuse et Vercors.
- Comparaison XML/PDF Belledonne du 15/02/2025 : 1 sous 2000 m, 2 au-dessus. Le PDF du 15/11/2026 confirme la date et le massif du XML correspondant.
- Neuf tests automatisés : bulletin réel, séparation altimétrique et évolution sur l'échantillon officiel, mauvais identifiant, niveau invalide, dates futures et échéances, description et géométrie KML, absence de réseau, PNG RGBA et MBTiles, couche AQX raster.
- Validation des sorties finales : 23 zones dans le KMZ Alpes, 1 dans le KMZ Belledonne ; XML lisibles, ZIP/KMZ intègres. Les anneaux KML sont fermés et leur sens est normalisé.
- 1 636 tuiles PNG RGBA dans la sortie Alpes ; 88 dans l'exercice Belledonne. Les tuiles vides du rectangle de couverture sont incluses. Pixel intérieur contrôlé dans la couche d'exercice : jaune RGBA (255,255,0,85), donc translucide. Une tuile d'exercice a aussi été inspectée visuellement : mention ARCHIVE et échéance lisibles.
- Intégrité SQLite des MBTiles et nombre de tuiles concordant ; inversion XYZ vers TMS effectuée. Copies `.mbtile` fournies.
- Serveur HTTP local : page, AQX, KMZ détaillé, KMZ de contours, JSON et URL PNG répondent 200. Aucune URL publique de ce projet n'est encore déployée.
- Swagger, modalités de sécurité et licence téléchargés depuis le portail officiel. Appel API sans authentification : 401, attendu.

## Disponibilité au moment de la génération

Les répertoires XML officiels des 16 et 17 novembre ne contenaient aucun fichier lors de la consultation. Les bulletins récupérés du 15 novembre expirent le 16 novembre à 18 h. La sortie actuelle est donc entièrement grise et ne présente aucun de leurs niveaux comme le danger du 17 novembre. Bauges est sans bulletin récupéré ; les informations anciennes des autres massifs sont identifiées comme périmées. Les résultats détaillés et les heures de vérification sont dans `dist/bulletins.json`.

Le mode exercice est distinct et explicitement historique. Son niveau jaune 2 est une donnée du bulletin de février 2025, jamais une donnée actuelle.

## Non exécuté et nécessaire avant validation opérationnelle complète

- Import et rendu sur Android dans AlpineQuest ; sélection des polygones, présentation HTML et liens cliquables.
- Superposition AQX + IGN + contours et comportement au zoom TOP 25.
- Cache AlpineQuest, retour de connexion, utilisation MBTiles comme couche et conservation de la transparence à l'import.
- Appel API avec une clé valide : aucune clé de l'utilisateur n'a été utilisée.
- Déploiement GitHub Pages et exécution planifiée : aucun dépôt ni compte n'a été configuré.

Ces limites sont reprises dans la recette Android et dans le guide. Le paquet est un livrable testable ; ce rapport n'atteste pas encore un fonctionnement observé dans AlpineQuest.
