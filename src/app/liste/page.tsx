'use client';

import { useEffect, useState } from 'react';
import { useElus, loadElus } from '@/hooks/useElus';
import PersonCard from '@/components/PersonCard';
import SearchBar from '@/components/SearchBar';
import { Loader2, ChevronDown, Users, Database, Search } from 'lucide-react';
import { Elu } from '@/lib/types';
import { useLang, t } from '@/lib/i18n';

// Nombre de fiches "vedettes" affichées par défaut
const FEATURED_COUNT = 12;

/**
 * Sélectionner les profils les plus complets pour la page d'accueil.
 * Critères : données financières, nombre de déclarations, photo disponible.
 */
function selectFeatured(elus: Elu[]): Elu[] {
  const scored = elus.map((elu) => {
    let score = 0;
    if ((elu.patrimoine || 0) > 0) score += 50;
    if ((elu.revenus || 0) > 0) score += 30;
    if ((elu.immobilier || 0) > 0) score += 10;
    if (elu.photo_url) score += 15;
    if (elu.photo && elu.photo !== '/photos/placeholder.jpg') score += 15;
    if (elu.declarations_csv && elu.declarations_csv.length > 0) score += elu.declarations_csv.length * 3;
    if (elu.hatvp?.nb_declarations_hatvp) score += elu.hatvp.nb_declarations_hatvp * 2;
    if (elu.mandats && elu.mandats.length > 1) score += 5;
    // Bonus pour mandats nationaux
    const nationalTypes = ['depute', 'senateur', 'president', 'gouvernement', 'europe'];
    if (elu.types_mandat?.some((tp) => nationalTypes.includes(tp))) score += 20;
    return { elu, score };
  });

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, FEATURED_COUNT).map((s) => s.elu);
}

export default function ListePage() {
  const { lang } = useLang();
  const { loading, getFiltered, searchTerm } = useElus();
  const filteredElus = getFiltered();
  const [showAll, setShowAll] = useState(true);

  useEffect(() => {
    loadElus();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-red-500 mx-auto mb-4" />
          <p className="text-th-text-muted">{t('loading', lang)}</p>
        </div>
      </div>
    );
  }

  // Si recherche active ou "voir tout", afficher tous les résultats
  const isSearching = searchTerm.length > 0;
  const displayedElus = (isSearching || showAll)
    ? filteredElus
    : selectFeatured(filteredElus);

  const totalCount = filteredElus.length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h2 className="text-4xl sm:text-5xl font-black text-th-text mb-4 tracking-tight">
          {t('landing.title', lang)}
        </h2>
        <p className="text-lg text-th-text-secondary max-w-3xl mx-auto">
          {t('landing.subtitle', lang)}
        </p>
        <div className="flex items-center justify-center gap-6 mt-6 text-sm text-th-text-muted">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-red-500" />
            <span>{totalCount.toLocaleString('fr-FR')} {t('landing.counted', lang)}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
            <span>{t('landing.official', lang)}</span>
          </div>
        </div>
      </div>

      {/* SearchBar */}
      <SearchBar />

      {/* Section titre */}
      {!isSearching && !showAll && (
        <div className="flex items-center gap-3 mb-6">
          <Users className="w-5 h-5 text-red-500" />
          <h3 className="text-lg font-semibold text-th-text-secondary">
            {t('landing.featured', lang)}
          </h3>
          <span className="text-sm text-th-text-muted">
            {t('landing.featured.sub', lang)}
          </span>
        </div>
      )}

      {/* Galerie */}
      {displayedElus.length > 0 ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
            {displayedElus.map((elu, index) => (
              <PersonCard key={elu.id} elu={elu} index={index} />
            ))}
          </div>

          {/* Bouton "Voir la base complète" */}
          {!isSearching && !showAll && totalCount > FEATURED_COUNT && (
            <div className="text-center mt-12">
              <button
                onClick={() => setShowAll(true)}
                className="inline-flex items-center gap-3 px-8 py-4 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors shadow-lg hover:shadow-xl font-bold text-lg"
              >
                <Database className="w-5 h-5" />
                {t('landing.see_all', lang)} ({totalCount.toLocaleString('fr-FR')} {t('landing.counted', lang)})
                <ChevronDown className="w-5 h-5" />
              </button>
              <p className="text-sm text-th-text-muted mt-3">
                {t('landing.see_all.sub', lang)}
              </p>
            </div>
          )}

          {/* Bouton retour aux vedettes */}
          {!isSearching && showAll && (
            <div className="text-center mt-8">
              <button
                onClick={() => {
                  setShowAll(false);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                className="inline-flex items-center gap-2 px-6 py-3 bg-th-card text-th-text-secondary rounded-lg hover:bg-th-bg-secondary transition-colors border border-th-border"
              >
                {t('landing.back_featured', lang)}
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-16">
          <Search className="w-16 h-16 text-th-text-muted mx-auto mb-4" />
          <h3 className="text-2xl font-bold text-th-text mb-2">
            {t('landing.no_result', lang)}
          </h3>
          <p className="text-th-text-muted">
            {t('landing.no_result.sub', lang)}
          </p>
        </div>
      )}
    </div>
  );
}
