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

Les générations suivent les horaires BERA : 16 h 30, 18 h 30 et 20 h 30 Europe/Paris, ainsi que les exécutions manuelles et les changements de code. Il ne s'agit pas d'un suivi continu des mesures horaires. L'heure de la mesure et celle de la copie sont distinctes ; une mesure de plus de trois heures est signalée comme ancienne.

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
