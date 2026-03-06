'use client';

import { Search, ImageOff, Image as ImageIcon } from 'lucide-react';
import { useElus } from '@/hooks/useElus';
import { SortBy, MandatFilter } from '@/lib/types';
import { useLang, t } from '@/lib/i18n';

const MANDAT_KEYS: { value: MandatFilter; i18nKey: string }[] = [
  { value: '', i18nKey: 'mandat.all' },
  { value: 'depute', i18nKey: 'mandat.depute' },
  { value: 'senateur', i18nKey: 'mandat.senateur' },
  { value: 'president', i18nKey: 'mandat.president' },
  { value: 'gouvernement', i18nKey: 'mandat.gouvernement' },
  { value: 'europe', i18nKey: 'mandat.europe' },
  { value: 'region', i18nKey: 'mandat.region' },
  { value: 'departement', i18nKey: 'mandat.departement' },
  { value: 'commune', i18nKey: 'mandat.commune' },
  { value: 'epci', i18nKey: 'mandat.epci' },
  { value: 'ctsp', i18nKey: 'mandat.ctsp' },
  { value: 'autre', i18nKey: 'mandat.autre' },
];

export default function SearchBar() {
  const { searchTerm, setSearchTerm, sortBy, setSortBy, mandatFilter, setMandatFilter, showPhotos, setShowPhotos } = useElus();
  const { lang } = useLang();

  return (
    <div className="flex flex-col gap-4 mb-8">
      {/* Ligne principale : recherche + tri */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-neutral-500" size={20} />
          <input
            type="text"
            placeholder={t('search.placeholder', lang)}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 border-2 border-neutral-600 bg-neutral-800 text-white rounded-lg focus:border-red-500 focus:outline-none transition-colors placeholder:text-neutral-500"
          />
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
          className="px-6 py-3 border-2 border-neutral-600 rounded-lg focus:border-red-500 focus:outline-none cursor-pointer bg-neutral-800 text-white transition-colors"
        >
          <option value="nom">{t('search.sort.nom', lang)}</option>
          <option value="patrimoine">{t('search.sort.patrimoine', lang)}</option>
          <option value="revenus">{t('search.sort.revenus', lang)}</option>
        </select>
      </div>

      {/* Ligne secondaire : filtre mandat + toggle photos */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        <select
          value={mandatFilter}
          onChange={(e) => setMandatFilter(e.target.value as MandatFilter)}
          className="px-4 py-2 border-2 border-neutral-600 rounded-lg focus:border-red-500 focus:outline-none cursor-pointer bg-neutral-800 text-white transition-colors text-sm"
        >
          {MANDAT_KEYS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {t(opt.i18nKey, lang)}
            </option>
          ))}
        </select>

        <button
          onClick={() => setShowPhotos(!showPhotos)}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border-2 text-sm font-medium transition-colors ${
            showPhotos
              ? 'border-red-500 bg-red-900/40 text-red-300'
              : 'border-neutral-600 bg-neutral-800 text-neutral-400 hover:border-neutral-500'
          }`}
        >
          {showPhotos ? <ImageIcon size={16} /> : <ImageOff size={16} />}
          {showPhotos ? t('search.photos.on', lang) : t('search.photos.off', lang)}
        </button>
      </div>
    </div>
  );
}
