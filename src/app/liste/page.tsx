'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { useElus, loadElus } from '@/hooks/useElus';
import PersonCard from '@/components/PersonCard';
import SearchBar from '@/components/SearchBar';
import ListeStats from '@/components/ListeStats';
import { Loader2, ChevronLeft, ChevronRight, Database, Search } from 'lucide-react';
import { MandatFilter } from '@/lib/types';
import { useLang, t } from '@/lib/i18n';

// Cards per page — keeps DOM light on mobile and desktop
const PAGE_SIZE = 60;

export default function ListePage() {
  const { lang } = useLang();
  const { loading, getFiltered, searchTerm, mandatFilter, setMandatFilter, elus } = useElus();
  const filteredElus = getFiltered();
  const [page, setPage] = useState(0);

  useEffect(() => {
    loadElus();
  }, []);

  // Reset to first page whenever filters/search change
  useEffect(() => {
    setPage(0);
  }, [searchTerm, mandatFilter]);

  const totalCount = filteredElus.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);

  const displayedElus = useMemo(
    () => filteredElus.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE),
    [filteredElus, currentPage],
  );

  const goToPage = useCallback((p: number) => {
    setPage(p);
    window.scrollTo({ top: 0, behavior: 'smooth' });
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

      {/* D3 interactive stats */}
      {elus.length > 0 && (
        <ListeStats
          elus={elus}
          mandatFilter={mandatFilter}
          onMandatFilter={(f: MandatFilter) => setMandatFilter(f)}
        />
      )}

      {/* Galerie */}
      {displayedElus.length > 0 ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
            {displayedElus.map((elu, index) => (
              <PersonCard key={elu.id} elu={elu} index={index} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <nav
              aria-label="Pagination"
              className="flex items-center justify-center gap-2 mt-10"
            >
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 0}
                aria-label={lang === 'fr' ? 'Page précédente' : 'Previous page'}
                className="p-2 rounded-lg border border-th-border bg-th-card text-th-text-secondary hover:bg-th-bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft size={18} />
              </button>

              {/* Page numbers — show up to 5 around current */}
              {Array.from({ length: totalPages }, (_, i) => i)
                .filter(i => i === 0 || i === totalPages - 1 || Math.abs(i - currentPage) <= 2)
                .reduce<(number | 'ellipsis')[]>((acc, i, idx, arr) => {
                  if (idx > 0) {
                    const prev = arr[idx - 1] as number;
                    if (i - prev > 1) acc.push('ellipsis');
                  }
                  acc.push(i);
                  return acc;
                }, [])
                .map((item, idx) =>
                  item === 'ellipsis' ? (
                    <span key={`e${idx}`} className="px-1 text-th-text-muted" aria-hidden="true">…</span>
                  ) : (
                    <button
                      key={item}
                      onClick={() => goToPage(item)}
                      aria-current={item === currentPage ? 'page' : undefined}
                      className={`min-w-[2.25rem] h-9 rounded-lg text-sm font-medium transition-colors ${
                        item === currentPage
                          ? 'bg-red-600 text-white'
                          : 'border border-th-border bg-th-card text-th-text-secondary hover:bg-th-bg-secondary'
                      }`}
                    >
                      {item + 1}
                    </button>
                  ),
                )}

              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage >= totalPages - 1}
                aria-label={lang === 'fr' ? 'Page suivante' : 'Next page'}
                className="p-2 rounded-lg border border-th-border bg-th-card text-th-text-secondary hover:bg-th-bg-secondary disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight size={18} />
              </button>
            </nav>
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
