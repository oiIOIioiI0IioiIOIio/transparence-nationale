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
    // Compteurs par section HATVP
    nb_biens_immobiliers?: number;
    nb_comptes_bancaires?: number;
    nb_vehicules?: number;
    nb_dettes?: number;
    nb_revenus?: number;
    nb_activites_professionnelles?: number;
    nb_mandats_electifs?: number;
    nb_participations_organes?: number;
    nb_fonctions_benevoles?: number;
    // Valeurs par section
    valeur_biens_immobiliers_euro?: number;
    valeur_comptes_bancaires_euro?: number;
    valeur_instruments_financiers_euro?: number;
    valeur_participations_financieres_euro?: number;
    valeur_valeurs_bourse_euro?: number;
    valeur_valeurs_non_bourse_euro?: number;
    valeur_assurances_vie_euro?: number;
    valeur_fonds_euro?: number;
    valeur_dettes_euro?: number;
    valeur_revenus_euro?: number;
    // Detailed extracted data (company names, salaries, etc.)
    details_activites?: { denomination?: string; remuneration?: string; fonction?: string }[];
    details_mandats?: { mandat?: string; organisme?: string; remuneration?: string }[];
    details_participations?: { denomination?: string; type?: string; valeur?: string }[];
    details_revenus?: { type?: string; organisme?: string; montant?: string }[];
    [key: string]: unknown;
  };
  groupe?: string;
  parti?: string;
}

export type SortBy = "nom" | "patrimoine" | "revenus";

export type MandatFilter = "" | "depute" | "senateur" | "president" | "gouvernement" | "europe" | "region" | "departement" | "commune" | "epci" | "ctsp" | "autre";

export interface ElusStore {
  elus: Elu[];
  loading: boolean;
  searchTerm: string;
  sortBy: SortBy;
  mandatFilter: MandatFilter;
  showPhotos: boolean;
  
  setSearchTerm: (term: string) => void;
  setSortBy: (sort: SortBy) => void;
  setMandatFilter: (filter: MandatFilter) => void;
  setShowPhotos: (show: boolean) => void;
  getFiltered: () => Elu[];
}
