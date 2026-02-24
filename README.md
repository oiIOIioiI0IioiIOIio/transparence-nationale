# 🇫🇷 Transparence Nationale

Une galerie interactive explorant le patrimoine et les revenus des élus français via les données officielles de la HATVP (Haute Autorité pour la Transparence de la Vie Publique).

![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.3-38bdf8)
![License](https://img.shields.io/badge/License-MIT-green)

## ✨ Fonctionnalités

- 🔍 **Recherche en temps réel** - Filtrez par nom, fonction ou région
- 📊 **Visualisations interactives** - Graphiques Recharts pour la composition du patrimoine
- 🎨 **Design moderne** - Interface responsive avec animations Framer Motion
- ⚡ **Performance optimale** - Next.js 14 App Router avec optimisations d'images
- 📱 **Mobile-first** - Expérience fluide sur tous les appareils

## 🚀 Démarrage Rapide

### Prérequis

- Node.js 18+ 
- npm ou yarn
- Python 3.8+ (pour le scraping)

### Installation

```bash
# Cloner le repo
git clone https://github.com/votre-username/transparence-nationale.git
cd transparence-nationale

# Installer les dépendances
npm install

# Lancer le serveur de développement
npm run dev
```

Ouvrez [http://localhost:3000](http://localhost:3000) dans votre navigateur.

## 📁 Structure du Projet

```
transparence-nationale/
├── src/
│   ├── app/
│   │   ├── layout.tsx           # Layout principal
│   │   ├── page.tsx             # Page galerie
│   │   ├── globals.css          # Styles globaux
│   │   └── profils/[id]/
│   │       └── page.tsx         # Page profil détaillé
│   ├── components/
│   │   ├── PersonCard.tsx       # Carte d'élu
│   │   ├── PortfolioChart.tsx   # Graphique patrimoine
│   │   └── SearchBar.tsx        # Barre de recherche + tri
│   ├── hooks/
│   │   └── useElus.ts           # Hook Zustand
│   └── lib/
│       └── types.ts             # Types TypeScript
├── public/
│   ├── data/
│   │   └── elus.json            # Données élus
│   └── photos/                   # Photos élus
├── scripts/
│   └── scrape-photos.py         # Script de scraping
└── package.json
```

## 🔧 Technologies

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Langage**: TypeScript 5
- **Styling**: Tailwind CSS 3.3
- **Animations**: Framer Motion
- **Graphiques**: Recharts
- **État**: Zustand

### Data
- **Parsing**: PapaParse
- **Source**: HATVP OpenData
- **Photos**: API Assemblée Nationale + Wikipedia

## 📊 Données

Les données proviennent de sources officielles :

1. **HATVP** : [https://www.hatvp.fr/livraison/opendata/liste.csv](https://www.hatvp.fr/livraison/opendata/liste.csv)
2. **API Assemblée Nationale** : [https://data.assemblee-nationale.fr/api](https://data.assemblee-nationale.fr/api)
3. **Wikipedia** (fallback photos)

### Scraping des Photos

```bash
# Exécuter le script Python
cd scripts
python3 scrape-photos.py
```

Le script :
- Télécharge les photos depuis l'API Assemblée
- Génère `/public/photos/*.jpg`
- Crée une image placeholder

## 🎨 Composants Principaux

### PersonCard
Carte interactive avec hover animation affichant :
- Photo de l'élu
- Nom et fonction
- Badges patrimoine/revenus
- Lien vers profil détaillé

### PortfolioChart
Graphique circulaire (Recharts) montrant :
- Répartition Immobilier/Placements/Autres
- Pourcentages et montants
- Légende détaillée

### SearchBar
Barre de recherche avec :
- Filtre temps réel
- Tri par nom/patrimoine/revenus
- Interface responsive

## 🌐 Déploiement

### Vercel (recommandé)

1. Push sur GitHub
2. Connectez votre repo à Vercel
3. Déploiement automatique !

```bash
# Build local
npm run build

# Start production
npm start
```

### Variables d'Environnement

Aucune variable requise ! 🎉  
Le projet utilise uniquement des données statiques.

## 📝 Scripts Disponibles

```bash
npm run dev      # Serveur développement
npm run build    # Build production
npm start        # Serveur production
npm run lint     # Linter ESLint
npm run scrape   # Lancer le scraping Python
```

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créez une branche (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🎯 Roadmap

- [ ] Timeline historique des mandats
- [ ] Comparateur de patrimoine (2 élus)
- [ ] Dark mode
- [ ] Export PDF/CSV
- [ ] Statistiques globales
- [ ] Graphiques d'évolution temporelle
- [ ] API publique

## 🙏 Remerciements

- **HATVP** pour les données publiques
- **Assemblée Nationale** pour l'API
- **Next.js** et **Vercel** pour l'infrastructure
- La communauté open-source

## 📞 Contact

Pour toute question ou suggestion :
- Ouvrez une [issue](https://github.com/votre-username/transparence-nationale/issues)
- Twitter: [@votre-handle](https://twitter.com/votre-handle)

---

**⚖️ Note légale** : Ce projet utilise des données publiques à des fins de transparence démocratique. Les informations affichées proviennent de déclarations officielles déposées auprès de la HATVP.

**🔐 Vie privée** : Seules les données publiques légalement accessibles sont utilisées.
