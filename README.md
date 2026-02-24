# Transparence Nationale

Une galerie interactive qui présente, de manière claire et accessible, le patrimoine et les revenus des élu·e·s français·es à partir des données publiques de la HATVP (Haute Autorité pour la Transparence de la Vie Publique).

![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.3-38bdf8)
![License](https://img.shields.io/badge/License-MIT-green)

## Ce que vous trouverez ici

- Une recherche simple pour retrouver un·e élu·e par nom, fonction ou région.
- Visualisations qui expliquent la composition du patrimoine (logements, placements, autres).
- Une interface responsive pensée pour être lisible sur ordinateur et mobile.
- Pages de profil détaillées pour chaque élu·e avec chiffres et graphiques.

## Prérequis et démarrage

Prérequis :
- Node.js (version récente)
- npm ou yarn
- Python (pour le script de récupération des photos, si vous l'utilisez)

Pour lancer le projet en local :

```bash
# cloner le dépôt
git clone https://github.com/votre-username/transparence-nationale.git
cd transparence-nationale

# installer les dépendances
npm install

# lancer le serveur de développement
npm run dev
```

Ensuite, ouvrez http://localhost:3000 dans votre navigateur.

## Structure du projet (vue d'ensemble)

- src/app : pages et layout principaux
- src/components : composants réutilisables (cartes, graphiques, barre de recherche)
- src/hooks : gestion d'état
- src/lib : types et petites utilitaires
- public/data : données statiques (liste des élu·e·s)
- public/photos : photos des élu·e·s (générées par le script)
- scripts : scripts utiles (ex. récupération de photos)

## Données et provenance

Les informations affichées proviennent de sources publiques officielles :
- HATVP (données déclaratives)
- API de l'Assemblée nationale pour les photos et métadonnées
- Wikipedia comme source de secours pour certaines images

Le projet utilise des fichiers de données statiques pour l'affichage, et un script Python permet de télécharger les photos depuis les API indiquées.

Pour récupérer les photos :

```bash
cd scripts
python3 scrape-photos.py
```

Le script place les images dans public/photos.

## Composants principaux (résumé)

- PersonCard : carte d'un·e élu·e avec photo, nom, fonction et indicateurs clés.
- PortfolioChart : graphique montrant la répartition du patrimoine.
- SearchBar : recherche et tri en temps réel.

## Déploiement

Le projet se déploie facilement sur une plateforme d'hébergement comme Vercel. En local :

```bash
# build
npm run build

# démarrer en production
npm start
```

Aucune variable d'environnement n'est nécessaire pour la version qui utilise uniquement des données statiques.

## Scripts disponibles

- npm run dev — serveur de développement
- npm run build — build de production
- npm start — serveur production
- npm run lint — v��rification de code
- npm run scrape — lancer le script de récupération des photos

## Contribution

Les contributions sont bienvenues. Si vous souhaitez aider :

1. Forkez le projet.
2. Créez une branche pour votre fonctionnalité.
3. Faites vos changements et commitez.
4. Poussez votre branche et ouvrez une pull request.

Merci d'expliquer brièvement le but de vos changements et, si nécessaire, de fournir des exemples ou captures d'écran.

## Licence

Ce projet est publié sous licence MIT. Voir le fichier LICENSE pour les détails.

## Prochaines étapes envisagées

Parmi les améliorations possibles :
- Historique des mandats
- Comparateur entre deux élu·e·s
- Mode sombre
- Export PDF/CSV
- Statistiques globales et graphiques d'évolution

## Remarques légales et confidentialité

Les informations présentées proviennent de déclarations publiques déposées auprès d'organismes officiels. Ce projet vise la transparence et l'information ; il n'a pas d'objectif commercial. Seules des données publiques et légalement accessibles sont utilisées.

Si vous avez des questions ou des suggestions, ouvrez une issue sur le dépôt.
