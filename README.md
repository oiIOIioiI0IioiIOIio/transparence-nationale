# Transparence Nationale

**Version 2.0** — Plateforme d'investigation citoyenne sur le patrimoine des élus français

![Next.js](https://img.shields.io/badge/Next.js-14-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8)

Cette plateforme présente de manière rigoureuse et accessible les déclarations de patrimoine et de situation financière des élus français, en s'appuyant exclusivement sur les données officielles de la **HATVP** (Haute Autorité pour la Transparence de la Vie Publique).


## Fonctionnalités v2.0

### Interface
-  **Mode nuit** : basculement clair/sombre avec mémorisation
-  **Chargement progressif** : 20 élus en preview, puis chargement complet sur demande
-  **Design épuré** : pas de photos, focus sur les données
-  **Mobile-first** : optimisé pour tous les écrans
-  **Performance** : site ultra-léger et rapide

### Données
-  **Patrimoine détaillé** : total, immobilier, placements
-  **Revenus annuels** : indemnités et revenus d'activité
-  **Instruments financiers** : actions, obligations, assurance-vie (HATVP)
-  **Participations** : sociétés, SARL, SCI (HATVP)
-  **Mandats** : fonctions actuelles et historique

### Recherche et tri
-  **Recherche avancée** : nom, fonction, région, mandats
-  **7 modes de tri** :
  - Nom (A-Z)
  - Patrimoine (décroissant)
  - Revenus (décroissant)
  - Immobilier (décroissant)
  - Placements (décroissant)
  - Instruments financiers (décroissant)
  - Participations (décroissant)


##  Structure du projet

```
transparence-nationale/
├── src/
│   ├── app/
│   │   ├── page.tsx              # Page d'accueil
│   │   ├── layout.tsx            # Layout principal
│   │   ├── globals.css           # Styles globaux + mode nuit
│   │   └── profils/[id]/
│   │       └── page.tsx          # Page de profil détaillée
│   ├── components/
│   │   ├── Header.tsx            # En-tête avec mode nuit
│   │   ├── PersonCard.tsx        # Carte élu (sans photo)
│   │   └── SearchBar.tsx         # Recherche et tri avancés
│   ├── hooks/
│   │   └── useElus.ts            # Store Zustand
│   └── lib/
│       └── types.ts              # Types TypeScript
├── public/
│   └── data/
│       └── elus.json             # Base de données élus
├── scripts/
│   └── generate-elus.py          # Script de récupération HATVP
├── package.json
├── next.config.js
├── tailwind.config.js
└── tsconfig.json
```

##  Format des données (elus.json)

```json
{
  "id": "jean-dupont",
  "nom": "Dupont",
  "prenom": "Jean",
  "fonction": "Député",
  "region": "Île-de-France",
  "revenus": 85000,
  "patrimoine": 1200000,
  "immobilier": 800000,
  "placements": 300000,
  "mandats": ["Député", "Conseiller municipal"],
  "liens": {
    "assemblee": "https://...",
    "hatvp": "https://...",
    "wikipedia": "https://..."
  },
  "hatvp_finances": {
    "nb_instruments_financiers": 15,
    "nb_participations_societes": 3,
    "valeur_totale_instruments_euro": 250000,
    "valeur_totale_participations_euro": 100000,
    "types_instruments": {
      "ACTIONS": 10,
      "OBLIGATIONS": 3,
      "ASSURANCE_VIE": 2
    },
    "nb_declarations_hatvp": 2,
    "hatvp_scraped_at": "2024-01-15T10:30:00Z"
  }
}
```

## 📝 Licence

**MIT** — Projet open source à but non lucratif.

##  Mentions légales

Les données affichées proviennent de déclarations publiques officielles déposées auprès de la HATVP. 
Ce projet vise la transparence et l'information citoyenne. Il n'a aucun objectif commercial ou partisan.

**Sources officielles** :
- [HATVP](https://www.hatvp.fr) — Haute Autorité pour la Transparence de la Vie Publique
- [Assemblée Nationale](https://www.assemblee-nationale.fr) — Données parlementaires
- [data.gouv.fr](https://www.data.gouv.fr) — Open data gouvernemental

##  Contribution

Les contributions sont bienvenues ! Pour contribuer :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/amelioration`)
3. Commit (`git commit -m 'Ajout fonctionnalité'`)
4. Push (`git push origin feature/amelioration`)
5. Ouvrir une Pull Request

##  Contact

Pour toute question ou suggestion, ouvrir une [issue](https://github.com/votre-username/transparence-nationale/issues).

---
