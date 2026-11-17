# Mise en service du dépôt caf-bera

Le workflow **BERA quotidien** génère les fichiers pour AlpineQuest avec le secret de dépôt `MF_API_KEY`.

- Fichiers publiés après activation de Pages : https://jfmouret.github.io/caf-bera/
- Exécutions : https://github.com/jfmouret/caf-bera/actions
- Si la configuration Pages échoue : Settings → Pages → Build and deployment → Source → GitHub Actions, puis relancer le travail échoué.

# CAF — BERA dans AlpineQuest

Paquet réalisé le 17 novembre 2026. Données : **Météo-France**, Licence Ouverte 2.0, plus conditions de l'API jointes dans `data/licence-donnees.md`. Les scripts réalisent une transformation indépendante ; ce projet n'est pas un produit officiel de Météo-France.

## Ouvrir immédiatement sur Android

1. Décompresser le paquet, puis copier `dist/bera-belledonne.kmz` dans Téléchargements sur Android.
2. Dans AlpineQuest : **Repères → Explorer les repères → Téléchargements**, sélectionner le KMZ, attendre l'importation, puis **Afficher**. Les intitulés peuvent varier selon la langue et la version.
3. Choisir le fond IGN TOP 25 déjà disponible dans votre configuration AlpineQuest.
4. Aller en Belledonne (environ 45.274 N, 6.002 E). Sélectionner la zone et ouvrir son nom/sa fiche. Un repère central « Belledonne — fiche BERA » fournit le même contenu si sélectionner la zone est difficile.
5. Vérifier les dates, les altitudes, les orientations, la stabilité, l'évolution et les liens. Le fichier actuel est gris si aucun bulletin valide n'a pu être obtenu. Le gris ne signifie jamais « risque faible ».
6. Pour tester une couleur avec des données véritables, importer séparément `demo/bera-belledonne.kmz` : **ARCHIVE du 15/02/2025, exercice uniquement**. Ne pas laisser cet exercice affiché lors d'une sortie réelle.
7. Pour l'ensemble des 23 massifs des Alpes françaises : importer `dist/bera-alpes.kmz`.

Les fichiers KML/KMZ fournis sont syntaxiquement vérifiés et prêts pour un essai d'import. **Aucun Android ni AlpineQuest n'est disponible dans cet environnement : le rendu, le clic sur les zones et l'ouverture des liens dans l'application restent à valider sur votre appareil.** Ne pas confondre cette vérification de fichiers avec un test réussi dans AlpineQuest.

## Solution dynamique retenue

| Composant | Fonction | Actualisation |
|---|---|---|
| Fond IGN TOP 25 | Topographie | Selon votre source/licence existante |
| `bera.aqx` + tuiles PNG RGBA | Couleurs BERA transparentes au-dessus du fond | Requête à chaque affichage en ligne (`0D`) ; génération serveur programmée |
| `bera-contours.kmz` | Zones cliquables neutres et repères centraux | Contours stables ; lien vers la fiche en ligne actualisée |
| `bera-alpes.kmz`, `bera-belledonne.kmz` | Instantané avec descriptions complètes et couleurs | Retélécharger et réimporter pour actualiser les informations embarquées |
| `bera.mbtiles` / `bera.mbtile` | Instantané raster hors ligne facultatif | Nouvelle copie nécessaire ; aucune actualisation hors ligne |

Le KML de contours neutres évite de superposer des couleurs d'un ancien bulletin à des tuiles nouvelles. Le clic propose un lien vers `index.html#massif-ID`, qui ouvre la fiche actualisée dans le navigateur. L'affichage de la description elle-même dans AlpineQuest reste statique. Le clic n'interroge pas l'API et n'expose aucun identifiant.

La documentation officielle confirme les zones KML/KMZ, les couches AQX raster `layer="true"` et les cartes MBTiles raster. Elle ne permet pas de garantir un rafraîchissement permanent des objets KML importés. Aucun `NetworkLink` non vérifié n'est utilisé. **AQX ne charge ni GeoJSON ni KML distant.** La mise à jour serveur est automatique ; le remplacement automatique d'une fiche KML détaillée à l'intérieur d'AlpineQuest n'est pas établi.

## Essai AQX sans hébergement public

Le fichier livré pointe vers `http://127.0.0.1:8765`. Il fonctionne uniquement si un serveur tourne **sur le même appareil**. Deux possibilités de test :

- Sur Android, avec un environnement Python/Termux déjà configuré : placer le dossier du projet sur l'appareil, lancer `python serve.py --directory dist`, puis ouvrir `dist/bera.aqx` avec AlpineQuest. L'installation de Termux/Python dépend de votre appareil et n'a pas été testée ici.
- Sur un ordinateur du même Wi-Fi : lancer le serveur dans ce dossier et remplacer `127.0.0.1` dans l'AQX **et dans le KML de contours** par l'adresse IP locale de l'ordinateur. Pour régénérer les deux correctement : `python bera.py --all-alps --base-url http://ADRESSE_IP:8765`. L'adresse IP réelle doit être fournie par votre réseau. Autoriser le port local si votre pare-feu le demande. HTTP local peut être refusé selon la version Android ; préférer l'hébergement HTTPS pour l'usage normal.

Une fois le serveur accessible depuis le navigateur Android : ouvrir `bera.aqx` depuis le gestionnaire de fichiers, choisir AlpineQuest, sélectionner le fond IGN puis la couche CAF BERA dans Cartes et couches. Importer aussi `bera-contours.kmz`. Tester à plusieurs niveaux de zoom, dont le niveau utilisé pour TOP 25. Les tuiles sont produites aux niveaux XYZ 6 à 12 ; le comportement d'agrandissement au-delà de 12 reste à vérifier dans AlpineQuest. Si nécessaire, étendre les niveaux dans le générateur, en tenant compte du volume.

Pour tester les tuiles de l'exercice, servir `demo` au lieu de `dist`. Ne pas mélanger les deux dossiers.

## Hors ligne

Le KMZ détaillé se suffit à lui-même pour le texte ; ses liens externes nécessitent Internet. Le MBTiles conserve l'alpha PNG, les niveaux 6–12 et l'indexation TMS inversée. Une copie `bera.mbtile` est fournie car la documentation AlpineQuest mentionne cette extension au singulier. Dans **Cartes et couches → Cartes disponibles → Cartes stockées**, choisir le dossier du fichier. Sur Android 11+, utiliser un dossier autorisé par l'application si Téléchargements n'est pas visible.

Tester l'ajout comme couche au fond IGN et régler l'opacité. Le comportement exact de superposition MBTiles reste à valider sur appareil. Le mode préféré pour la superposition est l'AQX ; le MBTiles est une solution facultative. Pour un cache hors ligne AQX, charger la zone pendant la connexion, puis tester le mode stockage local de l'application.

**Un cache ou un MBTiles peut conserver un bulletin périmé.** La fin de validité est imprimée sur les tuiles portant des données. Le cache n'efface pas automatiquement les anciennes couleurs à l'heure de péremption. Avant une sortie, contrôler les dates et télécharger un nouveau jeu de données. En l'absence de réseau, ne pas assimiler une couleur visible à un bulletin encore valide.

## Installation et commandes

Python 3.10+ avec base de fuseaux IANA (sur Windows, installer aussi `tzdata` si nécessaire).

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python bera.py --demo --mbtiles
python bera.py --all-alps --base-url https://VOTRE_DOMAINE/CHEMIN --mbtiles
python serve.py --directory dist
```

`VOTRE_DOMAINE/CHEMIN` est un paramètre à remplacer, pas une URL déployée. Le générateur lit `MF_API_KEY` dans l'environnement, sinon `MF_BEARER_TOKEN`, sinon les archives publiques uniquement. Ne pas mettre la clé dans un KML, un AQX, le code, un commit ou une discussion. Pour une automatisation durable, préférer une API Key configurée dans les secrets de l'hébergeur ; un jeton OAuth2 temporaire doit être renouvelé par son gestionnaire externe.

Sans `--all-alps`, seuls Chartreuse (7), Belledonne (8), Grandes-Rousses (12), Vercors (14) et Oisans (15) sont générés. Avec cette option, les 23 massifs officiels des Alpes sont inclus. **Taillefer n'est pas un massif distinct dans le GeoJSON officiel téléchargé** ; aucun polygone Taillefer indépendant n'est inventé. Utiliser le contour officiel à l'endroit considéré pour identifier le massif BERA, plutôt que déduire une appartenance de son nom géographique.

## GitHub Actions et Pages

Le workflow `.github/workflows/update.yml` est prêt à être installé **à la racine d'un dépôt**, avec les autres fichiers de ce projet. Il n'est pas activé dans votre compte et aucune URL publique n'a été créée.

1. Créer ou choisir un dépôt destiné au projet ; y déposer le contenu de ce dossier.
2. Dans les paramètres du dépôt, activer Pages avec source **GitHub Actions**.
3. Créer le secret de dépôt `MF_API_KEY` contenant votre clé après souscription à l'API Bulletin Avalanche. Cette étape se fait dans votre compte, sans communiquer la clé ici.
4. Lancer manuellement « BERA quotidien » depuis Actions et contrôler le résultat du déploiement.
5. Ouvrir la page HTTPS publiée, télécharger l'AQX et le KMZ de contours depuis cette version. L'URL de Pages est injectée automatiquement dans les fichiers générés.
6. Vérifier une URL de tuile en ligne puis refaire l'essai Android. Le workflow s'exécute à 05:25, 11:25, 17:25 et 21:25 UTC (06:25, 12:25, 18:25 et 22:25 en France en hiver). Il tourne toute l'année pour publier aussi l'indisponibilité hors saison ; la production BERA est saisonnière. Les tâches planifiées peuvent être retardées par GitHub : ce n'est pas un service temps réel garanti.

L'option Pages est adaptée à une publication statique de ces données ouvertes, sous réserve des conditions du compte GitHub et des quotas applicables au dépôt. Aucun fond IGN n'est copié ni redistribué. Les autorisations Pages, les quotas et la planification devront être vérifiés au déploiement réel. Les tuiles transparentes du rectangle couvert sont fournies ; hors couverture, Pages peut renvoyer 404. Le serveur de test local renvoie une tuile vide à la place.

## Données et interprétation

- API officielle : `https://public-api.meteofrance.fr/public/DPBRA/v1/` ; routes vérifiées dans le Swagger : `liste-massifs`, `massif/BRA?id-massif=8&format=xml` et `format=pdf`.
- Authentification : API Key (en-tête `apikey`) ou OAuth2 (en-tête `Authorization: Bearer …`), après compte et souscription. L'appel sans authentification a réellement renvoyé **401**.
- Le portail technique annonce **50 requêtes/minute** pour cette API ; la fiche data.gouv indique 100. Retenir le plafond conservateur de 50. Les appels sont séquentiels et espacés lorsque l'API est utilisée.
- XML, PDF, images PNG auxiliaires disponibles via l'API. Le XML porte le texte et les attributs des cartouches, pas les images elles-mêmes. Le projet utilise les textes et codes ; il ne prétend pas restituer tous les pictogrammes.
- Production quotidienne au minimum, début novembre à début juin, avec amendements possibles. La date de validité vient du contenu XML et non du nom du fichier ou de sa date HTTP.
- Archives découvertes dans les index officiels : jour courant et deux jours précédents. Pas de repli silencieux sur un ancien danger coloré. Un bulletin expiré ou futur est gris ; ses informations anciennes restent identifiées comme telles dans la fiche.
- `DATEVALIDITE` et `DATEECHEANCE` sont des échéances, pas le début de validité. Le code retient la plus précoce, et refuse de colorer avant `DATEBULLETIN`. Quand les dates n'ont pas de fuseau, la convention du projet est l'heure civile `Europe/Paris` : le document XML consulté ne précise pas explicitement ce point. Les valeurs originales sont conservées dans JSON.
- Couleur : maximum du cartouche du massif ; niveaux séparés `RISQUE1/2`, localisations `LOC1/2`, altitude et évolutions conservés. Aucune limite altimétrique n'est découpée géographiquement : il faudrait un MNT et une méthode supplémentaire. Les localisations géographiques E/O/N/S ne sont pas interprétées comme des altitudes.
- Problèmes : texte intégral de stabilité et codes `SitAvalTyp`. Les libellés des codes 2 (« neige ventée ») et 6 (« pas de situation prédominante ») ont été vérifiés par rapprochement avec les PDF officiels joints ; les autres codes restent bruts, sans correspondance devinée. Les orientations de la rose désignent les pentes les plus dangereuses du cartouche ; elles ne sont pas arbitrairement attribuées à chacun des problèmes. Les altitudes et orientations propres aux problèmes sont accessibles dans le texte officiel intégral.
- Palette : 1 vert `#ccff66`, 2 jaune `#ffff00`, 3 orange `#ff9900`, 4 rouge `#ff0000`, 5 rouge et hachures noires **dans les tuiles**. Le KML utilise du rouge avec le libellé 5/5, sans hachures (styles KML limités dans AlpineQuest). Gris : aucune estimation actuelle validée.
- Un niveau BERA à l'échelle du massif ne qualifie pas le risque local d'une pente. Ce paquet n'est pas un outil de décision automatique d'itinéraire.

## Gestion des erreurs et limites restantes

Les téléchargements ont un délai maximal, trois essais pour les erreurs réseau/429/5xx et une attente croissante. Les erreurs 401/403/404 sont conservées comme indisponibilité, sans divulguer de clé. L'identifiant du XML est vérifié avant association. Les niveaux hors 1–5, maximums incohérents et dates impossibles sont refusés. Si rien n'est disponible, la couche reste grise avec un statut explicite. Les fichiers sont construits dans un dossier temporaire avant remplacement de la sortie ; une erreur de génération fait échouer le workflow.

Une panne d'exécution/déploiement peut laisser la précédente version publiée en ligne. Les dates imprimées sont donc indispensables. Le workflow ne surveille pas lui-même sa propre exécution ; consulter ses échecs dans Actions. L'actualisation en ligne des fiches est obtenue via le lien web des contours, pas par un comportement non documenté d'AlpineQuest.

La chaîne authentifiée et le déploiement Pages ne sont pas testés sans votre configuration. Le paquet contient le code pour les exécuter, pas la preuve d'un déploiement déjà en service. Le test Android détaillé est dans `RECETTE-ANDROID.md` ; les validations locales sont dans `VALIDATION.md`.

## Sources officielles consultées

- [API Bulletin Avalanche, data.gouv](https://www.data.gouv.fr/dataservices/api-bulletin-avalanche)
- [Archives, ressources et licence](https://www.data.gouv.fr/datasets/archive-des-bulletins-avalanches)
- [Documentation Météo-France : données expertisées](https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/874741792)
- [Documentation API Bulletin Avalanche](https://confluence-meteofrance.atlassian.net/wiki/spaces/OpenDataMeteoFrance/pages/854196230/API+Bulletin+Avalanche)
- [Détail actuel de l'API : sécurité, URL et quota](https://portail-api.meteofrance.fr/api/am/devportal/v3/apis/4337c3b5-d909-4ade-80cb-cd1cd8e28a6b)
- [Swagger téléchargé](https://portail-api.meteofrance.fr/api/am/devportal/v3/apis/4337c3b5-d909-4ade-80cb-cd1cd8e28a6b/swagger)
- [AlpineQuest : objets et formats importés](https://www.alpinequest.net/en/help/v2/placemarks)
- [AlpineQuest : import de repères](https://www.alpinequest.net/en/help/v2/placemarks/local-import-export-gen)
- [AlpineQuest : AQX, couches et cache](https://www.alpinequest.net/en/help/v2/maps/on-demand-create)
- [AlpineQuest : MBTiles raster et autres cartes stockées](https://www.alpinequest.net/en/help/v2/maps/file-based-select)

Les contours et bulletins bruts ainsi que les documents API/XML et de licence téléchargés sont joints dans `data/` et `dist/raw/`. L'échantillon officiel 2023 contient lui-même du texte de test de Météo-France ; il sert uniquement aux tests du parseur et n'est pas présenté comme un bulletin opérationnel.
