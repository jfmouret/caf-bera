# Stations Nivôse des Alpes

`nivose.py` ajoute deux instantanés de repères cliquables à la publication existante :

- `nivose-belledonne.kmz` : AIGLETON-NIVOSE, station 38005402, altitude officielle 2240 m.
- `nivose-alpes.kmz` : stations portant NIVOSE dans le catalogue officiel, départements 04, 05, 06, 38, 73 et 74.
- `nivose.html` : fiches et téléchargements en ligne.
- `nivose.json` : mesures normalisées, heures, provenance et erreurs.

Le catalogue officiel enregistré le 17/11/2026 contient 20 stations dans ce périmètre. La liste est renouvelée depuis l'API lorsque l'accès est autorisé. Ce périmètre correspond aux stations disponibles dans le catalogue, sans inventer une station par massif. Le réseau nivo-météorologique des observateurs partenaires est un autre réseau.

## Accès et production

API : `https://public-api.meteofrance.fr/public/DPObs/v2/`

Routes documentées : `liste-stations`, puis `station/horaire?id_station=38005402&format=geojson`.

Le workflow utilise `MF_OBS_API_KEY` si ce secret existe ; sinon il essaie `MF_API_KEY`. La clé doit autoriser l'API **Données d'observation**. La clé reste côté GitHub et n'est pas écrite dans les fichiers publiés. Une erreur 401/403 suspend les requêtes suivantes, signale l'accès refusé et laisse les repères disponibles avec la mention « Mesures indisponibles ». Une dernière mesure déjà publiée est conservée avec sa date et une mention de repli.

Les collectes Nivôse ont lieu toutes les deux heures à H+15 aux heures paires, Europe/Paris (00:15, 02:15…22:15), ainsi qu'aux passages BERA de 16 h 30, 18 h 30 et 20 h 30, aux exécutions manuelles et aux changements de code. Les tâches de deux heures reprennent l'artefact de la dernière publication réussie pour préserver les BERA sans les interroger de nouveau. Un échec de reprise bloque la publication et préserve le site précédent. GitHub peut retarder les exécutions. L'heure de la mesure et celle de la copie sont distinctes ; une mesure de plus de trois heures est signalée comme ancienne.

Les unités suivent le descriptif officiel DPObs mis à jour le 30/06/2026 : `t` en K converti en °C, `sss` en m converti en cm, `ff` et `raf` en m/s convertis en km/h, `dd` en degrés de provenance, `u` en %. `raf` est la rafale maximale sur l'heure. Les valeurs nulles restent indisponibles, jamais transformées en zéro. L'identifiant de station et l'horodatage sont contrôlés ; les mesures futures sont écartées.

## Dans AlpineQuest

Télécharger le KMZ Alpes et l'ouvrir/importer comme repères. Afficher avec IGN, BERA V4 et les contours BERA existants. Le KMZ Belledonne est une alternative pour tester uniquement Aigleton ; importer les deux crée un doublon pour cette station. Toucher un repère pour lire les mesures. Texte et icône sont intégrés au KMZ, sans besoin de réseau pour lire l'instantané enregistré. Le lien vers la fiche officielle de station nécessite du réseau. Pour renouveler les données, remplacer l'ancien import par le KMZ actualisé. L'affichage exact des fiches reste à tester sur l'appareil Android.

Les observations sont ponctuelles au site de la station. Une variation de hauteur totale du manteau neigeux n'est pas une mesure de neige fraîche. Aucun niveau de danger d'avalanche n'est déduit de ces mesures.

## Sources officielles

- Documentation : https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/853639294/
- Catalogue CSV : https://www.data.gouv.fr/api/1/datasets/r/4250e317-1176-425d-880c-ebe9205efc89
- Paramètres et unités : https://www.data.gouv.fr/api/1/datasets/r/aaae09a4-4d5e-4191-a774-0a74d5214322
- Portail de souscription : https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesObservation
- Source Météo-France — Licence Ouverte 2.0.

Validation : tests de conversion d'unités, nulls, identifiant, date future, catalogue et KMZ autonome. Les tests utilisent des valeurs artificielles pour les conversions ; elles ne sont jamais publiées comme observations réelles.

## Courbes et actualisation

Chaque station dispose d'une page permanente `nivose/ID.html` : le lien « Courbes actualisées en ligne » dans le repère l'ouvre sans nouvelle importation du KMZ. La page vérifie la génération à l'ouverture et toutes les cinq minutes. L'actualisation automatique des repères importés / NetworkLink n'est pas garantie par la documentation AlpineQuest et n'est pas utilisée.

Les graphiques PNG représentent vent moyen et rafale maximale horaire, température (rouge au-dessus de zéro, bleu en dessous), et hauteur totale de neige en cm. Les images sont intégrées au KMZ pour consultation hors connexion. La copie locale ne s'actualise qu'après réimportation. L'affichage des images dans la fiche doit être testé sur Android ; le lien vers la page permet aussi leur consultation en grand.

L'API Observation conserve 24 heures : la première collecte redemande les mesures des 23 heures précédentes et la mesure courante ; les collectes suivantes complètent les heures manquantes. Les heures réelles `validity_time` sont dédupliquées et conservées pendant sept jours dans `nivose.json`, publié et sauvegardé avec l'artefact GitHub. Les journées antérieures non récupérables ne sont pas reconstituées. Si la copie précédente ne peut être récupérée (hors premier démarrage HTTP 404), la publication est interrompue pour éviter d'effacer l'historique. Les courbes sont interrompues pour les lacunes de plus de 90 minutes et pour les valeurs nulles ; aucune interpolation de ces lacunes. Les requêtes sont espacées de 0,7 seconde, sous la limite de 100/min avec ce client séquentiel. Les variations de hauteur totale ne sont pas renommées chutes de neige, car tassement, fonte et transport par le vent influencent la mesure.
