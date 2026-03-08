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
  revenus?: number;              // €
  patrimoine?: number;           // €
  immobilier?: number;           // € (détail patrimoine)
  placements?: number[] | number; // Legacy: was stored as array, now as number. Use placements_montant for new data.
  placements_montant?: number;  // €
  mandats?: string[];            // ["Député du Rhône", ...]
  types_mandat?: string[];      // ["depute", "senateur", ...]
  photo?: string;                // "/photos/jean-dupont.jpg"
  photo_url?: string;           // URL externe (assemblée, sénat)
  declarations_csv?: Declaration[];
  nb_declarations_csv?: number;   // Count of declarations (used in slim elus.json)
  liens?: {
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
    details_activites?: { denomination?: string; remuneration?: number; fonction?: string; periode?: string; montant_euro?: number; revenus_annuels?: { annee?: string; montant?: number }[] }[];
    details_mandats?: { mandat?: string; organisme?: string; remuneration?: number; periode?: string; statut?: string; montant_euro?: number; revenus_annuels?: { annee?: string; montant?: number }[] }[];
    details_participations?: { denomination?: string; type?: string; valeur?: number }[];
    details_participations_financieres?: { denomination?: string; nombre_parts?: string; pourcentage_capital?: string; montant_euro?: number; controle_conseil?: string }[];
    details_participations_organes?: { denomination?: string; fonction?: string; remuneration?: number }[];
    details_revenus?: { type?: string; organisme?: string; montant?: number }[];
    details_biens_immobiliers?: { description?: string; nature?: string; lieu?: string; surface?: string; mode_acquisition?: string; date_acquisition?: string; valeur?: number }[];
    details_comptes_bancaires?: { etablissement?: string; type_compte?: string; description?: string; solde?: number }[];
    details_valeurs_bourse?: { denomination?: string; nature?: string; nombre?: string; valeur?: number }[];
    details_valeurs_non_bourse?: { denomination?: string; nature?: string; nombre?: string; valeur?: number }[];
    details_assurances_vie?: { organisme?: string; description?: string; valeur?: number }[];
    details_fonds?: { denomination?: string; gestionnaire?: string; valeur?: number }[];
    details_instruments_financiers?: { denomination?: string; nature?: string; valeur?: number }[];
    details_dettes?: { organisme?: string; description?: string; date_emprunt?: string; montant?: number }[];
    details_vehicules?: { marque?: string; modele?: string; annee?: string; mode_acquisition?: string; valeur?: number }[];
    details_parts_sci?: { denomination?: string; nombre_parts?: string; valeur?: number }[];
    details_biens_divers?: { description?: string; valeur?: number }[];
    details_activites_conjoint?: { denomination?: string; fonction?: string; remuneration?: number }[];
    details_fonctions_benevoles?: { denomination?: string; fonction?: string }[];
    details_activites_anterieures?: { denomination?: string; fonction?: string; date_debut?: string; date_fin?: string; remuneration?: number }[];
    details_activites_consultant?: { denomination?: string; fonction?: string; remuneration?: number }[];
    details_autres_liens_interets?: { description?: string; organisme?: string }[];
    details_collaborateurs?: { description?: string }[];
    details_observations?: { description?: string }[];
    declarations_detail?: { type?: string; label?: string; date_depot?: string; qualite?: string; organe?: string }[];
    // PDF metadata
    pdf_type_detected?: string;
    pdf_date_declaration?: string;
    pdf_neant_sections?: string[];
    pdf_declarations?: { source_pdf?: string; parsed_at?: string; extraction_method?: string; [key: string]: unknown }[];
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
