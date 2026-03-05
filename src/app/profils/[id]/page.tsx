'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowLeft, ExternalLink, User, Briefcase, MapPin, Calendar, FileText, Scale, Building2, Landmark, Users, TrendingUp } from 'lucide-react';
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

// Labels pour les sections HATVP détaillées
const HATVP_SECTION_LABELS: Record<string, { label: string; icon: string }> = {
  nb_biens_immobiliers:            { label: 'Biens immobiliers',            icon: '🏠' },
  nb_parts_sci:                    { label: 'Parts de SCI',                 icon: '🏗️' },
  nb_comptes_bancaires:            { label: 'Comptes bancaires',            icon: '🏦' },
  nb_assurances_vie:               { label: 'Assurances vie',               icon: '🛡️' },
  nb_valeurs_bourse:               { label: 'Valeurs cotées',               icon: '📈' },
  nb_valeurs_non_bourse:           { label: 'Valeurs non cotées',           icon: '📊' },
  nb_instruments_financiers:       { label: 'Instruments financiers',       icon: '📈' },
  nb_participations_financieres:   { label: 'Participations financières',   icon: '🏢' },
  nb_fonds:                        { label: 'Fonds',                        icon: '💰' },
  nb_biens_divers:                 { label: 'Biens divers',                 icon: '🎨' },
  nb_autres_biens:                 { label: 'Autres biens',                 icon: '📦' },
  nb_biens_etrangers:              { label: 'Biens à l\'étranger',          icon: '🌍' },
  nb_vehicules:                    { label: 'Véhicules',                    icon: '🚗' },
  nb_biens_mobiliers_valeur:       { label: 'Biens mobiliers de valeur',    icon: '💎' },
  nb_dettes:                       { label: 'Dettes & emprunts',            icon: '📉' },
  nb_revenus:                      { label: 'Revenus',                      icon: '💶' },
  nb_evenements_majeurs:           { label: 'Événements majeurs',           icon: '⚡' },
  nb_activites_consultant:         { label: 'Activités de consultant',      icon: '🔍' },
  nb_activites_professionnelles:   { label: 'Activités professionnelles',   icon: '💼' },
  nb_activites_anterieures:        { label: 'Activités antérieures',        icon: '📋' },
  nb_mandats_electifs:             { label: 'Mandats électifs',             icon: '🗳️' },
  nb_participations_organes:       { label: 'Participations à des organes', icon: '🏛️' },
  nb_fonctions_benevoles:          { label: 'Fonctions bénévoles',          icon: '🤝' },
  nb_activites_conjoint:           { label: 'Activités du conjoint',        icon: '👥' },
  nb_activites_collaborateurs:     { label: 'Activités collaborateurs',     icon: '👤' },
  nb_autres_liens_interets:        { label: 'Autres liens d\'intérêts',     icon: '⚠️' },
  nb_autres_activites:             { label: 'Autres activités',             icon: '📝' },
  nb_fonctions_gouvernementales:   { label: 'Fonctions gouvernementales',   icon: '🏛️' },
  nb_fonctions_consultatives:      { label: 'Fonctions consultatives',      icon: '📋' },
  nb_participations_exploitant:    { label: 'Participations exploitant',    icon: '🏭' },
};

export default function ProfilPage() {
  const params = useParams();
  const router = useRouter();
  const [elu, setElu] = useState<Elu | null>(null);
  const [loading, setLoading] = useState(true);

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
          <div className="text-6xl mb-4">😕</div>
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
          label: HATVP_SECTION_LABELS[key]?.label || key.replace('nb_', '').replace(/_/g, ' '),
          icon: HATVP_SECTION_LABELS[key]?.icon || '📄',
          value: elu.hatvp?.[key.replace('nb_', 'valeur_') + '_euro'] as number | undefined,
        }))
    : [];

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

          {/* Détail patrimoine HATVP */}
          {hatvpSections.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 }}
              className="bg-white rounded-xl shadow-lg p-4 sm:p-6"
            >
              <h3 className="text-lg sm:text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <TrendingUp size={20} className="text-blue-600" />
                Détail des déclarations
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                {hatvpSections.map(({ key, count, label, icon, value }) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-base flex-shrink-0">{icon}</span>
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
