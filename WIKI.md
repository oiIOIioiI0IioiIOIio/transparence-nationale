# Wiki — Transparence Nationale

## Table des matières

1. [Naviguer sur le site](#naviguer-sur-le-site)
   - [Page d'accueil](#page-daccueil)
   - [Liste des élus](#liste-des-élus)
   - [Recherche et filtres](#recherche-et-filtres)
   - [Page profil d'un élu](#page-profil-dun-élu)
   - [Mode nuit et langues](#mode-nuit-et-langues)
2. [Architecture technique](#architecture-technique)
   - [Pipeline de données](#pipeline-de-données)
   - [Structure du code](#structure-du-code)
3. [Adapter le projet pour un autre pays](#adapter-le-projet-pour-un-autre-pays)
   - [Prérequis](#prérequis)
   - [Étape 1 — Identifier les sources de données](#étape-1--identifier-les-sources-de-données)
   - [Étape 2 — Adapter les scripts de collecte](#étape-2--adapter-les-scripts-de-collecte)
   - [Étape 3 — Adapter le format de données](#étape-3--adapter-le-format-de-données)
   - [Étape 4 — Adapter l'interface](#étape-4--adapter-linterface)
   - [Exemples par pays](#exemples-par-pays)

---

## Naviguer sur le site

### Page d'accueil

La page d'accueil (`/`) est le point d'entrée du site. Elle explique :

- **Ce que contient le site** — Les déclarations de patrimoine et d'intérêts des élus français, rendues lisibles et comparables.
- **Comment lire une fiche** — Un exemple visuel montre comment interpréter les badges de patrimoine (rouge), de revenus (jaune), le nombre de déclarations, les mandats et les liens vers les sources officielles.
- **La méthodologie** — Trois étapes : collecte automatisée depuis la HATVP, extraction des données (XML + PDF/OCR), et affichage brut sans interprétation.

Un bouton « Explorer les élus » renvoie vers la liste complète.

### Liste des élus

La page liste (`/liste`) affiche l'ensemble de la base de données.

- **Vue mise en avant** — Par défaut, 12 profils « vedettes » sont affichés. Ce sont les profils les plus complets de la base (données financières détaillées, mandats nationaux).
- **Vue complète** — Un bouton « Voir la base complète » charge l'intégralité des élus.
- **Compteur** — En haut de page, le nombre total d'élus dans la base est affiché en temps réel.
- **Grille responsive** — 1 colonne sur mobile, 2 sur tablette, 3 sur desktop.

Chaque carte d'élu affiche :
- Nom et prénom
- Fonction (ex : « Député des Hauts-de-Seine »)
- Région ou département
- Groupe politique
- **Badge patrimoine** (rouge) — montant total déclaré (ex : « 1.2M EUR »)
- **Badge revenus** (jaune) — revenus annuels déclarés (ex : « 85K EUR »)
- Nombre de déclarations si pas de données financières

Un clic sur une carte ouvre la page profil détaillée de l'élu.

### Recherche et filtres

La barre de recherche en haut de la liste permet de trouver un élu par :

- **Nom** (prénom ou nom de famille)
- **Fonction** (député, sénateur, ministre…)
- **Région** ou département
- **Groupe politique** ou parti
- **Type de mandat**

**Options de tri** (menu déroulant) :
| Tri | Description |
|-----|-------------|
| Par nom | Ordre alphabétique (A → Z) |
| Par patrimoine | Du plus riche au moins riche |
| Par revenus | Revenus annuels décroissants |

**Filtres par mandat** (menu déroulant) :
| Filtre | Cible |
|--------|-------|
| Tous les mandats | Aucun filtre |
| Député·es | Députés de l'Assemblée nationale |
| Sénateur·rices | Sénateurs et sénatrices |
| Président·e | Président de la République |
| Gouvernement | Membres du gouvernement |
| Européen·nes | Députés européens |
| Régional·es | Conseillers régionaux |
| Départemental·es | Conseillers départementaux |
| Communal·es | Élus municipaux |
| Intercommunal·es | Intercommunalités |
| Collectivités | Collectivités territoriales |
| Autres | Mandats non classés |

### Page profil d'un élu

La page profil (`/profils/[id]`) montre le détail complet d'un élu :

#### Informations générales
- Photo (si disponible), nom, fonction, région, groupe politique
- Bouton retour vers la liste

#### Mandats et fonctions
- Liste des mandats actuels
- Historique des mandats passés (section dépliable)

#### Synthèse financière
- **Patrimoine total** : actif brut, dettes, patrimoine net
- **Composition du patrimoine** : graphique camembert (immobilier, placements, autres)
- **Revenus annuels** : tableau année par année avec montants bruts

#### Déclarations HATVP détaillées
Sections dépliables pour chaque catégorie :
- **Biens immobiliers** — Propriétés, SCI, terrains
- **Comptes financiers** — Comptes bancaires, assurance-vie, titres
- **Véhicules et biens mobiliers** — Voitures, bijoux, meubles
- **Dettes** — Emprunts et obligations financières
- **Activités et intérêts** :
  - Activités professionnelles
  - Activités de consultant
  - Activités du conjoint
  - Fonctions bénévoles
  - Participations dans des organes
  - Mandats électifs
  - Collaborateurs

Chaque élément détaillé montre : la dénomination, la période, la fonction, les revenus annuels par année, et le montant total.

#### Sources et vérification
- Lien direct vers la fiche HATVP de l'élu
- Date de dernière mise à jour
- Attribution des données à la HATVP

### Mode nuit et langues

- **Mode nuit** — Bouton soleil/lune dans le header. Le choix est mémorisé dans le navigateur.
- **Langues** — Bouton « EN » / « FR » dans le header. L'intégralité de l'interface est traduite en français et en anglais.

---

## Architecture technique

### Pipeline de données

```
Sources officielles          Scripts Python            Fichiers JSON           Interface Next.js
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  HATVP (XML/PDF) │───▶│  generate-elus.py    │───▶│  elus.json      │───▶│  Page liste      │
│  data.gouv.fr    │    │  parse_pdf.py (OCR)  │    │  elus/{id}.json │    │  Page profil     │
│  Assemblée nat.  │    │  scrape-photos.py    │    │                 │    │  Page accueil    │
│  Sénat           │    │  verify_coherence.py │    │                 │    │                 │
└──────────────────┘    └──────────────────────┘    └─────────────────┘    └─────────────────┘
```

1. **Collecte** — `generate-elus.py` télécharge les données XML depuis la HATVP et les enrichit avec les données CSV de data.gouv.fr.
2. **Extraction PDF** — `parse_pdf.py` traite les déclarations au format PDF avec un parseur texte et un fallback OCR (Tesseract).
3. **Photos** — `scrape-photos.py` récupère les photos depuis les sites de l'Assemblée nationale et du Sénat.
4. **Validation** — `verify_coherence.py` vérifie la cohérence des données (compteurs vs détails, doublons).
5. **Affichage** — Le frontend Next.js charge les JSON statiques et les affiche sans base de données.

### Structure du code

```
src/
├── app/                     # Pages Next.js (App Router)
│   ├── page.tsx             # Accueil
│   ├── layout.tsx           # Layout racine
│   ├── globals.css          # Styles globaux + mode nuit
│   ├── liste/page.tsx       # Liste des élus
│   └── profils/[id]/page.tsx# Profil détaillé
├── components/              # Composants React réutilisables
│   ├── LayoutShell.tsx      # Header + Footer + navigation
│   ├── PersonCard.tsx       # Carte d'un élu
│   ├── PortfolioChart.tsx   # Graphique patrimoine (Recharts)
│   └── SearchBar.tsx        # Barre de recherche + tri + filtres
├── hooks/
│   └── useElus.ts           # Store Zustand (état global)
└── lib/
    ├── types.ts             # Interfaces TypeScript
    ├── theme.ts             # Utilitaires thème jour/nuit
    └── i18n.ts              # Traductions FR/EN

scripts/
├── generate-elus.py         # Extraction HATVP → JSON
├── parse_pdf.py             # Parsing PDF/OCR
├── scrape-photos.py         # Téléchargement photos
├── verify_coherence.py      # Validation données
├── progress.py              # Suivi batch (GitHub Actions)
└── requirements.txt         # Dépendances Python
```

---

## Adapter le projet pour un autre pays

Ce projet est conçu pour la France, mais son architecture est générique. Voici comment l'adapter pour un autre pays disposant de données de transparence publiques.

### Prérequis

Pour que ce projet fonctionne dans un autre pays, il faut :

1. **Des données publiques** — Le pays doit publier les déclarations de patrimoine et/ou d'intérêts de ses élus dans un format exploitable (XML, CSV, JSON, PDF).
2. **Un cadre légal** — La publication et la réutilisation de ces données doivent être autorisées par la loi.
3. **Des sources identifiées** — Sites officiels ou APIs publiques donnant accès aux données.

### Étape 1 — Identifier les sources de données

En France, les données proviennent de :
- **HATVP** (hatvp.fr) — Déclarations de patrimoine et d'intérêts (XML + PDF)
- **data.gouv.fr** — Open data gouvernemental (CSV avec listes d'élus)
- **Assemblée nationale / Sénat** — Photos et mandats

Pour un autre pays, cherchez l'équivalent :

| Donnée | Source en France | Équivalent à trouver |
|--------|-----------------|---------------------|
| Déclarations de patrimoine | HATVP (XML, PDF) | Autorité de transparence locale |
| Liste des élus | data.gouv.fr (CSV) | Parlement, commission électorale |
| Mandats et fonctions | Assemblée nationale | Site du parlement |
| Photos officielles | Assemblée nationale | Site du parlement |

### Étape 2 — Adapter les scripts de collecte

Le cœur du travail est dans `scripts/`. Pour chaque pays :

**a) Remplacer `generate-elus.py`**

Ce script télécharge et parse les données XML de la HATVP. Pour l'adapter :

- Modifier les URLs de téléchargement vers les sources du pays cible
- Adapter le parsing XML/CSV au format local
- Mapper les champs vers la structure JSON interne (voir `src/lib/types.ts`)

Les fonctions clés à adapter :
```python
# Téléchargement des données brutes
def download_source_data():
    # Remplacer par l'API / URL du pays cible
    pass

# Parsing du format source
def parse_declaration(raw_data):
    # Adapter au format XML/CSV/JSON du pays
    pass

# Mapping vers le format interne
def build_elu_entry(parsed):
    return {
        "id": "identifiant-unique",
        "nom": parsed["last_name"],
        "prenom": parsed["first_name"],
        "fonction": parsed["role"],
        "mandats": parsed["mandates"],
        "patrimoine": parsed["total_assets"],
        "revenus": parsed["total_income"],
        # ... etc
    }
```

**b) Adapter `parse_pdf.py` (si nécessaire)**

Si le pays publie des déclarations en PDF :
- Adapter les patterns de détection de sections (numérotation, titres)
- Adapter le nettoyage de texte OCR à la langue locale
- Modifier les regex d'extraction de montants (format monétaire, séparateurs)

Si les données sont uniquement en format structuré (XML, JSON, CSV), ce script n'est pas nécessaire.

**c) Adapter `scrape-photos.py` (optionnel)**

- Modifier les URLs des photos vers le site du parlement local
- Adapter le matching nom → photo

### Étape 3 — Adapter le format de données

Le format JSON interne est défini dans `src/lib/types.ts`. Les champs essentiels :

```typescript
interface Elu {
  id: string;               // Identifiant unique (prénom-nom slugifié)
  nom: string;              // Nom de famille
  prenom: string;           // Prénom
  fonction: string;         // Fonction actuelle
  region?: string;          // Localisation (région, état, province…)
  groupe?: string;          // Groupe politique
  parti?: string;           // Parti politique
  mandats: string[];        // Liste des mandats
  types_mandat: string[];   // Types de mandat (député, sénateur…)
  patrimoine?: number;      // Patrimoine total en euros (ou devise locale)
  revenus?: number;         // Revenus annuels
  immobilier?: number;      // Biens immobiliers
  placements?: number;      // Placements financiers
  photo_url?: string;       // URL de la photo
  liens?: {                 // Liens externes
    hatvp?: string;         // Autorité de transparence
    assemblee?: string;     // Site du parlement
  };
  hatvp?: { ... };          // Données détaillées de la déclaration
}
```

**Adaptations nécessaires** :
- Renommer les champs « hatvp » vers le nom de l'autorité locale
- Adapter les types de mandats (`types_mandat`) aux fonctions électives du pays
- Changer la devise (EUR → USD, GBP, etc.)
- Adapter les catégories de patrimoine aux pratiques locales

### Étape 4 — Adapter l'interface

**a) Traductions**

Le fichier `src/lib/i18n.ts` contient toutes les chaînes de texte en français et en anglais. Pour ajouter une langue :

```typescript
// Ajouter la langue dans le dictionnaire
const translations = {
  fr: { /* ... */ },
  en: { /* ... */ },
  de: { /* allemand */ },
  es: { /* espagnol */ },
  // ...
};
```

Pour changer la langue par défaut, modifier `src/lib/i18n.ts`.

**b) Types de mandats**

Adapter la liste des mandats dans `src/components/SearchBar.tsx` et `src/lib/i18n.ts` :

```typescript
// France
{ value: 'depute', label: 'Député·es' }
{ value: 'senateur', label: 'Sénateur·rices' }

// Exemple Allemagne
{ value: 'bundestagsmitglied', label: 'Bundestagsabgeordnete' }
{ value: 'landtagsmitglied', label: 'Landtagsabgeordnete' }

// Exemple USA
{ value: 'senator', label: 'Senators' }
{ value: 'representative', label: 'Representatives' }
```

**c) Cadre légal et sources**

Adapter les textes de `README.md`, `src/app/page.tsx` (page d'accueil), et les liens vers les sources officielles du pays.

**d) Déploiement**

Le site est un export statique Next.js déployé sur Vercel. Cette architecture fonctionne pour n'importe quel pays :
- Pas de base de données à gérer
- Pas de serveur backend en production
- Données servies en fichiers JSON statiques
- CDN mondial via Vercel (choisir la région la plus proche)

### Exemples par pays

Voici quelques pistes pour adapter ce projet à d'autres pays :

#### Royaume-Uni
- **Source** : [Register of Members' Financial Interests](https://www.parliament.uk/mps-lords-and-offices/standards-and-financial-interests/parliamentary-commissioner-for-standards/registers-of-interests/)
- **Format** : HTML structuré, publication régulière
- **Particularité** : Pas de patrimoine déclaré, mais intérêts financiers (revenus extérieurs, cadeaux, voyages, propriétés)

#### États-Unis
- **Source** : [Office of Government Ethics](https://www.oge.gov/) — Financial Disclosure Reports
- **Format** : PDF (formulaires OGE-278e), certains en XML
- **Particularité** : Déclarations très détaillées mais souvent en PDF scanné. Le parseur OCR de ce projet serait utile.

#### Allemagne
- **Source** : [Bundestag](https://www.bundestag.de/abgeordnete) — Déclarations d'intérêts (Nebentätigkeiten)
- **Format** : HTML structuré sur le site du Bundestag
- **Particularité** : Revenus annexes publiés par tranches (niveaux 1 à 10), pas de patrimoine détaillé

#### Italie
- **Source** : [Camera dei Deputati](https://www.camera.it/) et [Senato](https://www.senato.it/) — Dichiarazioni patrimoniali
- **Format** : PDF et pages web
- **Particularité** : Déclarations patrimoniales et de revenus obligatoires, accessibles en ligne

#### Espagne
- **Source** : [Congreso de los Diputados](https://www.congreso.es/) — Declaraciones de bienes y actividades
- **Format** : PDF
- **Particularité** : Déclarations accessibles mais souvent au format papier numérisé

#### Belgique
- **Source** : [Cour des comptes](https://www.courdescomptes.be/) — Déclarations de mandats et de patrimoine
- **Format** : PDF et HTML
- **Particularité** : Les listes de mandats sont publiques ; les déclarations patrimoniales sont déposées sous pli fermé

#### Canada
- **Source** : [Office of the Conflict of Interest and Ethics Commissioner](https://ciec-ccie.parl.gc.ca/)
- **Format** : HTML structuré
- **Particularité** : Registre public des déclarations, format relativement structuré

---

### Checklist de portage

Pour adapter ce projet à un nouveau pays, suivez cette checklist :

- [ ] Identifier l'autorité de transparence du pays et ses publications
- [ ] Vérifier que les données sont légalement réutilisables (open data, licence)
- [ ] Analyser le format des données (XML, CSV, JSON, PDF, HTML)
- [ ] Écrire un script de collecte adapté (`scripts/generate-elus.py`)
- [ ] Si PDF : adapter le parseur (`scripts/parse_pdf.py`) à la langue et au format
- [ ] Adapter le format JSON interne (`src/lib/types.ts`)
- [ ] Traduire l'interface (`src/lib/i18n.ts`)
- [ ] Adapter les types de mandats (`SearchBar.tsx`, `i18n.ts`)
- [ ] Mettre à jour les textes légaux et les sources (`README.md`, `page.tsx`)
- [ ] Adapter la devise et le formatage des montants
- [ ] Déployer sur Vercel (ou autre hébergeur statique)
- [ ] Documenter les sources et la méthodologie dans le README

---

*Ce wiki est maintenu dans le dépôt. Pour toute question, ouvrez une [issue](https://github.com/oiIOIioiI0IioiIOIio/transparence-nationale/issues).*
