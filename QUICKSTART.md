# 🚀 Guide de Démarrage Rapide - Transparence Nationale v2.0

## 📥 Installation (5 minutes)

### 1. Prérequis
Vérifiez que vous avez :
```bash
node --version   # >= 18.0.0
npm --version    # >= 9.0.0
```

Si non installé : [Télécharger Node.js](https://nodejs.org/)

### 2. Installation
```bash
# Extraire l'archive ou cloner le repo
cd transparence-nationale-v2

# Installer les dépendances
npm install
```

### 3. Lancer le site
```bash
npm run dev
```

🎉 **C'est prêt !** Ouvrez http://localhost:3000

## ✨ Nouveautés v2.0

### Interface
- ✅ **Mode nuit** — Bouton dans le header (persiste après rechargement)
- ✅ **Chargement progressif** — 20 élus au départ, puis bouton "Accéder aux données complètes"
- ✅ **Sans photos** — Focus sur les données, site ultra-léger
- ✅ **Mobile-first** — Optimisé pour smartphone et desktop

### Données enrichies
- ✅ **Champs HATVP détaillés** — Instruments financiers, participations
- ✅ **7 modes de tri** — Nom, patrimoine, revenus, immobilier, placements, instruments, participations
- ✅ **Recherche avancée** — Par nom, fonction, région, mandats

### Performance
- ✅ **Animations optimisées** — Framer Motion avec delays progressifs
- ✅ **Bundle léger** — Pas de dépendances inutiles
- ✅ **SEO optimisé** — Metadata, structure sémantique

## 📂 Structure des fichiers

```
transparence-nationale-v2/
├── src/
│   ├── app/
│   │   ├── page.tsx              ← Page d'accueil avec explication
│   │   ├── layout.tsx            ← Layout avec Header et Footer
│   │   ├── globals.css           ← Styles + mode nuit
│   │   └── profils/[id]/
│   │       └── page.tsx          ← Page profil détaillée
│   ├── components/
│   │   ├── Header.tsx            ← Header avec bouton mode nuit
│   │   ├── PersonCard.tsx        ← Carte élu (sans photo)
│   │   └── SearchBar.tsx         ← Recherche + tri avancé
│   ├── hooks/
│   │   └── useElus.ts            ← Store Zustand avec état global
│   └── lib/
│       └── types.ts              ← Types TypeScript complets
├── public/
│   └── data/
│       └── elus.json             ← Base de données (exemple fourni)
├── package.json                  ← Dépendances
├── next.config.js                ← Config Next.js optimisée
├── tailwind.config.js            ← Config Tailwind + mode nuit
└── README.md                     ← Documentation complète
```

## 🎨 Personnalisation

### Changer les couleurs
Éditez `tailwind.config.js` :
```javascript
colors: {
  primary: { 500: '#votre-couleur' },
}
```

### Ajouter des élus
Éditez `public/data/elus.json` :
```json
{
  "id": "nouvel-elu",
  "nom": "Nom",
  "prenom": "Prénom",
  "fonction": "Député",
  "revenus": 90000,
  "patrimoine": 1200000,
  "immobilier": 800000,
  "placements": 300000,
  "mandats": ["Député"],
  "liens": { "hatvp": "https://..." }
}
```

### Activer les données HATVP complètes
Exécutez le script Python :
```bash
cd scripts
python generate-elus.py --limit 50    # Test sur 50 élus
python generate-elus.py                 # Tous les élus
```

## 🚢 Déploiement sur Vercel

### Méthode 1 : Via GitHub (recommandé)
1. Push sur GitHub
2. Se connecter sur [vercel.com](https://vercel.com)
3. Cliquer "Import Project"
4. Sélectionner votre repo
5. Cliquer "Deploy"

✨ **Déploiement automatique** — Aucune configuration nécessaire !

### Méthode 2 : CLI Vercel
```bash
npm install -g vercel
vercel login
vercel
```

## 🔧 Scripts disponibles

```bash
npm run dev        # Serveur développement (port 3000)
npm run build      # Build production
npm start          # Serveur production
npm run lint       # Vérification code
```

## 💡 Astuces

### Mode nuit
- Automatique selon préférences système
- Mémorisé dans localStorage
- Bouton dans le header

### Chargement progressif
- Au départ : 20 élus + texte d'explication
- Clic sur "Accéder aux données" → Charge tous les élus
- Recherche et tri fonctionnent sur tous les élus chargés

### Optimisation mobile
- Grille responsive : 1 col mobile, 4 cols desktop
- Touch-friendly : zones cliquables larges
- Navigation simplifiée

## ⚠️ Dépannage

### Erreur de build
```bash
rm -rf .next node_modules
npm install
npm run build
```

### Port 3000 occupé
```bash
PORT=3001 npm run dev
```

### Types TypeScript
```bash
npx tsc --noEmit     # Vérifier les erreurs
```

## 📝 Format des données

### Structure minimale
```json
{
  "id": "identifiant-unique",
  "nom": "Nom",
  "prenom": "Prénom",
  "fonction": "Fonction",
  "revenus": 85000,
  "patrimoine": 1000000,
  "immobilier": 700000,
  "placements": 250000,
  "mandats": [],
  "liens": {}
}
```

### Avec données HATVP
```json
{
  "hatvp_finances": {
    "nb_instruments_financiers": 15,
    "nb_participations_societes": 3,
    "valeur_totale_instruments_euro": 200000,
    "valeur_totale_participations_euro": 50000,
    "types_instruments": {
      "ACTIONS": 10,
      "OBLIGATIONS": 3,
      "ASSURANCE_VIE": 2
    },
    "nb_declarations_hatvp": 2
  }
}
```

## 🎯 Objectifs du projet

1. **Transparence** — Données publiques accessibles à tous
2. **Rigueur** — Sources officielles, pas d'interprétation
3. **Performance** — Site rapide et léger
4. **Accessibilité** — Compatible tous devices

## 🤝 Support

- **Documentation** : Voir README.md complet
- **Issues** : GitHub issues
- **Email** : (votre contact)

---

**Transparence Nationale v2.0** — *Investigation • Données HATVP • Open Source*
