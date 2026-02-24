import { create } from 'zustand';
import { Elu, ElusStore } from '@/lib/types';

export const useElus = create<ElusStore>((set, get) => ({
  elus: [],
  loading: true,
  searchTerm: '',
  sortBy: 'nom',

  setSearchTerm: (term: string) => set({ searchTerm: term }),
  
  setSortBy: (sort) => set({ sortBy: sort }),

  getFiltered: () => {
    const { elus, searchTerm, sortBy } = get();
    
    // Filtrage
    let filtered = elus;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = elus.filter(
        (elu) =>
          elu.nom.toLowerCase().includes(term) ||
          elu.prenom.toLowerCase().includes(term) ||
          elu.fonction.toLowerCase().includes(term) ||
          (elu.region && elu.region.toLowerCase().includes(term))
      );
    }

    // Tri
    const sorted = [...filtered].sort((a, b) => {
      switch (sortBy) {
        case 'patrimoine':
          return b.patrimoine - a.patrimoine;
        case 'revenus':
          return b.revenus - a.revenus;
        case 'nom':
        default:
          return `${a.nom} ${a.prenom}`.localeCompare(`${b.nom} ${b.prenom}`);
      }
    });

    return sorted;
  },
}));

// Fonction pour charger les données
export const loadElus = async () => {
  try {
    const response = await fetch('/data/elus.json');
    if (!response.ok) throw new Error('Erreur lors du chargement des données');
    const data: Elu[] = await response.json();
    useElus.setState({ elus: data, loading: false });
  } catch (error) {
    console.error('Erreur:', error);
    useElus.setState({ loading: false });
  }
};
