export interface Elu {
  id: string;
  nom: string;
  prenom: string;
  fonction: string;
  region?: string;
  revenus: number;              // €
  patrimoine: number;           // €
  immobilier: number;           // € (détail patrimoine)
  placements: number;           // € (détail patrimoine)
  mandats: string[];            // ["Député", "Conseiller..."]
  photo: string;                // "/photos/jean-dupont.jpg"
  liens: {
    assemblee?: string;
    hatvp?: string;
    wikipedia?: string;
  };
}

export type SortBy = "nom" | "patrimoine" | "revenus";

export interface ElusStore {
  elus: Elu[];
  loading: boolean;
  searchTerm: string;
  sortBy: SortBy;
  
  setSearchTerm: (term: string) => void;
  setSortBy: (sort: SortBy) => void;
  getFiltered: () => Elu[];
}
