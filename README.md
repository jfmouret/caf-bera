# CAF — BERA et Nivôse dans AlpineQuest

Site : https://jfmouret.github.io/caf-bera/

Source : Météo-France — Licence Ouverte 2.0. Transformation indépendante pour les formations CAF. Aucun fond IGN n'est redistribué. Les couleurs BERA représentent le maximum du massif, pas le risque local d'une pente.

## Usage courant en ligne

- Importer `bera.aqx` : afficher uniquement **BERA V4** au-dessus de son fond IGN.
- Importer `bera-contours.kmz` : limites cliquables avec liens permanents vers les informations BERA actualisées.
- Importer `nivose-alpes.kmz` : 20 stations cliquables avec liens permanents vers les courbes en ligne. `nivose-belledonne.kmz` est une alternative limitée à l'Aigleton, déjà inclus dans le fichier Alpes.
- Les repères sont désormais légers : ils ouvrent les données en ligne. Les anciens imports hors ligne déjà enregistrés sur le téléphone restent des instantanés datés.

Les Nivôse gardent trois jours de mesures horaires. Les courbes sont actualisées en ligne aux six passages de 06 h 30, 10 h 30, 14 h 30, 16 h 30, 18 h 30 et 20 h 30, heure de Paris, avec gestion été/hiver. Les BERA sont interrogés aux trois passages du soir ; les autres passages préservent la dernière publication BERA. GitHub peut retarder une tâche.

Le dernier BERA reçu conserve sa couleur jusqu'au remplacement, même après son échéance initiale, avec dates réelles inchangées et dépassement signalé. Une mesure Nivôse est ponctuelle au site de la station. La hauteur totale du manteau n'est pas un cumul de neige fraîche.

Si d'anciens libellés BERA restent déplacés dans AlpineQuest, masquer les anciennes couches et relancer l'application : les tuiles V4 ont des URL et un cache distincts. Le KMZ Belledonne initial a été validé par l'utilisateur sur Android ; les images intégrées aux nouvelles fiches hors ligne restent à tester sur cet appareil.

## Paquet hors ligne sur demande

Ouvrir **Actions → BERA quotidien → Run workflow**, choisir `main`, cocher **Générer et publier le paquet hors ligne**, puis lancer.

La page `hors-ligne.html` donne le lien vers le dernier ZIP publié en release GitHub publique. Le téléchargement n'exige aucun compte GitHub. Avant la première génération manuelle, la page indique qu'aucun paquet n'est disponible.

Le ZIP contient `bera-contours.kmz` (bulletins et illustrations officielles hors ligne), `nivose-alpes.kmz` (graphiques hors ligne), `bera.mbtile` (couche raster BERA transparente) et un mode d'emploi. Les Nivôse du paquet sont limitées à trois jours et un point par tranche de quatre heures. Décompresser, importer les deux KMZ comme repères et ouvrir le MBTile comme carte/couche au-dessus d'IGN. Pour renouveler la copie hors ligne, télécharger un nouveau paquet et remplacer les anciens imports.

Le paquet est produit uniquement lorsque la case est cochée, puis conservé comme un seul asset de release remplacé à la prochaine demande. Il n'est pas dupliqué dans chaque archive de génération en ligne.

## Exploitation et stockage

Les secrets GitHub `MF_API_KEY` (BERA) et `MF_OBS_API_KEY` (Observation) restent dans GitHub Actions, jamais dans les fichiers publiés. La souscription Observation v2 est nécessaire pour les Nivôse.

Les deux dernières archives techniques légères `bera-en-ligne` et la dernière archive Pages sont conservées après publication. Les anciennes archives complètes `bera-fichiers` sont supprimées après la première publication légère réussie. Les autres noms d'artefacts ne sont pas touchés. L'historique de trois jours est contenu dans les copies légères. Le nettoyage est testé et conserve une sauvegarde avant le transfert, puis exige les nouvelles archives après publication. Aucun budget de facturation du compte n'est modifié.

Le trafic des visiteurs est indépendant du nombre de générations. Un objectif de 1,5 Go/jour correspond à environ 45 Go sur 30 jours ; ce projet ne peut pas imposer ce plafond quotidien sur GitHub Pages. Le stockage des artefacts est un quota distinct, partagé par le compte.

Voir `NIVOSE.md` pour les détails, `data/licence-donnees.md` pour les sources et `RECETTE-ANDROID.md` pour les essais sur appareil.

## Validation locale

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python bera.py --all-alps --online-only --base-url https://jfmouret.github.io/caf-bera
python nivose.py --online-only --output dist --base-url https://jfmouret.github.io/caf-bera
```

Les données de test artificielles et archives historiques de test ne sont jamais publiées comme observations actuelles. Taillefer n'est pas un massif BERA indépendant dans le GeoJSON officiel utilisé.
