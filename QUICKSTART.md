# đ Guide de DĂ©marrage Rapide - Transparence Nationale v2.0

## đ„ Installation (5 minutes)

### 1. PrĂ©requis
VĂ©rifiez que vous avez :
```bash
node --version   # >= 18.0.0
npm --version    # >= 9.0.0
```

Si non installĂ© : [TĂ©lĂ©charger Node.js](https://nodejs.org/)

### 2. Installation
```bash
# Extraire l'archive ou cloner le repo
cd transparence-nationale-v2

# Installer les dĂ©pendances
npm install
```

### 3. Lancer le site
```bash
npm run dev
```

đ **C'est prĂȘt !** Ouvrez http://localhost:3000

## âš NouveautĂ©s v2.0

### Interface
- â **Mode nuit** â Bouton dans le header (persiste aprĂšs rechargement)
- â **Chargement progressif** â 20 Ă©lus au dĂ©part, puis bouton "AccĂ©der aux donnĂ©es complĂštes"
- â **Sans photos** â Focus sur les donnĂ©es, site ultra-lĂ©ger
- â **Mobile-first** â OptimisĂ© pour smartphone et desktop

### DonnĂ©es enrichies
- â **Champs HATVP dĂ©taillĂ©s** â Instruments financiers, participations
- â **7 modes de tri** â Nom, patrimoine, revenus, immobilier, placements, instruments, participations
- â **Recherche avancĂ©e** â Par nom, fonction, rĂ©gion, mandats

### Performance
- â **Animations optimisĂ©es** â Framer Motion avec delays progressifs
- â **Bundle lĂ©ger** â Pas de dĂ©pendances inutiles
- â **SEO optimisĂ©** â Metadata, structure sĂ©mantique

## đ Structure des fichiers

```
transparence-nationale-v2/
âââ src/
â   âââ app/
â   â   âââ page.tsx              â Page d'accueil avec explication
â   â   âââ layout.tsx            â Layout avec Header et Footer
â   â   âââ globals.css           â Styles + mode nuit
â   â   âââ profils/[id]/
â   â       âââ page.tsx          â Page profil dĂ©taillĂ©e
â   âââ components/
â   â   âââ Header.tsx            â Header avec bouton mode nuit
â   â   âââ PersonCard.tsx        â Carte Ă©lu (sans photo)
â   â   âââ SearchBar.tsx         â Recherche + tri avancĂ©
â   âââ hooks/
â   â   âââ useElus.ts            â Store Zustand avec Ă©tat global
â   âââ lib/
â       âââ types.ts              â Types TypeScript complets
âââ public/
â   âââ data/
â       âââ elus.json             â Base de donnĂ©es (exemple fourni)
âââ package.json                  â DĂ©pendances
âââ next.config.js                â Config Next.js optimisĂ©e
âââ tailwind.config.js            â Config Tailwind + mode nuit
âââ README.md                     â Documentation complĂšte
```

## đš Personnalisation

### Changer les couleurs
Ăditez `tailwind.config.js` :
```javascript
colors: {
  primary: { 500: '#votre-couleur' },
}
```

### Ajouter des Ă©lus
Ăditez `public/data/elus.json` :
```json
{
  "id": "nouvel-elu",
  "nom": "Nom",
  "prenom": "PrĂ©nom",
  "fonction": "DĂ©putĂ©",
  "revenus": 90000,
  "patrimoine": 1200000,
  "immobilier": 800000,
  "placements": 300000,
  "mandats": ["DĂ©putĂ©"],
  "liens": { "hatvp": "https://..." }
}
```

### Activer les donnĂ©es HATVP complĂštes
ExĂ©cutez le script Python :
```bash
cd scripts
python generate-elus.py --limit 50    # Test sur 50 Ă©lus
python generate-elus.py                 # Tous les Ă©lus
```

## đą DĂ©ploiement sur Vercel

### MĂ©thode 1 : Via GitHub (recommandĂ©)
1. Push sur GitHub
2. Se connecter sur [vercel.com](https://vercel.com)
3. Cliquer "Import Project"
4. SĂ©lectionner votre repo
5. Cliquer "Deploy"

âš **DĂ©ploiement automatique** â Aucune configuration nĂ©cessaire !

### MĂ©thode 2 : CLI Vercel
```bash
npm install -g vercel
vercel login
vercel
```

## đ§ Scripts disponibles

```bash
npm run dev        # Serveur dĂ©veloppement (port 3000)
npm run build      # Build production
npm start          # Serveur production
npm run lint       # VĂ©rification code
```

## đĄ Astuces

### Mode nuit
- Automatique selon prĂ©fĂ©rences systĂšme
- MĂ©morisĂ© dans localStorage
- Bouton dans le header

### Chargement progressif
- Au dĂ©part : 20 Ă©lus + texte d'explication
- Clic sur "AccĂ©der aux donnĂ©es" â Charge tous les Ă©lus
- Recherche et tri fonctionnent sur tous les Ă©lus chargĂ©s

### Optimisation mobile
- Grille responsive : 1 col mobile, 4 cols desktop
- Touch-friendly : zones cliquables larges
- Navigation simplifiĂ©e

## â ïž DĂ©pannage

### Erreur de build
```bash
rm -rf .next node_modules
npm install
npm run build
```

### Port 3000 occupĂ©
```bash
PORT=3001 npm run dev
```

### Types TypeScript
```bash
npx tsc --noEmit     # VĂ©rifier les erreurs
```

## đ Format des donnĂ©es

### Structure minimale
```json
{
  "id": "identifiant-unique",
  "nom": "Nom",
  "prenom": "PrĂ©nom",
  "fonction": "Fonction",
  "revenus": 85000,
  "patrimoine": 1000000,
  "immobilier": 700000,
  "placements": 250000,
  "mandats": [],
  "liens": {}
}
```

### Avec donnĂ©es HATVP
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

## đŻ Objectifs du projet

1. **Transparence** â DonnĂ©es publiques accessibles Ă  tous
2. **Rigueur** â Sources officielles, pas d'interprĂ©tation
3. **Performance** â Site rapide et lĂ©ger
4. **AccessibilitĂ©** â Compatible tous devices

## đ€ Support

- **Documentation** : Voir README.md complet
- **Issues** : GitHub issues
- **Email** : (votre contact)

---

**Transparence Nationale v2.0** â *Investigation âą DonnĂ©es HATVP âą Open Source*
