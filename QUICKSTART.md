# 🚀 Guide de Démarrage Rapide

Guide étape par étape pour lancer **Transparence Nationale** en 5 minutes.

## Prérequis

Assurez-vous d'avoir installé :
- ✅ **Node.js 18+** ([Télécharger](https://nodejs.org/))
- ✅ **npm** ou **yarn**
- ✅ **Git** ([Télécharger](https://git-scm.com/))

Vérifiez vos versions :
```bash
node --version   # doit être >= 18.0.0
npm --version    # doit être >= 9.0.0
```

## Installation en 3 Étapes

### 1️⃣ Cloner le Projet

```bash
# Via HTTPS
git clone https://github.com/votre-username/transparence-nationale.git

# Ou via SSH
git clone git@github.com:votre-username/transparence-nationale.git

# Entrer dans le dossier
cd transparence-nationale
```

### 2️⃣ Installer les Dépendances

```bash
npm install
# ou
yarn install
```

⏱️ Durée : ~2 minutes

### 3️⃣ Lancer le Serveur

```bash
npm run dev
# ou
yarn dev
```

🎉 **C'est prêt !** Ouvrez http://localhost:3000

## Structure Rapide

```
📁 transparence-nationale/
├── 📁 src/app/          → Pages Next.js
├── 📁 src/components/   → Composants React
├── 📁 src/hooks/        → Custom Hooks
├── 📁 public/data/      → Données JSON
└── 📁 public/photos/    → Photos élus
```

## Commandes Utiles

```bash
# Développement
npm run dev          # Serveur dev (port 3000)

# Production
npm run build        # Build optimisé
npm start            # Serveur production

# Qualité
npm run lint         # Vérifier le code
npx tsc --noEmit     # Vérifier types TS

# Scraping (optionnel)
python3 scripts/scrape-photos.py
```

## Personnalisation Rapide

### Modifier les Données

Éditez `public/data/elus.json` :

```json
{
  "id": "votre-elu",
  "nom": "Nom",
  "prenom": "Prénom",
  "fonction": "Fonction",
  "revenus": 90000,
  "patrimoine": 1200000,
  ...
}
```

### Ajouter des Photos

1. Placez les images dans `public/photos/`
2. Nommez-les comme l'ID : `votre-elu.jpg`
3. Référencez dans le JSON : `"photo": "/photos/votre-elu.jpg"`

### Changer les Couleurs

Éditez `tailwind.config.js` :

```javascript
colors: {
  primary: {
    500: '#votrecouleur',
  }
}
```

## Déploiement Express

### Vercel (1 clic)

1. Push sur GitHub
2. Aller sur [vercel.com](https://vercel.com)
3. Cliquer "Import Project"
4. Sélectionner votre repo
5. Cliquer "Deploy" ✨

Aucune config nécessaire !

### Build Local

```bash
npm run build
npm start
```

Le site sera disponible sur http://localhost:3000

## Dépannage Rapide

### Erreur de Build

```bash
rm -rf .next node_modules
npm install
npm run build
```

### Port 3000 Occupé

```bash
# Changer le port
PORT=3001 npm run dev
```

### Types TypeScript

```bash
# Vérifier les erreurs
npx tsc --noEmit
```

## Prochaines Étapes

1. ✅ Explorer la galerie d'élus
2. ✅ Tester la recherche et les filtres
3. ✅ Consulter un profil détaillé
4. ✅ Personnaliser les données
5. ✅ Déployer sur Vercel

## Besoin d'Aide ?

- 📖 Documentation complète : [README.md](./README.md)
- 🐛 Signaler un bug : [Issues](https://github.com/votre-username/transparence-nationale/issues)
- 💬 Contribuer : [CONTRIBUTING.md](./CONTRIBUTING.md)

---

**Bon développement ! 🚀**
