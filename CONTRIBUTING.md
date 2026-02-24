# Guide de Contribution

Merci de votre intérêt pour contribuer à Transparence Nationale ! 🎉

## Comment Contribuer

### Signaler un Bug 🐛

1. Vérifiez que le bug n'a pas déjà été signalé
2. Ouvrez une [issue](https://github.com/votre-username/transparence-nationale/issues) avec :
   - Description claire du problème
   - Steps pour reproduire
   - Comportement attendu vs réel
   - Screenshots si applicable
   - Environnement (OS, navigateur, version)

### Proposer une Fonctionnalité ✨

1. Ouvrez une issue pour discuter de la fonctionnalité
2. Attendez l'approbation avant de commencer le développement
3. Suivez les guidelines de code ci-dessous

### Soumettre une Pull Request 🚀

1. **Fork** le projet
2. **Clone** votre fork
```bash
git clone https://github.com/votre-username/transparence-nationale.git
cd transparence-nationale
```

3. **Créez une branche**
```bash
git checkout -b feature/ma-super-feature
# ou
git checkout -b fix/correction-bug
```

4. **Installez les dépendances**
```bash
npm install
```

5. **Développez** votre fonctionnalité
   - Suivez les conventions de code
   - Testez votre code
   - Assurez-vous que `npm run build` fonctionne

6. **Commit** vos changements
```bash
git add .
git commit -m "feat: ajout de ma super feature"
```

Conventions de commit :
- `feat:` nouvelle fonctionnalité
- `fix:` correction de bug
- `docs:` documentation
- `style:` formatage, point-virgule manquant, etc.
- `refactor:` refactorisation du code
- `test:` ajout de tests
- `chore:` mise à jour des dépendances, config, etc.

7. **Push** vers votre fork
```bash
git push origin feature/ma-super-feature
```

8. **Ouvrez une Pull Request**
   - Description claire des changements
   - Référencez les issues liées
   - Ajoutez des screenshots si UI

## Standards de Code

### TypeScript
- Utilisez TypeScript strict
- Définissez les types explicitement
- Évitez `any`

### React/Next.js
- Utilisez les React Hooks
- Préférez les composants fonctionnels
- Utilisez 'use client' seulement si nécessaire
- Suivez les conventions Next.js App Router

### Styling
- Utilisez Tailwind CSS
- Classes utilitaires > CSS custom
- Mobile-first responsive design

### Nommage
- Composants : `PascalCase`
- Fonctions/variables : `camelCase`
- Constantes : `UPPER_SNAKE_CASE`
- Fichiers : `kebab-case` ou `PascalCase` pour composants

### Structure
```typescript
// Imports
import React from 'react';

// Types
interface MyComponentProps {
  title: string;
}

// Component
export default function MyComponent({ title }: MyComponentProps) {
  // Logic
  
  return (
    // JSX
  );
}
```

## Tests

Avant de soumettre :
```bash
npm run build    # Build réussi
npm run lint     # Pas d'erreurs ESLint
```

## Questions ?

N'hésitez pas à :
- Ouvrir une issue de discussion
- Demander de l'aide dans les PR
- Contacter les mainteneurs

## Code de Conduite

- Soyez respectueux et inclusif
- Acceptez les critiques constructives
- Focalisez sur le meilleur pour le projet
- Pas de spam, trolling, ou contenu offensant

## Licence

En contribuant, vous acceptez que vos contributions soient sous licence MIT.

---

Merci pour votre contribution ! 🙏
