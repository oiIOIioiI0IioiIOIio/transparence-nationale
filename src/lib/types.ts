export interface Declaration {
  type: string;
  date_publication: string;
  date_depot: string;
  qualite: string;
  type_mandat: string;
}

export interface Elu {
  id: string;
  nom: string;
  prenom: string;
  fonction: string;
  region?: string;
  revenus: number;              // €
  patrimoine: number;           // €
  immobilier: number;           // € (détail patrimoine)
  placements: number[] | number; // Legacy: was stored as array, now as number. Use placements_montant for new data.
  placements_montant?: number;  // €
  mandats: string[];            // ["Député du Rhône", ...]
  types_mandat?: string[];      // ["depute", "senateur", ...]
  photo: string;                // "/photos/jean-dupont.jpg"
  photo_url?: string;           // URL externe (assemblée, sénat)
  declarations_csv?: Declaration[];
  liens: {
    assemblee?: string;
    hatvp?: string;
    senat?: string;
    wikipedia?: string;
  };
  hatvp?: {
    nb_declarations_hatvp?: number;
    hatvp_scraped_at?: string;
    total_revenus_euro?: number;
    patrimoine_net_euro?: number;
    total_actif_brut_euro?: number;
    total_dettes_euro?: number;
    [key: string]: unknown;
  };
  groupe?: string;
  parti?: string;
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
