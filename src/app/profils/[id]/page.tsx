'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowLeft, ExternalLink, User, Briefcase, MapPin, Calendar, FileText, Scale, Building2, Landmark, Users, TrendingUp, ChevronDown, ChevronUp, Info } from 'lucide-react';
import { Elu } from '@/lib/types';
import { useLang, t } from '@/lib/i18n';
import PortfolioChart from '@/components/PortfolioChart';

// Mapping type_mandat → label lisible
const MANDAT_LABEL_KEYS: Record<string, string> = {
  depute: 'mandat_label.depute',
  senateur: 'mandat_label.senateur',
  president: 'mandat_label.president',
  gouvernement: 'mandat_label.gouvernement',
  europe: 'mandat_label.europe',
  region: 'mandat_label.region',
  departement: 'mandat_label.departement',
  commune: 'mandat_label.commune',
  epci: 'mandat_label.epci',
  ctsp: 'mandat_label.ctsp',
  autre: 'mandat_label.autre',
};

// Mandate types that require patrimoine declaration (government + HATVP college members)
const PATRIMOINE_REQUIRED_MANDATE_TYPES = ['gouvernement', 'president'];

const DOC_TYPE_LABELS: Record<string, string> = {
  DSP: 'Déclaration de Situation Patrimoniale',
  DSPM: 'DSP — Modification',
  DSPFM: 'DSP — Fin de mandat',
  DSPFIN: 'DSP (ancien format)',
  DI: "Déclaration d'Intérêts",
  DIM: "DI — Modification",
  DIA: "Déclaration d'Intérêts et d'Activités",
  DIAM: "DIA — Modification",
};

// Labels pour les sections HATVP détaillées (sans emojis, avec icônes Lucide)
const HATVP_SECTION_CONFIG: Record<string, { label: string; category: 'patrimoine' | 'interets' | 'autre' }> = {
  nb_biens_immobiliers:            { label: 'Biens immobiliers',            category: 'patrimoine' },
  nb_parts_sci:                    { label: 'Parts de SCI',                 category: 'patrimoine' },
  nb_comptes_bancaires:            { label: 'Comptes bancaires',            category: 'patrimoine' },
  nb_assurances_vie:               { label: 'Assurances vie',               category: 'patrimoine' },
  nb_valeurs_bourse:               { label: 'Valeurs cotées en bourse',     category: 'patrimoine' },
  nb_valeurs_non_bourse:           { label: 'Valeurs non cotées',           category: 'patrimoine' },
  nb_instruments_financiers:       { label: 'Instruments financiers',       category: 'patrimoine' },
  nb_participations_financieres:   { label: 'Participations financières',   category: 'patrimoine' },
  nb_fonds:                        { label: 'Fonds',                        category: 'patrimoine' },
  nb_biens_divers:                 { label: 'Biens divers',                 category: 'patrimoine' },
  nb_autres_biens:                 { label: 'Autres biens',                 category: 'patrimoine' },
  nb_biens_etrangers:              { label: 'Biens à l\'étranger',          category: 'patrimoine' },
  nb_vehicules:                    { label: 'Véhicules',                    category: 'patrimoine' },
  nb_biens_mobiliers_valeur:       { label: 'Biens mobiliers de valeur',    category: 'patrimoine' },
  nb_dettes:                       { label: 'Dettes et emprunts',           category: 'patrimoine' },
  nb_revenus:                      { label: 'Revenus déclarés',             category: 'patrimoine' },
  nb_evenements_majeurs:           { label: 'Événements patrimoniaux',      category: 'patrimoine' },
  nb_activites_consultant:         { label: 'Activités de consultant',      category: 'interets' },
  nb_activites_professionnelles:   { label: 'Activités professionnelles',   category: 'interets' },
  nb_activites_anterieures:        { label: 'Activités antérieures',        category: 'interets' },
  nb_mandats_electifs:             { label: 'Mandats électifs',             category: 'interets' },
  nb_participations_organes:       { label: 'Participations à des organes', category: 'interets' },
  nb_fonctions_benevoles:          { label: 'Fonctions bénévoles',          category: 'interets' },
  nb_activites_conjoint:           { label: 'Activités du·de la conjoint·e',        category: 'interets' },
  nb_activites_collaborateurs:     { label: 'Activités collaborateur·ices',     category: 'interets' },
  nb_autres_liens_interets:        { label: 'Autres liens d\'intérêts',     category: 'interets' },
  nb_autres_activites:             { label: 'Autres activités',             category: 'interets' },
  nb_fonctions_gouvernementales:   { label: 'Fonctions gouvernementales',   category: 'interets' },
  nb_fonctions_consultatives:      { label: 'Fonctions consultatives',      category: 'interets' },
  nb_participations_exploitant:    { label: 'Participations exploitant',    category: 'interets' },
};

// Mapping nb_* keys → details_* keys in hatvp data
const NB_TO_DETAILS_KEY: Record<string, string> = {
  nb_biens_immobiliers: 'details_biens_immobiliers',
  nb_parts_sci: 'details_parts_sci',
  nb_comptes_bancaires: 'details_comptes_bancaires',
  nb_assurances_vie: 'details_assurances_vie',
  nb_valeurs_bourse: 'details_valeurs_bourse',
  nb_valeurs_non_bourse: 'details_valeurs_non_bourse',
  nb_instruments_financiers: 'details_instruments_financiers',
  nb_participations_financieres: 'details_participations_financieres',
  nb_fonds: 'details_fonds',
  nb_biens_divers: 'details_biens_divers',
  nb_vehicules: 'details_vehicules',
  nb_dettes: 'details_dettes',
  nb_revenus: 'details_revenus',
  nb_activites_consultant: 'details_activites_consultant',
  nb_activites_professionnelles: 'details_activites',
  nb_activites_anterieures: 'details_activites_anterieures',
  nb_mandats_electifs: 'details_mandats',
  nb_participations_organes: 'details_participations_organes',
  nb_fonctions_benevoles: 'details_fonctions_benevoles',
  nb_activites_conjoint: 'details_activites_conjoint',
  nb_activites_collaborateurs: 'details_collaborateurs',
  nb_autres_liens_interets: 'details_autres_liens_interets',
};

// Human-readable labels for detail fields
const DETAIL_FIELD_LABELS: Record<string, string> = {
  denomination: 'Dénomination',
  description: 'Description',
  nature: 'Nature',
  lieu: 'Lieu',
  departement: 'Département',
  surface: 'Surface',
  mode_acquisition: 'Mode d\'acquisition',
  date_acquisition: 'Date d\'acquisition',
  etablissement: 'Établissement',
  type_compte: 'Type de compte',
  nombre: 'Nombre',
  gestionnaire: 'Gestionnaire',
  date_emprunt: 'Date d\'emprunt',
  marque: 'Marque',
  modele: 'Modèle',
  annee: 'Année',
  nombre_parts: 'Nombre de parts',
  fonction: 'Fonction',
  organisme: 'Organisme',
  mandat: 'Mandat',
  type: 'Type',
  date_debut: 'Début',
  date_fin: 'Fin',
  employeur: 'Employeur',
  periode: 'Période',
  commentaire: 'Commentaire',
  valeur: 'Valeur',
  solde: 'Solde',
  montant: 'Montant',
  remuneration: 'Rémunération',
  profession_conjoint: 'Profession du·de la conjoint·e',
  employeur_conjoint: 'Employeur du·de la conjoint·e',
  type_revenu: 'Type de revenu',
  capital_restant_du: 'Capital restant dû',
  type_bien: 'Type de bien',
  localisation: 'Localisation',
  surface_m2: 'Surface (m²)',
  type_instrument: 'Type d\'instrument',
  salaire_euro: 'Salaire',
  revenus_annuels: 'Revenus annuels',
  // PDF-specific fields
  montant_euro: 'Montant total',
  pourcentage_capital: 'Capital détenu',
  controle_conseil: 'Contrôle activité de conseil',
  statut: 'Statut',
  date_declaration: 'Date de déclaration',
  role: 'Rôle',
};

// Fields that represent money amounts (displayed with formatMoney)
const MONEY_FIELDS = new Set(['valeur', 'solde', 'montant', 'remuneration', 'capital_restant_du', 'salaire_euro', 'montant_euro']);

/**
 * Deduplicate an array of detail items by comparing their non-financial string fields.
 * Items that have the same key fields (ignoring financial values that may differ across declarations)
 * are merged, keeping the one with the highest financial value.
 */
function deduplicateDetails(items: Record<string, unknown>[]): Record<string, unknown>[] {
  if (!items || items.length <= 1) return items;
  const seen = new Map<string, Record<string, unknown>>();
  for (const item of items) {
    // Build a key from non-financial, non-empty string fields
    const keyParts: string[] = [];
    for (const [k, v] of Object.entries(item)) {
      if (MONEY_FIELDS.has(k) || v == null || v === '') continue;
      keyParts.push(`${k}:${String(v).toLowerCase().trim()}`);
    }
    keyParts.sort();
    const key = keyParts.join('|');
    if (!key) {
      // Items with no string fields — keep all
      seen.set(`__empty_${seen.size}`, item);
      continue;
    }
    const existing = seen.get(key);
    if (!existing) {
      seen.set(key, item);
    } else {
      // Keep the one with higher financial value
      let existingVal = 0;
      let newVal = 0;
      for (const f of MONEY_FIELDS) {
        if (typeof existing[f] === 'number') existingVal = Math.max(existingVal, existing[f] as number);
        if (typeof item[f] === 'number') newVal = Math.max(newVal, item[f] as number);
      }
      if (newVal > existingVal) {
        seen.set(key, item);
      }
    }
  }
  return Array.from(seen.values());
}

/**
 * Compute per-year revenue totals from all activities and mandates.
 * Aggregates revenus_annuels from details_activites and details_mandats.
 * Returns { yearTotals: Map<string, number>, lastYear: string | null, lastYearTotal: number, grandTotal: number }.
 */
function computeYearlyRevenues(
  detailsActivites?: Record<string, unknown>[],
  detailsMandats?: Record<string, unknown>[],
): { yearTotals: Map<string, number>; lastYear: string | null; lastYearTotal: number; grandTotal: number } {
  const yearTotals = new Map<string, number>();

  const processItems = (items?: Record<string, unknown>[]) => {
    if (!items) return;
    for (const item of items) {
      const annuels = item.revenus_annuels as { annee?: string; montant?: number }[] | undefined;
      if (annuels && Array.isArray(annuels)) {
        for (const ys of annuels) {
          if (ys.annee && typeof ys.montant === 'number' && ys.montant > 0) {
            yearTotals.set(ys.annee, (yearTotals.get(ys.annee) || 0) + ys.montant);
          }
        }
      }
    }
  };

  processItems(detailsActivites);
  processItems(detailsMandats);

  let lastYear: string | null = null;
  let lastYearNum = 0;
  let lastYearTotal = 0;
  let grandTotal = 0;

  for (const [year, total] of yearTotals.entries()) {
    grandTotal += total;
    const yearNum = parseInt(year, 10) || 0;
    if (yearNum > lastYearNum) {
      lastYearNum = yearNum;
      lastYear = year;
      lastYearTotal = total;
    }
  }

  return { yearTotals, lastYear, lastYearTotal, grandTotal };
}

/**
 * Categorize mandats into current and past.
 * A mandat is considered "past" if the HATVP details_mandats indicate it has ended (date_fin).
 */
function categorizeMandats(
  mandats: string[],
  fonction: string,
  detailMandats?: { mandat?: string; organisme?: string; date_fin?: string }[]
): { current: string[]; past: string[] } {
  const uniqueMandats = [...new Set(mandats)];
  const currentFonction = (fonction || '').toLowerCase().trim();

  const pastMandatLabels = new Set<string>();
  if (detailMandats) {
    for (const dm of detailMandats) {
      if (dm.date_fin && dm.date_fin.trim()) {
        const label = (dm.mandat || dm.organisme || '').toLowerCase().trim();
        if (label) pastMandatLabels.add(label);
      }
    }
  }

  const current = uniqueMandats.filter(m => {
    const ml = m.toLowerCase().trim();
    if (ml === currentFonction || currentFonction.includes(ml) || ml.includes(currentFonction)) return true;
    return !pastMandatLabels.has(ml);
  });

  const past = uniqueMandats.filter(m => !current.includes(m));

  return { current, past };
}

function DetailItemRenderer({ item, formatMoney }: { item: Record<string, unknown>; formatMoney: (v: number) => string }) {
  // Find the primary label (denomination, description, mandat, or first string field)
  const primaryKey = ['denomination', 'description', 'mandat', 'marque', 'etablissement', 'organisme', 'type'].find(k => item[k] != null && item[k] !== '');
  const primaryValue = primaryKey ? String(item[primaryKey]) : null;

  // Fields to skip in the "other fields" list (metadata or already displayed)
  const skipFields = new Set([primaryKey || '', 'montants_details', 'description']);

  // Collect other fields
  const otherFields = Object.entries(item).filter(([key, val]) => {
    if (skipFields.has(key) || val == null || val === '' || val === 0) return false;
    return true;
  });

  return (
    <div className="p-2.5 bg-th-bg-secondary/80 rounded-lg text-sm border border-th-border/50">
      {primaryValue && <p className="text-th-text font-medium">{primaryValue}</p>}
      {otherFields.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {otherFields.map(([key, val]) => {
            const label = DETAIL_FIELD_LABELS[key] || key.replace(/_/g, ' ');
            const isMoney = MONEY_FIELDS.has(key);

            // Handle revenus_annuels array display
            if (key === 'revenus_annuels' && Array.isArray(val)) {
              return (
                <div key={key} className="mt-1">
                  <p className="text-xs text-th-text-muted mb-0.5">{label} :</p>
                  <div className="ml-2 space-y-0.5">
                    {(val as { annee?: string; montant?: number }[]).map((ys, idx) => (
                      <p key={idx} className="text-xs text-yellow-500 font-semibold">
                        {ys.annee} : {typeof ys.montant === 'number' ? formatMoney(ys.montant) : '—'}
                      </p>
                    ))}
                  </div>
                </div>
              );
            }

            const display = isMoney && typeof val === 'number' ? formatMoney(val) : String(val);
            return (
              <p key={key} className={`text-xs ${isMoney ? 'text-yellow-500 font-semibold' : 'text-th-text-muted'}`}>
                <span className="text-th-text-muted">{label} :</span> {display}
              </p>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ProfilPage() {
  const params = useParams();
  const router = useRouter();
  const [elu, setElu] = useState<Elu | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showPastMandats, setShowPastMandats] = useState(false);
  const { lang } = useLang();

  const toggleSection = (key: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  useEffect(() => {
    const fetchElu = async () => {
      // Load from per-person JSON (contains ALL data: details + financial summaries)
      try {
        const detailResp = await fetch(`/data/elus/${params.id}.json`);
        if (detailResp.ok) {
          const data: Elu = await detailResp.json();
          setElu(data);
          setLoading(false);
          return;
        }
      } catch {
        // Individual file not available, try fallback
      }

      // Fallback: load from slim elus.json (list-page data only)
      try {
        const response = await fetch('/data/elus.json');
        const data: Elu[] = await response.json();
        const found = data.find((e) => e.id === params.id) || null;
        setElu(found);
      } catch (error) {
        console.error('Erreur:', error);
      }
      setLoading(false);
    };

    fetchElu();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-red-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-th-text-muted">Chargement du profil...</p>
        </div>
      </div>
    );
  }

  if (!elu) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center py-16">
          <User size={64} className="text-th-text-muted mx-auto mb-4" />
          <h3 className="text-2xl font-bold text-th-text mb-2">
            Élu non trouvé
          </h3>
          <button
            onClick={() => router.push('/liste')}
            className="mt-4 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Retour à la galerie
          </button>
        </div>
      </div>
    );
  }

  const formatMoney = (value: number) => {
    if (!value) return '—';
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const hasPatrimoineData = (elu.patrimoine || 0) > 0 || (elu.immobilier || 0) > 0;
  const hasRevenusData = (elu.revenus || 0) > 0;
  const hasFinancialData = hasPatrimoineData || hasRevenusData;
  const placementsMontant = elu.placements_montant || (typeof elu.placements === 'number' ? elu.placements : 0);
  const photoSrc = elu.photo_url || (elu.photo !== '/photos/placeholder.jpg' ? elu.photo : '');

  // Check if this person has DSP (patrimoine) declarations
  const hasDspDeclarations = elu.declarations_csv?.some(d => d.type.startsWith('DSP'));
  // Check if mandate type requires patrimoine
  const hasPatrimoineMandat = elu.types_mandat?.some((tp) => PATRIMOINE_REQUIRED_MANDATE_TYPES.includes(tp));

  // Collecter les sections HATVP détaillées qui ont des données
  // Exclure les champs meta (nb_declarations_hatvp) et ne garder que les sections de contenu
  const HATVP_META_FIELDS = new Set(['nb_declarations_hatvp']);
  const hatvpSections = elu.hatvp
    ? Object.entries(elu.hatvp)
        .filter(([key, val]) => key.startsWith('nb_') && !HATVP_META_FIELDS.has(key) && typeof val === 'number' && val > 0)
        .map(([key, val]) => ({
          key,
          count: val as number,
          label: HATVP_SECTION_CONFIG[key]?.label || key.replace('nb_', '').replace(/_/g, ' '),
          category: HATVP_SECTION_CONFIG[key]?.category || 'autre',
          value: elu.hatvp?.[key.replace('nb_', 'valeur_') + '_euro'] as number | undefined,
        }))
    : [];

  // Calculer des totaux pour l'affichage
  const totalActifBrut = elu.hatvp?.total_actif_brut_euro || 0;
  const totalDettes = elu.hatvp?.total_dettes_euro || 0;
  const patrimoineNet = elu.hatvp?.patrimoine_net_euro || 0;

  // Use pre-computed yearly revenue data from JSON when available,
  // fall back to computing from details on the client side.
  const precomputedLastYear = elu.hatvp?.last_year_label as string | undefined;
  const precomputedLastYearRevenus = elu.hatvp?.last_year_revenus as number | undefined;
  const precomputedTotalAll = elu.hatvp?.total_revenus_all_years as number | undefined;

  let hasYearlyData: boolean;
  let lastYearLabel: string | null;
  let lastYearRevenu: number;
  let yearlyRevenuesGrandTotal: number;

  if (precomputedLastYear && typeof precomputedLastYearRevenus === 'number' && precomputedLastYearRevenus > 0) {
    hasYearlyData = true;
    lastYearLabel = precomputedLastYear;
    lastYearRevenu = precomputedLastYearRevenus;
    yearlyRevenuesGrandTotal = precomputedTotalAll || precomputedLastYearRevenus;
  } else {
    // Fallback: compute on the client
    const yearlyRevenues = computeYearlyRevenues(
      elu.hatvp?.details_activites as Record<string, unknown>[] | undefined,
      elu.hatvp?.details_mandats as Record<string, unknown>[] | undefined,
    );
    hasYearlyData = yearlyRevenues.lastYear !== null;
    lastYearLabel = yearlyRevenues.lastYear;
    lastYearRevenu = yearlyRevenues.lastYearTotal;
    yearlyRevenuesGrandTotal = yearlyRevenues.grandTotal;
  }

  // Sections that have expandable details
  const expandableSectionKeys = hatvpSections
    .filter(({ key }) => {
      const dk = NB_TO_DETAILS_KEY[key];
      const d = dk ? (elu.hatvp?.[dk] as Record<string, unknown>[] | undefined) : undefined;
      return d && d.length > 0;
    })
    .map(({ key }) => key);
  const allSectionsExpanded = expandableSectionKeys.length > 0 && expandableSectionKeys.every(k => expandedSections.has(k));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-12">
      {/* Bouton retour */}
      <motion.button
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={() => router.push('/liste')}
        className="flex items-center gap-2 text-th-text-muted hover:text-red-500 mb-6 sm:mb-8 transition-colors"
      >
        <ArrowLeft size={20} />
        <span className="font-medium">Retour à la galerie</span>
      </motion.button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        {/* Colonne gauche - Photo et infos */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="lg:col-span-1"
        >
          <div className="bg-th-card rounded-xl shadow-lg overflow-hidden sticky top-20 sm:top-24 border-2 border-red-700">
            {/* Photo — affichée en entier */}
            <div className="relative aspect-[3/4] max-h-80 sm:max-h-96 bg-gradient-to-br from-red-100 dark:from-red-900/40 to-gray-50 dark:to-neutral-800">
              {photoSrc ? (
                <Image
                  src={photoSrc}
                  alt={`${elu.prenom} ${elu.nom}`}
                  fill
                  className="object-contain"
                  priority
                  unoptimized={!!elu.photo_url}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <User size={100} className="text-th-text-muted" />
                </div>
              )}
            </div>

            {/* Infos de base */}
            <div className="p-4 sm:p-6">
              <h1 className="text-xl sm:text-2xl font-bold text-th-text mb-2">
                {elu.prenom} {elu.nom}
              </h1>
              
              <div className="space-y-2.5 sm:space-y-3 mb-4 sm:mb-6">
                <div className="flex items-start gap-2 sm:gap-3">
                  <Briefcase size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs text-th-text-muted">Fonction</p>
                    <p className="font-semibold text-th-text text-sm sm:text-base">{elu.fonction}</p>
                  </div>
                </div>
                
                {elu.region && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <MapPin size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-th-text-muted">Département</p>
                      <p className="font-semibold text-th-text text-sm sm:text-base">{elu.region}</p>
                    </div>
                  </div>
                )}

                {elu.groupe && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Users size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-th-text-muted">Groupe politique</p>
                      <p className="font-semibold text-th-text text-sm sm:text-base">{elu.groupe}</p>
                    </div>
                  </div>
                )}

                {elu.parti && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Building2 size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-th-text-muted">Parti</p>
                      <p className="font-semibold text-th-text text-sm sm:text-base">{elu.parti}</p>
                    </div>
                  </div>
                )}

                {elu.types_mandat && elu.types_mandat.length > 0 && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Landmark size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-th-text-muted">Type de mandat</p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {elu.types_mandat.map((tm) => (
                          <span
                            key={tm}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-900/30 text-red-300"
                          >
                            {MANDAT_LABEL_KEYS[tm] ? t(MANDAT_LABEL_KEYS[tm], lang) : tm}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Nombre de déclarations retiré du sidebar */}
              </div>

              {/* Liens externes */}
              {(elu.liens?.assemblee || elu.liens?.hatvp || elu.liens?.senat || elu.liens?.wikipedia) && (
                <div className="border-t border-th-border pt-4">
                  <p className="text-sm font-semibold text-th-text-secondary mb-3">
                    Sources & Liens
                  </p>
                  <div className="space-y-2">
                    {elu.liens?.hatvp && (
                      <a
                        href={elu.liens?.hatvp}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Fiche HATVP
                      </a>
                    )}
                    {elu.liens?.assemblee && (
                      <a
                        href={elu.liens?.assemblee}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Assemblée Nationale
                      </a>
                    )}
                    {elu.liens?.senat && (
                      <a
                        href={elu.liens?.senat}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Sénat
                      </a>
                    )}
                    {elu.liens?.wikipedia && (
                      <a
                        href={elu.liens?.wikipedia}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Wikipedia
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* Colonne droite - Stats et détails */}
        <div className="lg:col-span-2 space-y-5 sm:space-y-6">
          {/* Stats Cards — show revenus and patrimoine independently */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="space-y-3 sm:space-y-4"
          >
            {/* Revenue + Patrimoine Cards */}
            {hasFinancialData && (
              <div className={`grid gap-3 sm:gap-6 ${hasPatrimoineData && hasRevenusData ? 'grid-cols-2' : 'grid-cols-1'}`}>
                {hasPatrimoineData && (
                  <div className="bg-gradient-to-br from-red-700 to-red-800 rounded-xl shadow-lg p-4 sm:p-6 text-white">
                    <p className="text-red-200 text-xs sm:text-sm font-medium mb-1 sm:mb-2">
                      Patrimoine Total
                    </p>
                    <p className="text-xl sm:text-3xl font-bold mb-0.5 sm:mb-1">
                      {formatMoney(elu.patrimoine || 0)}
                    </p>
                    <p className="text-red-200 text-[10px] sm:text-xs">
                      Déclaré à la HATVP
                    </p>
                  </div>
                )}

                {hasRevenusData && (
                  <div className="bg-gradient-to-br from-yellow-600 to-yellow-700 rounded-xl shadow-lg p-4 sm:p-6 text-white">
                    <p className="text-yellow-100 text-xs sm:text-sm font-medium mb-1 sm:mb-2">
                      {hasYearlyData
                        ? `${t('profil.revenus_declares', lang)} (${lastYearLabel})`
                        : t('profil.revenus_declares', lang)
                      }
                    </p>
                    <p className="text-xl sm:text-3xl font-bold mb-0.5 sm:mb-1">
                      {formatMoney(hasYearlyData ? lastYearRevenu : (elu.revenus || 0))}
                    </p>
                    <p className="text-yellow-100 text-[10px] sm:text-xs">
                      {t('profil.bruts_declares', lang)}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Patrimoine explanation when missing */}
            {!hasPatrimoineData && (
              <div className="bg-th-card/60 border border-th-border rounded-xl p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <Scale size={20} className="text-th-text-muted mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="text-sm sm:text-base font-semibold text-th-text-secondary mb-1">
                      {t('profil.no_patrimoine_title', lang)}
                    </h3>
                    <p className="text-xs sm:text-sm text-th-text-muted">
                      {(() => {
                        if (hasDspDeclarations) {
                          return t('profil.patrimoine_en_cours', lang);
                        }
                        if (!hasPatrimoineMandat) {
                          return t('profil.no_patrimoine_mandat', lang);
                        }
                        return (
                          <>
                            {t('profil.no_financial.sub', lang)}
                            {elu.liens?.hatvp && (
                              <>
                                {' '}{t('profil.consult', lang)}{' '}
                                <a href={elu.liens?.hatvp} target="_blank" rel="noopener noreferrer" className="underline font-medium text-red-400">
                                  {t('profil.fiche_hatvp', lang)}
                                </a>
                                {' '}{t('profil.for_more', lang)}
                              </>
                            )}
                          </>
                        );
                      })()}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* No financial data at all */}
            {!hasFinancialData && !hatvpSections.length && (
              <div className="bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 rounded-xl p-4 sm:p-6">
                <div className="flex items-start gap-3">
                  <Scale size={22} className="text-yellow-600 dark:text-yellow-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="text-base sm:text-lg font-semibold text-yellow-800 dark:text-yellow-300 mb-1">
                      {t('profil.no_financial', lang)}
                    </h3>
                    <p className="text-xs sm:text-sm text-yellow-700 dark:text-yellow-200/80">
                      {t('profil.no_financial.sub', lang)}
                      {elu.liens?.hatvp && (
                        <>
                          {' '}{t('profil.consult', lang)}{' '}
                          <a href={elu.liens?.hatvp} target="_blank" rel="noopener noreferrer" className="underline font-medium">
                            {t('profil.fiche_hatvp', lang)}
                          </a>
                          {' '}{t('profil.for_more', lang)}
                        </>
                      )}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </motion.div>

          {/* Detail patrimoine HATVP */}
          {hatvpSections.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 }}
              className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg sm:text-xl font-bold text-th-text flex items-center gap-2">
                  <TrendingUp size={20} className="text-red-500" />
                  {t('profil.synthese', lang)}
                </h3>
                <button
                  onClick={() => {
                    if (allSectionsExpanded) {
                      setExpandedSections(new Set());
                    } else {
                      setExpandedSections(new Set(expandableSectionKeys));
                    }
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-500 bg-red-900/30 rounded-lg hover:bg-red-900/50 transition-colors"
                >
                  <Info size={14} />
                  {allSectionsExpanded ? t('profil.details.hide', lang) : t('profil.details.show', lang)}
                  {allSectionsExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>

              {/* Revenus annuels en premier — dernier exercice déclaré, cliquable pour détail */}
              {(() => {
                const totalRevenus = elu.hatvp?.total_revenus_euro || elu.revenus || 0;
                const detailsActivites = elu.hatvp?.details_activites as Record<string, unknown>[] | undefined;
                const detailsMandats = elu.hatvp?.details_mandats as Record<string, unknown>[] | undefined;

                // Build a list of revenue items per function/mandate
                const revenueByFunction: { label: string; montant: number }[] = [];
                if (detailsActivites) {
                  for (const item of deduplicateDetails(detailsActivites)) {
                    const label = (item.denomination || item.employeur || item.organisme || 'Activité') as string;
                    const montant = (item.montant_euro || item.remuneration || item.montant || 0) as number;
                    if (montant > 0) revenueByFunction.push({ label, montant });
                  }
                }
                if (detailsMandats) {
                  for (const item of deduplicateDetails(detailsMandats)) {
                    const label = (item.mandat || item.organisme || 'Mandat') as string;
                    const montant = (item.montant_euro || item.remuneration || item.montant || 0) as number;
                    if (montant > 0) revenueByFunction.push({ label, montant });
                  }
                }

                // Summary amount: last year's total if yearly data available, otherwise overall total
                const summaryAmount = hasYearlyData ? lastYearRevenu : totalRevenus;
                const summaryLabel = hasYearlyData
                  ? `${t('profil.revenus_par_an', lang)} (${lastYearLabel})`
                  : t('profil.revenus_par_an', lang);

                const isRevenusExpanded = expandedSections.has('__revenus_annual');

                if (totalRevenus > 0 || revenueByFunction.length > 0) {
                  return (
                    <div className="mb-4">
                      <button
                        onClick={() => toggleSection('__revenus_annual')}
                        className={`w-full p-3 rounded-lg transition-colors cursor-pointer ${
                          isRevenusExpanded ? 'bg-yellow-100 dark:bg-yellow-900/40 border border-yellow-300 dark:border-yellow-700' : 'bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 hover:bg-yellow-100 dark:hover:bg-yellow-900/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {isRevenusExpanded ? <ChevronUp size={14} className="text-yellow-600 dark:text-yellow-500" /> : <ChevronDown size={14} className="text-yellow-600 dark:text-yellow-500" />}
                            <span className="text-sm font-semibold text-yellow-800 dark:text-yellow-300">{summaryLabel}</span>
                          </div>
                          <p className="text-lg font-bold text-yellow-900 dark:text-yellow-200">{formatMoney(summaryAmount)}</p>
                        </div>
                        {revenueByFunction.length > 1 && !isRevenusExpanded && (
                          <p className="text-xs text-yellow-600 dark:text-yellow-500 mt-1 text-left">{t('profil.click_detail_mandats', lang)}</p>
                        )}
                      </button>
                      {isRevenusExpanded && revenueByFunction.length > 0 && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          transition={{ duration: 0.2 }}
                          className="mt-1 ml-4 space-y-1 pb-1"
                        >
                          {revenueByFunction.map((rf, idx) => (
                            <div key={idx} className="p-2.5 bg-th-bg-secondary/80 rounded-lg text-sm border border-th-border/50 flex items-center justify-between">
                              <span className="text-th-text font-medium">{rf.label}</span>
                              <span className="text-yellow-700 dark:text-yellow-500 font-semibold">{formatMoney(rf.montant)}</span>
                            </div>
                          ))}
                          {/* Total across all years */}
                          {hasYearlyData && yearlyRevenuesGrandTotal > lastYearRevenu && (
                            <div className="p-2.5 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg text-sm border border-yellow-300 dark:border-yellow-800 flex items-center justify-between mt-2">
                              <span className="text-yellow-800 dark:text-yellow-300 font-semibold">{t('profil.total_all_years', lang)}</span>
                              <span className="text-yellow-900 dark:text-yellow-200 font-bold">{formatMoney(yearlyRevenuesGrandTotal)}</span>
                            </div>
                          )}
                        </motion.div>
                      )}
                    </div>
                  );
                }
                return null;
              })()}

              {/* Totaux patrimoine */}
              {(totalActifBrut > 0 || patrimoineNet > 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                  {totalActifBrut > 0 && (
                    <div className="p-3 bg-red-50 dark:bg-red-900/30 rounded-lg border border-red-200 dark:border-red-800">
                      <p className="text-xs text-red-600 dark:text-red-500 font-medium">{t('profil.actif_brut', lang)}</p>
                      <p className="text-lg font-bold text-red-800 dark:text-red-200">{formatMoney(totalActifBrut)}</p>
                    </div>
                  )}
                  {totalDettes > 0 && (
                    <div className="p-3 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg border border-yellow-300 dark:border-yellow-800">
                      <p className="text-xs text-yellow-700 dark:text-yellow-500 font-medium">{t('profil.dettes_emprunts', lang)}</p>
                      <p className="text-lg font-bold text-yellow-900 dark:text-yellow-200">-{formatMoney(totalDettes)}</p>
                    </div>
                  )}
                  {patrimoineNet > 0 && (
                    <div className="p-3 bg-th-bg-secondary/50 rounded-lg border border-th-border">
                      <p className="text-xs text-th-text-muted font-medium">{t('profil.patrimoine_net', lang)}</p>
                      <p className="text-lg font-bold text-th-text">{formatMoney(patrimoineNet)}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Sections — each is an expandable dropdown with deduplicated details */}
              <div className="space-y-1.5">
                {hatvpSections.map(({ key, count, label, value }) => {
                  const detailsKey = NB_TO_DETAILS_KEY[key];
                  const rawDetails = detailsKey ? (elu.hatvp?.[detailsKey] as Record<string, unknown>[] | undefined) : undefined;
                  const details = rawDetails ? deduplicateDetails(rawDetails) : undefined;
                  const hasDetails = details && details.length > 0;
                  const dedupCount = details ? details.length : count;
                  const isExpanded = expandedSections.has(key);

                  return (
                    <div key={key}>
                      <button
                        onClick={() => hasDetails && toggleSection(key)}
                        className={`w-full flex items-center justify-between p-3 rounded-lg transition-colors ${
                          isExpanded ? 'bg-th-bg-secondary/60' : 'bg-th-bg-secondary/60'
                        } ${hasDetails ? 'cursor-pointer hover:bg-th-bg-secondary/50' : 'cursor-default'}`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {hasDetails ? (
                            isExpanded
                              ? <ChevronUp size={14} className="text-red-500 flex-shrink-0" />
                              : <ChevronDown size={14} className="text-red-500 flex-shrink-0" />
                          ) : (
                            <div className="w-3.5 h-3.5 flex items-center justify-center flex-shrink-0">
                              <div className="w-2 h-2 rounded-full bg-red-500/30" />
                            </div>
                          )}
                          <span className="text-sm text-th-text-secondary truncate text-left">{label}</span>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <span className="text-sm font-bold text-th-text">{dedupCount}</span>
                          {value != null && value > 0 && (
                            <p className="text-xs text-th-text-muted">{formatMoney(value)}</p>
                          )}
                        </div>
                      </button>

                      {isExpanded && details && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          transition={{ duration: 0.2 }}
                          className="mt-1 ml-4 space-y-1 pb-1"
                        >
                          {details.map((item, idx) => (
                            <DetailItemRenderer key={idx} item={item} formatMoney={formatMoney} />
                          ))}
                        </motion.div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Source note — simplified */}
              <div className="text-xs text-th-text-muted pt-3 mt-3 border-t border-th-border">
                {t('profil.see_full', lang)}{' '}
                {elu.liens?.hatvp && (
                  <a href={elu.liens?.hatvp} target="_blank" rel="noopener noreferrer" className="underline text-yellow-500">
                    {t('profil.fiche_hatvp', lang)}
                  </a>
                )}
              </div>
            </motion.div>
          )}

          {/* Observations du déclarant */}
          {elu.hatvp?.details_observations && (elu.hatvp.details_observations as Record<string, unknown>[]).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.17 }}
              className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
            >
              <h3 className="text-base sm:text-lg font-bold text-th-text mb-3 flex items-center gap-2">
                <FileText size={18} className="text-red-500" />
                Observations du déclarant
              </h3>
              {(elu.hatvp.details_observations as Record<string, unknown>[]).map((obs, idx) => (
                <p key={idx} className="text-sm text-th-text-secondary italic">
                  {String(obs.description || '')}
                </p>
              ))}
            </motion.div>
          )}
          {hasPatrimoineData && (
            <PortfolioChart
              immobilier={elu.immobilier || 0}
              placements={placementsMontant}
              patrimoine={elu.patrimoine || 0}
            />
          )}

          {/* Mandats et Fonctions — current and past */}
          {elu.mandats && elu.mandats.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
            >
              <h3 className="text-lg sm:text-xl font-bold text-th-text mb-4 flex items-center gap-2">
                <Briefcase size={20} className="text-red-500" />
                {t('profil.mandats', lang)}
              </h3>

              {/* Current vs past mandats */}
              {(() => {
                const { current: currentMandats, past: pastMandats } = categorizeMandats(
                  elu.mandats,
                  elu.fonction,
                  elu.hatvp?.details_mandats as { mandat?: string; organisme?: string; date_fin?: string }[] | undefined
                );

                return (
                  <>
                    {currentMandats.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-semibold text-green-400 mb-2">Actuels</h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                          {currentMandats.map((mandat, index) => (
                            <div
                              key={index}
                              className="flex items-center gap-3 p-3 bg-th-bg-secondary/60 rounded-lg"
                            >
                              <div className="w-2 h-2 bg-green-500 rounded-full flex-shrink-0" />
                              <span className="text-sm text-th-text-secondary">{mandat}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {pastMandats.length > 0 && (
                      <div>
                        <button
                          onClick={() => setShowPastMandats(!showPastMandats)}
                          className="flex items-center gap-2 text-sm font-semibold text-th-text-muted hover:text-th-text-secondary transition-colors mb-2"
                        >
                          {showPastMandats ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          Passés ({pastMandats.length})
                        </button>
                        {showPastMandats && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            transition={{ duration: 0.2 }}
                          >
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                              {pastMandats.map((mandat, index) => (
                                <div
                                  key={index}
                                  className="flex items-center gap-3 p-3 bg-th-bg-secondary/40 rounded-lg"
                                >
                                  <div className="w-2 h-2 bg-th-text-muted rounded-full flex-shrink-0" />
                                  <span className="text-sm text-th-text-muted">{mandat}</span>
                                </div>
                              ))}
                            </div>
                          </motion.div>
                        )}
                      </div>
                    )}
                  </>
                );
              })()}
            </motion.div>
          )}

          {/* Déclarations HATVP */}
          {elu.declarations_csv && elu.declarations_csv.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
              className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
            >
              <h3 className="text-lg sm:text-xl font-bold text-th-text mb-4 flex items-center gap-2">
                <FileText size={20} className="text-red-500" />
                Déclarations HATVP
              </h3>
              <div className="space-y-2 sm:space-y-3">
                {elu.declarations_csv.map((decl, index) => (
                  <div
                    key={index}
                    className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4 p-3 sm:p-4 bg-th-bg-secondary/60 rounded-lg"
                  >
                    <div className="flex-shrink-0">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold ${
                        decl.type.startsWith('DSP') 
                          ? 'bg-red-900/50 text-red-300' 
                          : 'bg-yellow-900/60 text-yellow-300'
                      }`}>
                        {decl.type}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-th-text">
                        {DOC_TYPE_LABELS[decl.type] || decl.type}
                      </p>
                      {decl.qualite && (
                        <p className="text-xs text-th-text-muted mt-0.5">
                          En qualité de : {decl.qualite}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-1">
                        {decl.date_publication && (
                          <span className="flex items-center gap-1 text-xs text-th-text-muted">
                            <Calendar size={12} />
                            Publiée le {formatDate(decl.date_publication)}
                          </span>
                        )}
                        {decl.date_depot && (
                          <span className="text-xs text-th-text-muted">
                            Déposée le {formatDate(decl.date_depot)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {elu.liens?.hatvp && (
                <div className="mt-4 pt-4 border-t">
                  <a
                    href={elu.liens?.hatvp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm text-red-500 hover:underline font-medium"
                  >
                    <Building2 size={16} />
                    Voir toutes les déclarations sur hatvp.fr
                    <ExternalLink size={14} />
                  </a>
                </div>
              )}
            </motion.div>
          )}

          {/* Source des données */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.5 }}
            className="bg-th-bg-secondary/60 rounded-xl p-4 text-xs text-th-text-muted"
          >
            <p className="font-medium text-th-text-muted mb-1">Sources des données</p>
            <p>
              Données issues de la{' '}
              <a href="https://www.hatvp.fr/open-data/" target="_blank" rel="noopener noreferrer" className="underline">
                Haute Autorité pour la Transparence de la Vie Publique (HATVP)
              </a>
              {' '}— Open Data.
              {elu.hatvp?.hatvp_scraped_at && (
                <> Dernière mise à jour : {formatDate(String(elu.hatvp.hatvp_scraped_at).split('T')[0])}.</>
              )}
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
