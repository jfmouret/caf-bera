# CAF BERA — accès en ligne et paquet hors ligne

Les six passages quotidiens sont programmés à 06 h 30, 10 h 30, 14 h 30, 16 h 30, 18 h 30 et 20 h 30 Europe/Paris. GitHub peut retarder le démarrage. Les BERA sont interrogés aux trois horaires du soir ; les trois autres passages reprennent la dernière publication BERA et renouvellent les Nivôse. Les générations manuelles renouvellent les deux.

## En ligne

Le site publie les tuiles AQX BERA, les bulletins et PDF officiels accessibles, les graphiques Nivôse et des KMZ légers contenant les positions et liens permanents. Les textes, couleurs et dates BERA continuent de provenir des bulletins officiels. La dernière valeur de danger reste affichée jusqu'au remplacement, avec les dates réelles.

Les historiques Nivôse sont conservés trois jours. Les observations sont récupérées au pas horaire depuis l'API Observation autorisée (clé MF_OBS_API_KEY, repli MF_API_KEY), qui ne conserve que 24 heures. Les heures manquantes des dernières 24 heures sont redemandées ; aucun jour antérieur indisponible n'est reconstitué. Les heures réelles validity_time sont utilisées, dédupliquées, et les valeurs nulles restent indisponibles. Les courbes sont coupées aux lacunes. Température K vers °C, neige m vers cm, vent m/s vers km/h, selon la documentation officielle DPObs.

Le catalogue officiel contient 20 Nivôse dans les départements 04, 05, 06, 38, 73 et 74, dont AIGLETON-NIVOSE 38005402 à 2240 m. Il est renouvelé depuis l'API si elle est accessible. Les dernières mesures déjà publiées sont conservées en cas d'échec avec leur date et une mention de repli. Une impossibilité de récupérer la copie précédente interrompt la publication pour préserver l'historique.

Les repères légers s'importent une fois dans AlpineQuest. Toucher une station puis son lien ouvre les courbes actualisées ; les repères importés ne se renouvellent pas automatiquement. Les pages de stations vérifient la génération à l'ouverture puis toutes les cinq minutes ; les URL des images sont versionnées. Aucun NetworkLink AlpineQuest non vérifié n'est utilisé.

## Hors ligne, uniquement sur demande

Dans GitHub : Actions → BERA quotidien → Run workflow → branche main → cocher « Générer et publier le paquet hors ligne » → Run workflow.

La génération produit un seul caf-bera-hors-ligne.zip, partagé comme asset d'une release publique fixe hors-ligne. La dernière version de cet asset est remplacée à chaque demande ; elle n'est pas dupliquée dans les archives des générations en ligne. Les personnes qui téléchargent cet asset n'ont pas besoin de compte GitHub. La page hors-ligne.html affiche le lien et la date obtenus de l'API GitHub ; tant qu'aucun paquet manuel n'a été généré, elle le signale.

Le ZIP contient :
- bera-contours.kmz : massifs cliquables, BERA, illustrations officielles et PDF sous forme d'images locales ;
- nivose-alpes.kmz : stations, courbes et dernières mesures enregistrées ;
- bera.mbtile : couche raster BERA transparente, à superposer au fond IGN personnel ;
- LIRE-MOI.txt : date de génération et installation.

Les Nivôse hors ligne gardent trois jours maximum, un point (le dernier disponible) par tranche UTC de quatre heures. Les dates sont affichées en heure de Paris. Les courbes relient ces points espacés de quatre heures et interrompent les lacunes plus longues ; aucun point manquant n'est inventé. Une variation de hauteur totale de neige n'est pas un cumul de neige fraîche. Les textes et graphiques hors ligne sont figés à la date du paquet ; remplacer les imports pour les renouveler. L'affichage des images intégrées reste à tester dans AlpineQuest Android.

## Stockage et trafic

Les copies techniques en ligne portent le nom bera-en-ligne : deux dernières copies au maximum après nettoyage, expiration à un jour. Avant le nouveau transfert, après validation des données, une seule ancienne copie en ligne et la dernière archive Pages sont conservées. La dernière archive legacy bera-fichiers est conservée pendant la migration jusqu'au premier déploiement léger réussi ; les anciennes copies lourdes de ce nom sont alors supprimées. Après publication, le nettoyage exige la présence des nouvelles archives bera-en-ligne et github-pages avant toute suppression. Les autres noms d'artefacts ne sont pas touchés. Le jeton temporaire du workflow a actions: write pour ce nettoyage et contents: write pour publier le paquet hors ligne demandé.

L'historique Nivôse de trois jours est contenu dans ces petites copies en ligne ; il est indépendant de la durée de rétention des archives complètes. Le paquet hors ligne n'est produit que si la case de génération manuelle est cochée. Il reste téléchargeable en release jusqu'à son remplacement.

Un objectif de 1,5 Go/jour correspond à environ 45 Go sur 30 jours. Le trafic des visiteurs est indépendant du nombre de générations ; Pages ne fournit ici ni compteur quotidien ni coupure automatique à 1,5 Go. La limite souple documentée de Pages est 100 Go/mois, et la taille maximale du site publié 1 Go. Les quotas de stockage d'artefacts sont distincts du trafic et partagés au niveau du compte. Aucun budget ou moyen de paiement du compte n'est modifié par ce projet.

Source : Météo-France — Licence Ouverte 2.0.

Documentation API : https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/853639294/
Catalogue stations : https://www.data.gouv.fr/api/1/datasets/r/4250e317-1176-425d-880c-ebe9205efc89
Unités : https://www.data.gouv.fr/api/1/datasets/r/aaae09a4-4d5e-4191-a774-0a74d5214322
