# Correction AQX V3

Réimporter `bera.aqx` et afficher uniquement la couche **BERA V3** en masquant les anciennes couches BERA V1/V2. Le cache et les URL de tuiles V3 sont distincts. Les KMZ avec textes et illustrations hors ligne sont conservés.

Les libellés sont désormais ancrés sur le centre géographique officiel de chaque massif, puis découpés sur la grille de tuiles. Ils ne sont plus répétés aux bords des tuiles. Les niveaux de vue générale 6–8 affichent les polygones sans bandeaux de texte pour éviter leur agrandissement depuis des tuiles de secours. Les limites de tuiles disponibles sont indiquées dans l'AQX à chaque niveau de zoom.

Une absence de couleur de danger peut être normale : un bulletin expiré, futur ou indisponible reste gris. La génération conserve la date réelle du bulletin obtenu et n'attribue pas de nouveau danger par supposition.

# CAF — BERA dynamique dans AlpineQuest

Publication : https://jfmouret.github.io/caf-bera/

Source : **Météo-France**, Licence Ouverte 2.0 et conditions de l'API jointes dans `data/licence-donnees.md`. Transformation indépendante destinée aux formations neige et avalanches. Aucun fond IGN n'est redistribué.

## Fichiers pour Android

| Fichier publié | Fonction |
|---|---|
| `bera.aqx` | Tuiles transparentes BERA au-dessus du fond IGN ; actualisation en ligne |
| `bera-contours.kmz` | Contours neutres des 23 massifs, texte agrandi et illustrations hors ligne, avec un lien PDF en ligne |
| `bera-belledonne.kmz` | Instantané détaillé Belledonne |
| `bera-alpes.kmz` | Instantané détaillé des 23 massifs |
| `bera.mbtile`, `bera.mbtiles` | Instantané raster facultatif pour le hors ligne |

Importer l'AQX dans AlpineQuest et afficher cette couche au-dessus du fond IGN. Importer les contours depuis Repères → Explorer les repères, puis Afficher. Les KMZ détaillés sont facultatifs et nécessitent une nouvelle importation pour renouveler les informations enregistrées.

Après une modification du KMZ, masquer/supprimer l'ancien import puis importer la nouvelle version : AlpineQuest ne met pas automatiquement à jour les repères déjà importés.

## Lisibilité et accès au PDF

Les bandeaux des tuiles utilisent un texte de 16 pixels et une largeur ajustée au contenu. Les noms longs sont répartis sur plusieurs lignes. La fin de validité reste visible. La version de cache AQX est `CAFBERA2026V3` : réimporter l'AQX, puis masquer l'ancienne couche si elle reste affichée.

Les fiches des contours contiennent le texte agrandi, les dates et les illustrations du bulletin enregistrées dans le KMZ. Le cartouche danger/altitude/orientations et les pictogrammes de situations avalancheuses sont repris du PDF officiel, sans redessin ni correspondance de code supposée. Les pages complètes du PDF sont aussi conservées comme images locales. Le nom du massif et la date de rédaction du PDF doivent correspondre au XML ; sinon les illustrations sont écartées et signalées comme indisponibles.

Le lien « PDF officiel — connexion requise » est distinct du contenu hors ligne. Il ouvre `bulletins/ID.html`, puis la copie PDF disponible en ligne. La copie KMZ ne s'actualise pas : retélécharger et réimporter avant une sortie et contrôler la date. La couche AQX continue de se charger en ligne selon sa configuration.

Les images sont des références relatives `media/ID/...` présentes dans le ZIP du KMZ : elles ne dépendent d'aucun téléchargement au moment de la lecture. Leur affichage effectif après import dans AlpineQuest reste à confirmer en mode avion sur Android. Le texte reste disponible si le lecteur ne restitue pas les images.
Le premier toucher sur une zone reste géré par AlpineQuest : l'ouverture automatique du PDF depuis ce seul toucher n'est pas garantie par KML. Il faut activer le lien dans la fiche/menu de la zone. La taille du panneau natif AlpineQuest reste gérée par l'application ; les styles HTML proposés restent à vérifier sur Android.

Le KMZ Belledonne a été validé par l'utilisateur sur Android : zone sélectionnable, texte consultable et ouverture du PDF officiel. Les nouveaux bandeaux et nouvelles fiches avec images locales doivent être retestés sur cet appareil, notamment en mode avion.

## Production automatique

Le workflow `.github/workflows/update.yml` est installé sur `main`. Il se déclenche sur les changements de code, manuellement, et à 05:25, 11:25, 17:25 et 21:25 UTC (06:25, 12:25, 18:25 et 22:25 en France en hiver).

Il utilise le secret de dépôt `MF_API_KEY`, teste le parseur, télécharge XML et PDF via l'API officielle, crée les KML/KMZ, PNG RGBA, AQX et MBTiles, conserve une archive d'exécution pendant 7 jours et publie via GitHub Pages. Le secret ne doit jamais être placé dans le code, un AQX, un fichier public ou une discussion.

- Exécutions : https://github.com/jfmouret/caf-bera/actions
- Configuration : Settings → Pages → Source → GitHub Actions
- API : `https://public-api.meteofrance.fr/public/DPBRA/v1/massif/BRA?id-massif=8&format=xml` (`format=pdf` pour le PDF).

## Installation locale

Python 3.10+ et fuseau IANA Europe/Paris.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python bera.py --all-alps --mbtiles --base-url https://jfmouret.github.io/caf-bera
python serve.py --directory dist
```

Sans clé, le script utilise les archives publiques du jour et des deux jours précédents. Les dates des XML déterminent l'état ; aucun ancien niveau n'est présenté comme actuel. Les erreurs HTTP, le contrôle du massif et les dates sont consignés dans `bulletins.json`. Les codes et textes d'origine sont conservés. `--demo` produit séparément un exercice historique Belledonne, à ne jamais utiliser comme bulletin actuel.

## Interprétation et limites

La couleur correspond au **maximum du massif**, pas au risque local d'une pente. Les niveaux séparés par altitude ou localisation figurent dans les descriptions et le PDF. Aucun découpage des pentes par altitude n'est inventé. Taillefer n'est pas un massif indépendant dans le GeoJSON officiel joint.

1 vert faible, 2 jaune limité, 3 orange marqué, 4 rouge fort, 5 rouge hachuré noir dans les tuiles ; gris : danger actuel indisponible. Les hachures ne sont pas reproduites dans les polygones KML. Les tuiles sont produites aux niveaux XYZ 6–12 et les MBTiles sont indexés en TMS avec alpha PNG.

Un cache, un KMZ ou un MBTiles peut conserver un ancien bulletin : **contrôler les dates avant utilisation**, notamment hors connexion. Une panne d'exécution peut laisser l'ancienne publication en ligne. `0D` demande l'actualisation à l'affichage, sans garantir un changement instantané sur une vue immobile. GitHub peut retarder une tâche planifiée.

Les dates XML sans fuseau sont interprétées en heure civile française ; les valeurs originales sont conservées. Les libellés SAT 2 et 6 ont été rapprochés des PDF officiels ; les autres restent bruts plutôt qu'être devinés. Les orientations de la rose ne sont pas attribuées arbitrairement à chaque problème.

## Références

- https://www.data.gouv.fr/dataservices/api-bulletin-avalanche
- https://www.data.gouv.fr/datasets/archive-des-bulletins-avalanches
- https://www.alpinequest.net/en/help/v2/maps/on-demand-create
- https://www.alpinequest.net/en/help/v2/placemarks
- https://www.alpinequest.net/en/help/v2/maps/file-based-select

`VALIDATION.md` décrit les vérifications initiales et `RECETTE-ANDROID.md` propose les essais sur appareil. Les fichiers actuels et leur provenance sont accessibles sur la publication.
