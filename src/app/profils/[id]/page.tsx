'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowLeft, ExternalLink, User, Briefcase, MapPin, Calendar, FileText, Scale, Building2, Landmark, Users, TrendingUp, Home, BarChart3, Wallet, Package, AlertTriangle, Receipt, ChevronDown, ChevronUp, Info } from 'lucide-react';
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

export default function ProfilPage() {
  const params = useParams();
  const router = useRouter();
  const [elu, setElu] = useState<Elu | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(false);
  const { lang } = useLang();

  useEffect(() => {
    const fetchElu = async () => {
      try {
        const response = await fetch('/data/elus.json');
        const data: Elu[] = await response.json();
        const found = data.find((e) => e.id === params.id);
        setElu(found || null);
      } catch (error) {
        console.error('Erreur:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchElu();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-red-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-neutral-400">Chargement du profil...</p>
        </div>
      </div>
    );
  }

  if (!elu) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center py-16">
          <User size={64} className="text-neutral-600 mx-auto mb-4" />
          <h3 className="text-2xl font-bold text-white mb-2">
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

  const hasFinancialData = (elu.patrimoine || 0) > 0 || (elu.revenus || 0) > 0 || (elu.immobilier || 0) > 0;
  const placementsMontant = elu.placements_montant || (typeof elu.placements === 'number' ? elu.placements : 0);
  const photoSrc = elu.photo_url || (elu.photo !== '/photos/placeholder.jpg' ? elu.photo : '');
  const nbDeclarations = elu.hatvp?.nb_declarations_hatvp || elu.declarations_csv?.length || 0;

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

  // Séparer patrimoine et intérêts pour l'affichage détaillé
  const patrimoineSections = hatvpSections.filter((s) => s.category === 'patrimoine');
  const interetsSections = hatvpSections.filter((s) => s.category === 'interets');

  // Calculer des totaux pour l'affichage
  const totalActifBrut = elu.hatvp?.total_actif_brut_euro || 0;
  const totalDettes = elu.hatvp?.total_dettes_euro || 0;
  const patrimoineNet = elu.hatvp?.patrimoine_net_euro || 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-12">
      {/* Bouton retour */}
      <motion.button
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={() => router.push('/liste')}
        className="flex items-center gap-2 text-neutral-400 hover:text-red-500 mb-6 sm:mb-8 transition-colors"
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
          <div className="bg-neutral-800 rounded-xl shadow-lg overflow-hidden sticky top-20 sm:top-24 border-2 border-red-700">
            {/* Photo — affichée en entier */}
            <div className="relative aspect-[3/4] max-h-80 sm:max-h-96 bg-gradient-to-br from-red-900/40 to-neutral-800">
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
                  <User size={100} className="text-neutral-600" />
                </div>
              )}
            </div>

            {/* Infos de base */}
            <div className="p-4 sm:p-6">
              <h1 className="text-xl sm:text-2xl font-bold text-white mb-2">
                {elu.prenom} {elu.nom}
              </h1>
              
              <div className="space-y-2.5 sm:space-y-3 mb-4 sm:mb-6">
                <div className="flex items-start gap-2 sm:gap-3">
                  <Briefcase size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs text-neutral-500">Fonction</p>
                    <p className="font-semibold text-white text-sm sm:text-base">{elu.fonction}</p>
                  </div>
                </div>
                
                {elu.region && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <MapPin size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-neutral-500">Département</p>
                      <p className="font-semibold text-white text-sm sm:text-base">{elu.region}</p>
                    </div>
                  </div>
                )}

                {elu.groupe && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Users size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-neutral-500">Groupe politique</p>
                      <p className="font-semibold text-white text-sm sm:text-base">{elu.groupe}</p>
                    </div>
                  </div>
                )}

                {elu.parti && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Building2 size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-neutral-500">Parti</p>
                      <p className="font-semibold text-white text-sm sm:text-base">{elu.parti}</p>
                    </div>
                  </div>
                )}

                {elu.types_mandat && elu.types_mandat.length > 0 && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Landmark size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-neutral-500">Type de mandat</p>
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

                {nbDeclarations > 0 && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <FileText size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs text-neutral-500">Déclarations HATVP</p>
                      <p className="font-semibold text-white text-sm sm:text-base">{nbDeclarations} déclaration(s)</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Liens externes */}
              {(elu.liens.assemblee || elu.liens.hatvp || elu.liens.senat || elu.liens.wikipedia) && (
                <div className="border-t border-neutral-700 pt-4">
                  <p className="text-sm font-semibold text-neutral-300 mb-3">
                    Sources & Liens
                  </p>
                  <div className="space-y-2">
                    {elu.liens.hatvp && (
                      <a
                        href={elu.liens.hatvp}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Fiche HATVP
                      </a>
                    )}
                    {elu.liens.assemblee && (
                      <a
                        href={elu.liens.assemblee}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Assemblée Nationale
                      </a>
                    )}
                    {elu.liens.senat && (
                      <a
                        href={elu.liens.senat}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-red-500 hover:underline"
                      >
                        <ExternalLink size={14} />
                        Sénat
                      </a>
                    )}
                    {elu.liens.wikipedia && (
                      <a
                        href={elu.liens.wikipedia}
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
          {/* Stats Cards */}
          {hasFinancialData ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
              className="grid grid-cols-2 gap-3 sm:gap-6"
            >
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

              <div className="bg-gradient-to-br from-yellow-600 to-yellow-700 rounded-xl shadow-lg p-4 sm:p-6 text-white">
                <p className="text-yellow-100 text-xs sm:text-sm font-medium mb-1 sm:mb-2">
                  Revenus Annuels
                </p>
                <p className="text-xl sm:text-3xl font-bold mb-0.5 sm:mb-1">
                  {formatMoney(elu.revenus || 0)}
                </p>
                <p className="text-yellow-100 text-[10px] sm:text-xs">
                  Bruts déclarés
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
              className="bg-yellow-900/30 border border-yellow-700 rounded-xl p-4 sm:p-6"
            >
              <div className="flex items-start gap-3">
                <Scale size={22} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="text-base sm:text-lg font-semibold text-yellow-300 mb-1">
                    Données financières non disponibles
                  </h3>
                  <p className="text-xs sm:text-sm text-yellow-200/80">
                    Les données patrimoniales et de revenus ne sont pas encore disponibles pour cet élu.
                    {elu.liens.hatvp && (
                      <>
                        {' '}Consultez la{' '}
                        <a href={elu.liens.hatvp} target="_blank" rel="noopener noreferrer" className="underline font-medium">
                          fiche HATVP
                        </a>
                        {' '}pour plus d&apos;informations.
                      </>
                    )}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Detail patrimoine HATVP */}
          {hatvpSections.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 }}
              className="bg-neutral-800 rounded-xl shadow-lg p-4 sm:p-6 border border-neutral-700"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg sm:text-xl font-bold text-white flex items-center gap-2">
                  <TrendingUp size={20} className="text-red-500" />
                  Synthèse des déclarations
                </h3>
                <button
                  onClick={() => setShowDetails(!showDetails)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-500 bg-red-900/30 rounded-lg hover:bg-red-900/50 transition-colors"
                >
                  <Info size={14} />
                  {showDetails ? 'Masquer les détails' : 'Voir les détails'}
                  {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>

              {/* Vue resumee (toujours visible) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                {hatvpSections.map(({ key, count, label, value }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 bg-neutral-900/60 rounded-lg"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-2 h-2 rounded-full bg-red-900/300 flex-shrink-0" />
                      <span className="text-sm text-neutral-300 truncate">{label}</span>
                    </div>
                    <div className="text-right flex-shrink-0 ml-2">
                      <span className="text-sm font-bold text-white">{count}</span>
                      {value != null && value > 0 && (
                        <p className="text-xs text-neutral-500">{formatMoney(value)}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Vue détaillée (expandable) */}
              {showDetails && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  transition={{ duration: 0.3 }}
                  className="mt-6 space-y-6"
                >
                  {/* Ventilation du patrimoine */}
                  {patrimoineSections.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b pb-2">
                        <Wallet size={16} className="text-red-500" />
                        Ventilation du patrimoine
                      </h4>

                      {/* Totaux patrimoine */}
                      {(totalActifBrut > 0 || patrimoineNet > 0) && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                          {totalActifBrut > 0 && (
                            <div className="p-3 bg-red-900/30 rounded-lg border border-red-800">
                              <p className="text-xs text-red-500 font-medium">Actif brut total</p>
                              <p className="text-lg font-bold text-red-200">{formatMoney(totalActifBrut)}</p>
                            </div>
                          )}
                          {totalDettes > 0 && (
                            <div className="p-3 bg-yellow-900/30 rounded-lg border border-yellow-800">
                              <p className="text-xs text-yellow-400 font-medium">Dettes et emprunts</p>
                              <p className="text-lg font-bold text-yellow-200">-{formatMoney(totalDettes)}</p>
                            </div>
                          )}
                          {patrimoineNet > 0 && (
                            <div className="p-3 bg-neutral-700/50 rounded-lg border border-neutral-600">
                              <p className="text-xs text-neutral-400 font-medium">Patrimoine net</p>
                              <p className="text-lg font-bold text-white">{formatMoney(patrimoineNet)}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Immobilier */}
                      {patrimoineSections.filter(s => s.key === 'nb_biens_immobiliers' || s.key === 'nb_parts_sci' || s.key === 'nb_biens_etrangers').length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-neutral-300 mb-2 flex items-center gap-1.5">
                            <Home size={14} className="text-red-400" />
                            Immobilier et foncier
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => ['nb_biens_immobiliers', 'nb_parts_sci', 'nb_biens_etrangers'].includes(s.key))
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-neutral-900/60 rounded-lg text-sm">
                                  <span className="text-neutral-300">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-white">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-neutral-500">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* Placements et investissements */}
                      {patrimoineSections.filter(s =>
                        ['nb_comptes_bancaires', 'nb_assurances_vie', 'nb_valeurs_bourse',
                         'nb_valeurs_non_bourse', 'nb_instruments_financiers',
                         'nb_participations_financieres', 'nb_fonds'].includes(s.key)
                      ).length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-neutral-300 mb-2 flex items-center gap-1.5">
                            <BarChart3 size={14} className="text-green-500" />
                            Placements et investissements
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s =>
                                ['nb_comptes_bancaires', 'nb_assurances_vie', 'nb_valeurs_bourse',
                                 'nb_valeurs_non_bourse', 'nb_instruments_financiers',
                                 'nb_participations_financieres', 'nb_fonds'].includes(s.key)
                              )
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-neutral-900/60 rounded-lg text-sm">
                                  <span className="text-neutral-300">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-white">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-neutral-500">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            {placementsMontant > 0 && (
                              <div className="flex items-center justify-between p-2.5 bg-neutral-700/50 rounded-lg text-sm border border-neutral-600">
                                <span className="text-yellow-300 font-medium">Total placements</span>
                                <span className="font-bold text-white">{formatMoney(placementsMontant)}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Autres biens */}
                      {patrimoineSections.filter(s =>
                        ['nb_biens_divers', 'nb_autres_biens', 'nb_vehicules',
                         'nb_biens_mobiliers_valeur'].includes(s.key)
                      ).length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-neutral-300 mb-2 flex items-center gap-1.5">
                            <Package size={14} className="text-orange-500" />
                            Autres biens
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s =>
                                ['nb_biens_divers', 'nb_autres_biens', 'nb_vehicules',
                                 'nb_biens_mobiliers_valeur'].includes(s.key)
                              )
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-neutral-900/60 rounded-lg text-sm">
                                  <span className="text-neutral-300">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-white">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-neutral-500">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* Dettes */}
                      {patrimoineSections.filter(s => s.key === 'nb_dettes').length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-neutral-300 mb-2 flex items-center gap-1.5">
                            <AlertTriangle size={14} className="text-red-500" />
                            Passif
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => s.key === 'nb_dettes')
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-yellow-900/30 rounded-lg text-sm border border-yellow-800">
                                  <span className="text-yellow-300">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-yellow-200">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-yellow-400">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* Revenus déclarés */}
                      {patrimoineSections.filter(s => s.key === 'nb_revenus').length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-neutral-300 mb-2 flex items-center gap-1.5">
                            <Receipt size={14} className="text-green-500" />
                            Revenus déclarés
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => s.key === 'nb_revenus')
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-neutral-900/60 rounded-lg text-sm">
                                  <span className="text-neutral-300">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-white">{count} source{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-neutral-500">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Declarations d'interets */}
                  {interetsSections.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b pb-2">
                        <Briefcase size={16} className="text-red-500" />
                        Intérêts et activités déclarés
                      </h4>
                      <div className="space-y-2">
                        {interetsSections.map(({ key, count, label }) => (
                          <div key={key} className="flex items-center justify-between p-2.5 bg-neutral-900/60 rounded-lg text-sm">
                            <span className="text-neutral-300">{label}</span>
                            <span className="font-semibold text-white">{count} élément{count > 1 ? 's' : ''}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Détails activités (entreprises, rémunérations) */}
                  {elu.hatvp?.details_activites && elu.hatvp.details_activites.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b border-neutral-700 pb-2">
                        <Briefcase size={16} className="text-yellow-400" />
                        {lang === 'fr' ? 'Détail des activités et entreprises' : 'Activities & Companies Detail'}
                      </h4>
                      <div className="space-y-2">
                        {elu.hatvp.details_activites.map((act, idx) => (
                          <div key={idx} className="p-2.5 bg-neutral-900/60 rounded-lg text-sm border border-neutral-700">
                            {act.denomination && <p className="text-white font-medium">{act.denomination}</p>}
                            {act.fonction && <p className="text-neutral-400 text-xs mt-0.5">{act.fonction}</p>}
                            {act.remuneration && <p className="text-yellow-400 text-xs mt-0.5 font-semibold">{act.remuneration}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Détails mandats (organismes, rémunérations) */}
                  {elu.hatvp?.details_mandats && elu.hatvp.details_mandats.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b border-neutral-700 pb-2">
                        <Landmark size={16} className="text-red-400" />
                        {lang === 'fr' ? 'Détail des mandats et rémunérations' : 'Mandate & Salary Detail'}
                      </h4>
                      <div className="space-y-2">
                        {elu.hatvp.details_mandats.map((m, idx) => (
                          <div key={idx} className="p-2.5 bg-neutral-900/60 rounded-lg text-sm border border-neutral-700">
                            {m.mandat && <p className="text-white font-medium">{m.mandat}</p>}
                            {m.organisme && <p className="text-neutral-400 text-xs mt-0.5">{m.organisme}</p>}
                            {m.remuneration && <p className="text-yellow-400 text-xs mt-0.5 font-semibold">{m.remuneration}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Détails participations (sociétés, types) */}
                  {elu.hatvp?.details_participations && elu.hatvp.details_participations.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b border-neutral-700 pb-2">
                        <Building2 size={16} className="text-neutral-300" />
                        {lang === 'fr' ? 'Détail des participations et sociétés' : 'Participations & Companies Detail'}
                      </h4>
                      <div className="space-y-2">
                        {elu.hatvp.details_participations.map((p, idx) => (
                          <div key={idx} className="p-2.5 bg-neutral-900/60 rounded-lg text-sm border border-neutral-700">
                            {p.denomination && <p className="text-white font-medium">{p.denomination}</p>}
                            {p.type && <p className="text-neutral-400 text-xs mt-0.5">{p.type}</p>}
                            {p.valeur && <p className="text-yellow-400 text-xs mt-0.5 font-semibold">{p.valeur}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Détails revenus (types, organismes, montants) */}
                  {elu.hatvp?.details_revenus && elu.hatvp.details_revenus.length > 0 && (
                    <div>
                      <h4 className="text-base font-semibold text-neutral-200 mb-3 flex items-center gap-2 border-b border-neutral-700 pb-2">
                        <Receipt size={16} className="text-yellow-400" />
                        {lang === 'fr' ? 'Détail des revenus par source' : 'Income Detail by Source'}
                      </h4>
                      <div className="space-y-2">
                        {elu.hatvp.details_revenus.map((r, idx) => (
                          <div key={idx} className="p-2.5 bg-neutral-900/60 rounded-lg text-sm border border-neutral-700">
                            {r.type && <p className="text-white font-medium">{r.type}</p>}
                            {r.organisme && <p className="text-neutral-400 text-xs mt-0.5">{r.organisme}</p>}
                            {r.montant && <p className="text-yellow-400 text-xs mt-0.5 font-semibold">{r.montant}</p>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Note source */}
                  <div className="text-xs text-neutral-500 pt-2 border-t border-neutral-700">
                    {t('profil.note_source', lang)}
                    {elu.liens.hatvp && (
                      <>
                        {' '}{t('profil.see_full', lang)}{' '}
                        <a href={elu.liens.hatvp} target="_blank" rel="noopener noreferrer" className="underline text-yellow-400">
                          {t('profil.fiche_hatvp', lang)}
                        </a>
                      </>
                    )}
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Graphique - seulement si données financières */}
          {hasFinancialData && (
            <PortfolioChart
              immobilier={elu.immobilier || 0}
              placements={placementsMontant}
              patrimoine={elu.patrimoine || 0}
            />
          )}

          {/* Mandats */}
          {elu.mandats && elu.mandats.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="bg-neutral-800 rounded-xl shadow-lg p-4 sm:p-6 border border-neutral-700"
            >
              <h3 className="text-lg sm:text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Briefcase size={20} className="text-red-500" />
                Mandats et Fonctions
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                {elu.mandats.map((mandat, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 bg-neutral-900/60 rounded-lg"
                  >
                    <div className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0" />
                    <span className="text-sm text-neutral-300">{mandat}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Déclarations HATVP */}
          {elu.declarations_csv && elu.declarations_csv.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
              className="bg-neutral-800 rounded-xl shadow-lg p-4 sm:p-6 border border-neutral-700"
            >
              <h3 className="text-lg sm:text-xl font-bold text-white mb-4 flex items-center gap-2">
                <FileText size={20} className="text-red-500" />
                Déclarations HATVP
              </h3>
              <div className="space-y-2 sm:space-y-3">
                {elu.declarations_csv.map((decl, index) => (
                  <div
                    key={index}
                    className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4 p-3 sm:p-4 bg-neutral-900/60 rounded-lg"
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
                      <p className="text-sm font-medium text-white">
                        {DOC_TYPE_LABELS[decl.type] || decl.type}
                      </p>
                      {decl.qualite && (
                        <p className="text-xs text-neutral-500 mt-0.5">
                          En qualité de : {decl.qualite}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-1">
                        {decl.date_publication && (
                          <span className="flex items-center gap-1 text-xs text-neutral-500">
                            <Calendar size={12} />
                            Publiée le {formatDate(decl.date_publication)}
                          </span>
                        )}
                        {decl.date_depot && (
                          <span className="text-xs text-neutral-500">
                            Déposée le {formatDate(decl.date_depot)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {elu.liens.hatvp && (
                <div className="mt-4 pt-4 border-t">
                  <a
                    href={elu.liens.hatvp}
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
            className="bg-neutral-900/60 rounded-xl p-4 text-xs text-neutral-500"
          >
            <p className="font-medium text-neutral-400 mb-1">Sources des données</p>
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
