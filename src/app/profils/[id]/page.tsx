'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowLeft, ExternalLink, User, Briefcase, MapPin, Calendar, FileText, Scale, Building2, Landmark, Users, TrendingUp, Home, BarChart3, Wallet, Package, AlertTriangle, Receipt, ChevronDown, ChevronUp, Info } from 'lucide-react';
import { Elu } from '@/lib/types';
import PortfolioChart from '@/components/PortfolioChart';

// Mapping type_mandat → label lisible
const MANDAT_LABELS: Record<string, string> = {
  depute: 'Député(e)',
  senateur: 'Sénateur/Sénatrice',
  president: 'Président(e) de la République',
  gouvernement: 'Membre du Gouvernement',
  europe: 'Député(e) européen(ne)',
  region: 'Conseiller(ère) régional(e)',
  departement: 'Conseiller(ère) départemental(e)',
  commune: 'Élu(e) municipal(e)',
  epci: 'Élu(e) intercommunal(e)',
  ctsp: 'Élu(e) collectivité territoriale',
  autre: 'Autre mandat',
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
  nb_activites_conjoint:           { label: 'Activités du conjoint',        category: 'interets' },
  nb_activites_collaborateurs:     { label: 'Activités collaborateurs',     category: 'interets' },
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
          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Chargement du profil...</p>
        </div>
      </div>
    );
  }

  if (!elu) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center py-16">
          <User size={64} className="text-gray-300 mx-auto mb-4" />
          <h3 className="text-2xl font-bold text-gray-900 mb-2">
            Élu non trouvé
          </h3>
          <button
            onClick={() => router.push('/')}
            className="mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
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
      return new Date(dateStr).toLocaleDateString('fr-FR', {
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
        onClick={() => router.push('/')}
        className="flex items-center gap-2 text-gray-600 hover:text-blue-600 mb-6 sm:mb-8 transition-colors"
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
          <div className="bg-white rounded-xl shadow-lg overflow-hidden sticky top-20 sm:top-24">
            {/* Photo — affichée en entier */}
            <div className="relative aspect-[3/4] max-h-80 sm:max-h-96 bg-gradient-to-br from-blue-100 to-green-100">
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
                  <User size={100} className="text-gray-300" />
                </div>
              )}
            </div>

            {/* Infos de base */}
            <div className="p-4 sm:p-6">
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2">
                {elu.prenom} {elu.nom}
              </h1>
              
              <div className="space-y-2.5 sm:space-y-3 mb-4 sm:mb-6">
                <div className="flex items-start gap-2 sm:gap-3">
                  <Briefcase size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs text-gray-500">Fonction</p>
                    <p className="font-semibold text-gray-900 text-sm sm:text-base">{elu.fonction}</p>
                  </div>
                </div>
                
                {elu.region && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <MapPin size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">Département</p>
                      <p className="font-semibold text-gray-900 text-sm sm:text-base">{elu.region}</p>
                    </div>
                  </div>
                )}

                {elu.groupe && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Users size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">Groupe politique</p>
                      <p className="font-semibold text-gray-900 text-sm sm:text-base">{elu.groupe}</p>
                    </div>
                  </div>
                )}

                {elu.parti && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Building2 size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">Parti</p>
                      <p className="font-semibold text-gray-900 text-sm sm:text-base">{elu.parti}</p>
                    </div>
                  </div>
                )}

                {elu.types_mandat && elu.types_mandat.length > 0 && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <Landmark size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-gray-500">Type de mandat</p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {elu.types_mandat.map((tm) => (
                          <span
                            key={tm}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700"
                          >
                            {MANDAT_LABELS[tm] || tm}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {nbDeclarations > 0 && (
                  <div className="flex items-start gap-2 sm:gap-3">
                    <FileText size={18} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500">Déclarations HATVP</p>
                      <p className="font-semibold text-gray-900 text-sm sm:text-base">{nbDeclarations} déclaration(s)</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Liens externes */}
              {(elu.liens.assemblee || elu.liens.hatvp || elu.liens.senat || elu.liens.wikipedia) && (
                <div className="border-t pt-4">
                  <p className="text-sm font-semibold text-gray-700 mb-3">
                    Sources & Liens
                  </p>
                  <div className="space-y-2">
                    {elu.liens.hatvp && (
                      <a
                        href={elu.liens.hatvp}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
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
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
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
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
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
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
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
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-4 sm:p-6 text-white">
                <p className="text-blue-100 text-xs sm:text-sm font-medium mb-1 sm:mb-2">
                  Patrimoine Total
                </p>
                <p className="text-xl sm:text-3xl font-bold mb-0.5 sm:mb-1">
                  {formatMoney(elu.patrimoine || 0)}
                </p>
                <p className="text-blue-100 text-[10px] sm:text-xs">
                  Déclaré à la HATVP
                </p>
              </div>

              <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl shadow-lg p-4 sm:p-6 text-white">
                <p className="text-green-100 text-xs sm:text-sm font-medium mb-1 sm:mb-2">
                  Revenus Annuels
                </p>
                <p className="text-xl sm:text-3xl font-bold mb-0.5 sm:mb-1">
                  {formatMoney(elu.revenus || 0)}
                </p>
                <p className="text-green-100 text-[10px] sm:text-xs">
                  Bruts déclarés
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
              className="bg-amber-50 border border-amber-200 rounded-xl p-4 sm:p-6"
            >
              <div className="flex items-start gap-3">
                <Scale size={22} className="text-amber-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="text-base sm:text-lg font-semibold text-amber-900 mb-1">
                    Données financières non disponibles
                  </h3>
                  <p className="text-xs sm:text-sm text-amber-700">
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
              className="bg-white rounded-xl shadow-lg p-4 sm:p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
                  <TrendingUp size={20} className="text-blue-600" />
                  Synthèse des déclarations
                </h3>
                <button
                  onClick={() => setShowDetails(!showDetails)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
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
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                      <span className="text-sm text-gray-700 truncate">{label}</span>
                    </div>
                    <div className="text-right flex-shrink-0 ml-2">
                      <span className="text-sm font-bold text-gray-900">{count}</span>
                      {value != null && value > 0 && (
                        <p className="text-xs text-gray-500">{formatMoney(value)}</p>
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
                      <h4 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2 border-b pb-2">
                        <Wallet size={16} className="text-blue-600" />
                        Ventilation du patrimoine
                      </h4>

                      {/* Totaux patrimoine */}
                      {(totalActifBrut > 0 || patrimoineNet > 0) && (
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                          {totalActifBrut > 0 && (
                            <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                              <p className="text-xs text-blue-600 font-medium">Actif brut total</p>
                              <p className="text-lg font-bold text-blue-900">{formatMoney(totalActifBrut)}</p>
                            </div>
                          )}
                          {totalDettes > 0 && (
                            <div className="p-3 bg-red-50 rounded-lg border border-red-100">
                              <p className="text-xs text-red-600 font-medium">Dettes et emprunts</p>
                              <p className="text-lg font-bold text-red-900">-{formatMoney(totalDettes)}</p>
                            </div>
                          )}
                          {patrimoineNet > 0 && (
                            <div className="p-3 bg-green-50 rounded-lg border border-green-100">
                              <p className="text-xs text-green-600 font-medium">Patrimoine net</p>
                              <p className="text-lg font-bold text-green-900">{formatMoney(patrimoineNet)}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Immobilier */}
                      {patrimoineSections.filter(s => s.key === 'nb_biens_immobiliers' || s.key === 'nb_parts_sci' || s.key === 'nb_biens_etrangers').length > 0 && (
                        <div className="mb-4">
                          <h5 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                            <Home size={14} className="text-blue-500" />
                            Immobilier et foncier
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => ['nb_biens_immobiliers', 'nb_parts_sci', 'nb_biens_etrangers'].includes(s.key))
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg text-sm">
                                  <span className="text-gray-700">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-gray-900">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-gray-500">({formatMoney(value)})</span>
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
                          <h5 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
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
                                <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg text-sm">
                                  <span className="text-gray-700">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-gray-900">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-gray-500">({formatMoney(value)})</span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            {placementsMontant > 0 && (
                              <div className="flex items-center justify-between p-2.5 bg-green-50 rounded-lg text-sm border border-green-100">
                                <span className="text-green-700 font-medium">Total placements</span>
                                <span className="font-bold text-green-900">{formatMoney(placementsMontant)}</span>
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
                          <h5 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
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
                                <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg text-sm">
                                  <span className="text-gray-700">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-gray-900">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-gray-500">({formatMoney(value)})</span>
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
                          <h5 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                            <AlertTriangle size={14} className="text-red-500" />
                            Passif
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => s.key === 'nb_dettes')
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-red-50 rounded-lg text-sm border border-red-100">
                                  <span className="text-red-700">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-red-900">{count} élément{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-red-600">({formatMoney(value)})</span>
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
                          <h5 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-1.5">
                            <Receipt size={14} className="text-green-500" />
                            Revenus déclarés
                          </h5>
                          <div className="space-y-2">
                            {patrimoineSections
                              .filter(s => s.key === 'nb_revenus')
                              .map(({ key, count, label, value }) => (
                                <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg text-sm">
                                  <span className="text-gray-700">{label}</span>
                                  <div className="text-right">
                                    <span className="font-semibold text-gray-900">{count} source{count > 1 ? 's' : ''}</span>
                                    {value != null && value > 0 && (
                                      <span className="ml-2 text-xs text-gray-500">({formatMoney(value)})</span>
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
                      <h4 className="text-base font-semibold text-gray-800 mb-3 flex items-center gap-2 border-b pb-2">
                        <Briefcase size={16} className="text-blue-600" />
                        Intérêts et activités déclarés
                      </h4>
                      <div className="space-y-2">
                        {interetsSections.map(({ key, count, label }) => (
                          <div key={key} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg text-sm">
                            <span className="text-gray-700">{label}</span>
                            <span className="font-semibold text-gray-900">{count} élément{count > 1 ? 's' : ''}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Note source */}
                  <div className="text-xs text-gray-400 pt-2 border-t">
                    Données agrégées à partir des déclarations HATVP disponibles pour cet élu.
                    {elu.liens.hatvp && (
                      <>
                        {' '}Pour consulter le détail complet :{' '}
                        <a href={elu.liens.hatvp} target="_blank" rel="noopener noreferrer" className="underline text-blue-500">
                          fiche HATVP
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
              className="bg-white rounded-xl shadow-lg p-4 sm:p-6"
            >
              <h3 className="text-lg sm:text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <Briefcase size={20} className="text-blue-600" />
                Mandats et Fonctions
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                {elu.mandats.map((mandat, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="w-2 h-2 bg-blue-600 rounded-full flex-shrink-0" />
                    <span className="text-sm text-gray-700">{mandat}</span>
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
              className="bg-white rounded-xl shadow-lg p-4 sm:p-6"
            >
              <h3 className="text-lg sm:text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <FileText size={20} className="text-blue-600" />
                Déclarations HATVP
              </h3>
              <div className="space-y-2 sm:space-y-3">
                {elu.declarations_csv.map((decl, index) => (
                  <div
                    key={index}
                    className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4 p-3 sm:p-4 bg-gray-50 rounded-lg"
                  >
                    <div className="flex-shrink-0">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold ${
                        decl.type.startsWith('DSP') 
                          ? 'bg-blue-100 text-blue-800' 
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {decl.type}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900">
                        {DOC_TYPE_LABELS[decl.type] || decl.type}
                      </p>
                      {decl.qualite && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          En qualité de : {decl.qualite}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-1">
                        {decl.date_publication && (
                          <span className="flex items-center gap-1 text-xs text-gray-500">
                            <Calendar size={12} />
                            Publiée le {formatDate(decl.date_publication)}
                          </span>
                        )}
                        {decl.date_depot && (
                          <span className="text-xs text-gray-400">
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
                    className="inline-flex items-center gap-2 text-sm text-blue-600 hover:underline font-medium"
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
            className="bg-gray-50 rounded-xl p-4 text-xs text-gray-500"
          >
            <p className="font-medium text-gray-600 mb-1">Sources des données</p>
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
