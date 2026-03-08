import { create } from 'zustand';

export type Lang = 'fr' | 'en';

interface LangStore {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const useLang = create<LangStore>((set) => ({
  lang: 'fr',
  setLang: (lang) => set({ lang }),
}));

const translations: Record<string, Record<Lang, string>> = {
  // Layout / Header
  'site.title': {
    fr: 'Transparence Nationale',
    en: 'National Transparency',
  },
  'site.subtitle': {
    fr: 'Données HATVP',
    en: 'HATVP Data',
  },
  // Landing page
  'landing.title': {
    fr: 'Patrimoine des Élu·es Français·es',
    en: 'Wealth of French Elected Officials',
  },
  'landing.subtitle': {
    fr: 'Explorez de manière interactive le patrimoine et les revenus des représentant·es de la République grâce aux données officielles de la HATVP',
    en: 'Interactively explore the wealth and income of French elected representatives using official HATVP data',
  },
  'landing.counted': {
    fr: 'élu·es recensé·es',
    en: 'elected officials listed',
  },
  'landing.official': {
    fr: 'Données HATVP officielles',
    en: 'Official HATVP data',
  },
  'landing.featured': {
    fr: 'Profils mis en avant',
    en: 'Featured Profiles',
  },
  'landing.featured.sub': {
    fr: '— les fiches les plus complètes',
    en: '— most complete records',
  },
  'landing.see_all': {
    fr: 'Voir la base complète',
    en: 'See full database',
  },
  'landing.see_all.sub': {
    fr: 'Utilisez la recherche pour trouver un·e élu·e spécifique',
    en: 'Use the search to find a specific elected official',
  },
  'landing.back_featured': {
    fr: 'Revenir aux profils mis en avant',
    en: 'Back to featured profiles',
  },
  'landing.no_result': {
    fr: 'Aucun résultat trouvé',
    en: 'No results found',
  },
  'landing.no_result.sub': {
    fr: 'Essayez de modifier votre recherche',
    en: 'Try modifying your search',
  },
  'loading': {
    fr: 'Chargement des données...',
    en: 'Loading data...',
  },
  // Home hero (landing page)
  'home.hero.title': {
    fr: 'Transparence Nationale',
    en: 'National Transparency',
  },
  'home.hero.lead': {
    fr: 'Toutes les déclarations de patrimoine et d\'intérêts des élu·es français·es, rendues lisibles et comparables.',
    en: 'All wealth and interest declarations of French elected officials, made readable and comparable.',
  },
  'home.hero.source': {
    fr: 'Source : Haute Autorité pour la Transparence de la Vie Publique (HATVP) — données ouvertes.',
    en: 'Source: High Authority for Transparency in Public Life (HATVP) — open data.',
  },
  'home.how.title': {
    fr: 'Comment lire une fiche',
    en: 'How to read a record',
  },
  'home.example.name': {
    fr: 'Exemple fictif',
    en: 'Fictional Example',
  },
  'home.example.fonction': {
    fr: 'Député·e de la 1ère circonscription',
    en: 'MP for the 1st constituency',
  },
  'home.example.region': {
    fr: 'Île-de-France',
    en: 'Île-de-France',
  },
  'home.example.groupe': {
    fr: 'Groupe Exemple',
    en: 'Example Group',
  },
  'home.legend.patrimoine': {
    fr: 'Patrimoine total déclaré (immobilier + placements + divers)',
    en: 'Total declared wealth (real estate + investments + other)',
  },
  'home.legend.revenus': {
    fr: 'Revenus annuels bruts déclarés (mandats + activités)',
    en: 'Declared gross annual income (mandates + activities)',
  },
  'home.legend.declarations': {
    fr: 'Nombre de déclarations publiées à la HATVP',
    en: 'Number of declarations published with HATVP',
  },
  'home.legend.mandats': {
    fr: 'Mandats et fonctions occupé·es',
    en: 'Mandates and positions held',
  },
  'home.legend.liens': {
    fr: 'Liens vers les sources officielles (HATVP, Assemblée, Sénat)',
    en: 'Links to official sources (HATVP, Assembly, Senate)',
  },
  'home.methodo.title': {
    fr: 'Méthodologie',
    en: 'Methodology',
  },
  'home.methodo.1': {
    fr: 'Les données proviennent exclusivement des déclarations publiques de la HATVP (XML + PDF).',
    en: 'Data comes exclusively from public HATVP declarations (XML + PDF).',
  },
  'home.methodo.2': {
    fr: 'Les montants sont extraits automatiquement et peuvent comporter des imprécisions.',
    en: 'Amounts are automatically extracted and may contain inaccuracies.',
  },
  'home.methodo.3': {
    fr: 'Chaque fiche renvoie vers la source officielle pour vérification.',
    en: 'Each record links to the official source for verification.',
  },
  'home.cta': {
    fr: 'Explorer les élu·es',
    en: 'Explore elected officials',
  },
  // SearchBar
  'search.placeholder': {
    fr: 'Rechercher un·e élu·e (nom, fonction, région...)',
    en: 'Search an official (name, position, region...)',
  },
  'search.sort.nom': {
    fr: 'Trier par Nom',
    en: 'Sort by Name',
  },
  'search.sort.patrimoine': {
    fr: 'Trier par Patrimoine',
    en: 'Sort by Wealth',
  },
  'search.sort.revenus': {
    fr: 'Trier par Revenus',
    en: 'Sort by Income',
  },
  'search.photos.on': {
    fr: 'Photos activées',
    en: 'Photos enabled',
  },
  'search.photos.off': {
    fr: 'Photos désactivées',
    en: 'Photos disabled',
  },
  // Mandat options
  'mandat.all': { fr: 'Tous les mandats', en: 'All mandates' },
  'mandat.depute': { fr: 'Député·es', en: 'MPs' },
  'mandat.senateur': { fr: 'Sénateur·ices', en: 'Senators' },
  'mandat.president': { fr: 'Président·e de la République', en: 'President of the Republic' },
  'mandat.gouvernement': { fr: 'Gouvernement', en: 'Government' },
  'mandat.europe': { fr: 'Député·es européen·nes', en: 'MEPs' },
  'mandat.region': { fr: 'Conseiller·ères régionaux·ales', en: 'Regional councillors' },
  'mandat.departement': { fr: 'Conseiller·ères départementaux·ales', en: 'Departmental councillors' },
  'mandat.commune': { fr: 'Élu·es municipaux·ales', en: 'Municipal officials' },
  'mandat.epci': { fr: 'Élu·es intercommunaux·ales', en: 'Intercommunal officials' },
  'mandat.ctsp': { fr: 'Collectivités territoriales', en: 'Territorial authorities' },
  'mandat.autre': { fr: 'Autres mandats', en: 'Other mandates' },
  // PersonCard
  'card.patrimoine': { fr: 'Patrimoine', en: 'Wealth' },
  'card.revenus': { fr: 'Revenus', en: 'Income' },
  'card.declarations': { fr: 'déclaration(s)', en: 'declaration(s)' },
  'card.data_pending': { fr: 'Données en cours', en: 'Data pending' },
  // Profile page
  'profil.back': { fr: 'Retour à la galerie', en: 'Back to gallery' },
  'profil.loading': { fr: 'Chargement du profil...', en: 'Loading profile...' },
  'profil.not_found': { fr: 'Élu·e non trouvé·e', en: 'Official not found' },
  'profil.fonction': { fr: 'Fonction', en: 'Position' },
  'profil.departement': { fr: 'Département', en: 'Department' },
  'profil.groupe': { fr: 'Groupe politique', en: 'Political group' },
  'profil.parti': { fr: 'Parti', en: 'Party' },
  'profil.type_mandat': { fr: 'Type de mandat', en: 'Mandate type' },
  'profil.declarations_hatvp': { fr: 'Déclarations HATVP', en: 'HATVP Declarations' },
  'profil.sources': { fr: 'Sources & Liens', en: 'Sources & Links' },
  'profil.patrimoine_total': { fr: 'Patrimoine Total', en: 'Total Wealth' },
  'profil.revenus_annuels': { fr: 'Revenus Annuels', en: 'Annual Income' },
  'profil.declare_hatvp': { fr: 'Déclaré à la HATVP', en: 'Declared to HATVP' },
  'profil.bruts_declares': { fr: 'Bruts déclarés', en: 'Gross declared' },
  'profil.no_financial': { fr: 'Données financières non disponibles', en: 'Financial data not available' },
  'profil.no_financial.sub': {
    fr: 'Les données patrimoniales et de revenus ne sont pas encore disponibles pour cet·te élu·e.',
    en: 'Wealth and income data are not yet available for this official.',
  },
  'profil.synthese': { fr: 'Synthèse des déclarations', en: 'Declaration Summary' },
  'profil.details.show': { fr: 'Voir les détails', en: 'Show details' },
  'profil.details.hide': { fr: 'Masquer les détails', en: 'Hide details' },
  'profil.patrimoine_ventilation': { fr: 'Ventilation du patrimoine', en: 'Wealth Breakdown' },
  'profil.actif_brut': { fr: 'Actif brut total', en: 'Total Gross Assets' },
  'profil.dettes_emprunts': { fr: 'Dettes et emprunts', en: 'Debts and Loans' },
  'profil.patrimoine_net': { fr: 'Patrimoine net', en: 'Net Wealth' },
  'profil.immobilier': { fr: 'Immobilier et foncier', en: 'Real Estate' },
  'profil.placements': { fr: 'Placements et investissements', en: 'Investments' },
  'profil.total_placements': { fr: 'Total placements', en: 'Total investments' },
  'profil.autres_biens': { fr: 'Autres biens', en: 'Other assets' },
  'profil.passif': { fr: 'Passif', en: 'Liabilities' },
  'profil.revenus_declares': { fr: 'Revenus déclarés', en: 'Declared income' },
  'profil.interets': { fr: 'Intérêts et activités déclarés', en: 'Declared interests and activities' },
  'profil.note_source': {
    fr: 'Pour consulter le détail complet :',
    en: 'For full details:',
  },
  'profil.see_full': { fr: 'Pour consulter le détail complet :', en: 'For full details:' },
  'profil.fiche_hatvp': { fr: 'fiche HATVP', en: 'HATVP record' },
  'profil.composition': { fr: 'Composition du Patrimoine', en: 'Wealth Composition' },
  'profil.mandats': { fr: 'Mandats et Fonctions', en: 'Mandates and Positions' },
  'profil.declarations': { fr: 'Déclarations HATVP', en: 'HATVP Declarations' },
  'profil.qualite': { fr: 'En qualité de :', en: 'As:' },
  'profil.publiee': { fr: 'Publiée le', en: 'Published on' },
  'profil.deposee': { fr: 'Déposée le', en: 'Filed on' },
  'profil.voir_hatvp': { fr: 'Voir toutes les déclarations sur hatvp.fr', en: 'View all declarations on hatvp.fr' },
  'profil.source_data': { fr: 'Sources des données', en: 'Data Sources' },
  'profil.source_text': {
    fr: 'Données issues de la',
    en: 'Data from the',
  },
  'profil.hatvp_name': {
    fr: 'Haute Autorité pour la Transparence de la Vie Publique (HATVP)',
    en: 'High Authority for Transparency in Public Life (HATVP)',
  },
  'profil.open_data': { fr: 'Open Data', en: 'Open Data' },
  'profil.last_update': { fr: 'Dernière mise à jour :', en: 'Last updated:' },
  // Mandat labels (profile page)
  'mandat_label.depute': { fr: 'Député·e', en: 'MP' },
  'mandat_label.senateur': { fr: 'Sénateur·ice', en: 'Senator' },
  'mandat_label.president': { fr: 'Président·e de la République', en: 'President of the Republic' },
  'mandat_label.gouvernement': { fr: 'Membre du Gouvernement', en: 'Government Member' },
  'mandat_label.europe': { fr: 'Député·e européen·ne', en: 'MEP' },
  'mandat_label.region': { fr: 'Conseiller·ère régional·e', en: 'Regional Councillor' },
  'mandat_label.departement': { fr: 'Conseiller·ère départemental·e', en: 'Departmental Councillor' },
  'mandat_label.commune': { fr: 'Élu·e municipal·e', en: 'Municipal Official' },
  'mandat_label.epci': { fr: 'Élu·e intercommunal·e', en: 'Intercommunal Official' },
  'mandat_label.ctsp': { fr: 'Élu·e collectivité territoriale', en: 'Territorial Authority Official' },
  'mandat_label.autre': { fr: 'Autre mandat', en: 'Other mandate' },
  // Footer
  'footer.copy': {
    fr: '© 2024 Transparence Nationale - Données issues de la',
    en: '© 2024 National Transparency - Data from the',
  },
  'footer.hatvp': {
    fr: 'Haute Autorité pour la Transparence de la Vie Publique',
    en: 'High Authority for Transparency in Public Life',
  },
  'footer.opensource': {
    fr: 'Projet open-source à des fins de transparence démocratique',
    en: 'Open-source project for democratic transparency',
  },
  // Charts
  'chart.immobilier': { fr: 'Immobilier', en: 'Real Estate' },
  'chart.placements': { fr: 'Placements', en: 'Investments' },
  'chart.autres': { fr: 'Autres', en: 'Other' },
  // New keys
  'profil.no_patrimoine_mandat': {
    fr: 'Son mandat n\'impose pas la déclaration de patrimoine. Seules les déclarations de situation patrimoniale des membres du gouvernement et des membres du collège de la Haute Autorité sont publiées sur hatvp.fr.',
    en: 'This mandate does not require a wealth declaration. Only the asset declarations of government members and members of the High Authority college are published on hatvp.fr.',
  },
  'profil.consult': { fr: 'Consultez la', en: 'Check the' },
  'profil.for_more': { fr: 'pour plus d\'informations.', en: 'for more information.' },
  'profil.revenus_par_an': { fr: 'Revenus annuels déclarés', en: 'Declared annual income' },
  'profil.an': { fr: 'an', en: 'year' },
  'profil.click_detail_mandats': { fr: 'Cliquez pour voir le détail par fonction / mandat', en: 'Click for detail by function / mandate' },
  'profil.total_all_years': { fr: 'Total cumulé (toutes années)', en: 'Cumulative total (all years)' },
  'profil.no_patrimoine_title': {
    fr: 'Patrimoine non déclaré',
    en: 'No wealth declaration',
  },
  'profil.patrimoine_en_cours': {
    fr: 'Les déclarations de situation patrimoniale existent mais sont en cours de traitement ou de contrôle par la HATVP. Les données détaillées seront disponibles prochainement.',
    en: 'Wealth declarations exist but are being processed or reviewed by HATVP. Detailed data will be available soon.',
  },
};

export function t(key: string, lang: Lang): string {
  return translations[key]?.[lang] ?? key;
}
