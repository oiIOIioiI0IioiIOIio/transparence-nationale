# Changelog - Transparence Nationale

## Version 2.0.0 - Refonte complète (Février 2025)

### 🎨 Interface
- ✅ **Suppression des photos** — Focus sur les données, pas l'apparence
- ✅ **Mode nuit complet** — Dark mode avec persistance localStorage
- ✅ **Chargement progressif** — 20 élus en preview, puis chargement complet sur clic
- ✅ **Design épuré** — Interface minimaliste et professionnelle
- ✅ **Mobile-first** — Optimisation smartphone prioritaire
- ✅ **Animations subtiles** — Framer Motion avec delays progressifs

### 📊 Données
- ✅ **Champs HATVP enrichis** — Support complet des données HATVP
  - Instruments financiers (actions, obligations, assurance-vie...)
  - Participations dans des sociétés
  - Types d'instruments détaillés
  - Valeurs totales
- ✅ **Page d'explication** — Contexte journalistique au premier chargement
- ✅ **Détails patrimoine** — Composition visuelle (immobilier, placements, autres)

### 🔍 Recherche et tri
- ✅ **7 modes de tri** (vs 3 avant) :
  - Nom (A-Z)
  - Patrimoine (décroissant)
  - Revenus (décroissant)
  - Immobilier (décroissant) 🆕
  - Placements (décroissant) 🆕
  - Instruments financiers (décroissant) 🆕
  - Participations (décroissant) 🆕
- ✅ **Recherche étendue** — Nom, fonction, région, mandats
- ✅ **Interface tri améliorée** — Panel déroulant avec boutons clairs

### ⚡ Performance
- ✅ **Bundle optimisé** — Suppression des imports inutiles
- ✅ **Images supprimées** — Site ultra-léger
- ✅ **Lazy loading** — Chargement progressif des données
- ✅ **Cache localStorage** — Mode nuit mémorisé
- ✅ **CSS optimisé** — Transitions ciblées uniquement

### 🏗️ Architecture
- ✅ **TypeScript strict** — Types complets pour toutes les données
- ✅ **Zustand amélioré** — State management avec preview/full mode
- ✅ **Components refactorisés** — Code plus maintenable
- ✅ **Config optimisée** — Next.js, Tailwind, TypeScript

### 📱 Mobile
- ✅ **Touch-friendly** — Zones tactiles larges
- ✅ **Navigation simplifiée** — Menu burger si nécessaire
- ✅ **Grille responsive** — 1-2-3-4 colonnes selon écran
- ✅ **Performance mobile** — Temps de chargement < 2s

## Version 1.0.0 - Version initiale (2024)

### Fonctionnalités
- ✅ Galerie d'élus avec photos
- ✅ Recherche par nom, fonction, région
- ✅ Tri par nom, patrimoine, revenus
- ✅ Pages de profil détaillées
- ✅ Graphiques patrimoine (PortfolioChart)
- ✅ Liens HATVP, Assemblée, Wikipedia
- ✅ Design classique avec Tailwind CSS
- ✅ Animation Framer Motion

### Limitations v1
- ❌ Pas de mode nuit
- ❌ Photos lourdes (impact performance)
- ❌ Chargement complet au démarrage
- ❌ Tri limité à 3 critères
- ❌ Pas de données HATVP détaillées
- ❌ Interface générique

---

## Migration v1 → v2

### Fichiers modifiés
- `src/lib/types.ts` — Types étendus avec HatvpFinances
- `src/hooks/useElus.ts` — Ajout darkMode, showAll, preview
- `src/components/PersonCard.tsx` — Suppression photo, ajout données HATVP
- `src/components/SearchBar.tsx` — Tri avancé avec 7 options
- `src/app/page.tsx` — Texte explicatif + chargement progressif
- `src/app/layout.tsx` — Header avec mode nuit
- `src/app/globals.css` — Support dark mode complet

### Fichiers ajoutés
- `src/components/Header.tsx` — Header standalone avec toggle dark
- `QUICKSTART.md` — Guide de démarrage
- `CHANGELOG.md` — Ce fichier

### Fichiers supprimés
- Photos individuelles dans `public/photos/` — Remplacées par des placeholders

### Données
Le format JSON reste compatible. Les nouveaux champs sont optionnels :
```json
{
  "hatvp_finances": {
    "nb_instruments_financiers": 15,
    "nb_participations_societes": 3,
    ...
  }
}
```

---

## Roadmap v2.1 (à venir)

### Fonctionnalités prévues
- [ ] Export CSV/PDF des données
- [ ] Comparateur entre 2 élus
- [ ] Statistiques globales (moyennes, médianes)
- [ ] Graphiques avancés (évolution temporelle)
- [ ] Filtres par fourchettes de valeurs
- [ ] Recherche par ville/département
- [ ] API REST publique
- [ ] Mode impression optimisé

### Optimisations
- [ ] PWA (Progressive Web App)
- [ ] Service Worker pour cache offline
- [ ] Compression Brotli
- [ ] CDN pour assets statiques
- [ ] Lazy loading images (si réintroduites)

---

**Transparence Nationale** — Open Source • Investigation • Données Publiques
