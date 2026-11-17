# Recette à effectuer sur Android

État initial : **non effectuée sur appareil**. Relever modèle Android, version d'AlpineQuest, date et réseau utilisés. Commencer par Belledonne avant de charger les Alpes.

| Essai | Manipulation | Résultat attendu | État |
|---|---|---|---|
| Import | Importer dist/bera-belledonne.kmz | Zone et repère central visibles | À tester |
| Clic | Sélectionner zone puis fiche | Description complète accessible | À tester |
| Liens | Ouvrir lien XML et éventuel PDF | Source officielle accessible en ligne | À tester |
| Péremption | Lire fiche actuelle grise | Indisponibilité explicite, dates anciennes identifiées | À tester |
| Altitudes | Importer demo/bera-belledonne.kmz | ARCHIVE 2025 ; 1 sous 2000 m, 2 au-dessus ; jamais affiché comme actuel | À tester |
| Styles | Comparer demo au fond IGN | Jaune translucide, fond lisible ; bordure sélectionnable | À tester |
| AQX | Servir dist ou déployer ; importer AQX | PNG transparents au-dessus du fond IGN | À tester |
| Zoom TOP 25 | Zoomer jusqu'à l'échelle habituelle | Couche reste visible ; sinon élargir niveaux et retester | À tester |
| Contours stables | Afficher bera-contours.kmz avec AQX | Bordures neutres, clic vers fiche web du massif | À tester |
| Cache | Revenir en ligne après nouvelle génération | Nouveaux horodatages/tuiles chargés ; 0D ne promet pas un push sur une vue immobile | À tester |
| Hors ligne | Mode avion après mise en cache | Carte déjà chargée et KMZ lisibles, date toujours vérifiable | À tester |
| MBTiles | Ouvrir bera.mbtile, ajouter comme couche | Bon emplacement, alpha conservé, IGN visible | À tester |
| Extension | Importer bera-alpes.kmz | 23 zones ; Chartreuse, Vercors, Grandes-Rousses et Oisans sélectionnables | À tester |

Si AlpineQuest supprime le HTML ou rend mal les liens dans les descriptions, tester le repère central et recopier l'URL depuis la fiche ; noter le résultat pour ajuster le format. Aucun contournement n'est présenté comme déjà validé.
