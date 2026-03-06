'use client';

import { Search, ImageOff, Image as ImageIcon } from 'lucide-react';
import { useElus } from '@/hooks/useElus';
import { SortBy, MandatFilter } from '@/lib/types';

const MANDAT_OPTIONS: { value: MandatFilter; label: string }[] = [
  { value: '', label: 'Tous les mandats' },
  { value: 'depute', label: 'Député(e)s' },
  { value: 'senateur', label: 'Sénateurs/Sénatrices' },
  { value: 'president', label: 'Président(e) de la République' },
  { value: 'gouvernement', label: 'Gouvernement' },
  { value: 'europe', label: 'Député(e)s européens' },
  { value: 'region', label: 'Conseillers régionaux' },
  { value: 'departement', label: 'Conseillers départementaux' },
  { value: 'commune', label: 'Élus municipaux' },
  { value: 'epci', label: 'Élus intercommunaux' },
  { value: 'ctsp', label: 'Collectivités territoriales' },
  { value: 'autre', label: 'Autres mandats' },
];

export default function SearchBar() {
  const { searchTerm, setSearchTerm, sortBy, setSortBy, mandatFilter, setMandatFilter, showPhotos, setShowPhotos } = useElus();

  return (
    <div className="flex flex-col gap-4 mb-8">
      {/* Ligne principale : recherche + tri */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Rechercher un élu (nom, fonction, région...)"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-12 pr-4 py-3 border-2 border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none transition-colors"
          />
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
          className="px-6 py-3 border-2 border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none cursor-pointer bg-white transition-colors"
        >
          <option value="nom">Trier par Nom</option>
          <option value="patrimoine">Trier par Patrimoine</option>
          <option value="revenus">Trier par Revenus</option>
        </select>
      </div>

      {/* Ligne secondaire : filtre mandat + toggle photos */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        <select
          value={mandatFilter}
          onChange={(e) => setMandatFilter(e.target.value as MandatFilter)}
          className="px-4 py-2 border-2 border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none cursor-pointer bg-white transition-colors text-sm"
        >
          {MANDAT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <button
          onClick={() => setShowPhotos(!showPhotos)}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border-2 text-sm font-medium transition-colors ${
            showPhotos
              ? 'border-blue-500 bg-blue-50 text-blue-700'
              : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
          }`}
        >
          {showPhotos ? <ImageIcon size={16} /> : <ImageOff size={16} />}
          {showPhotos ? 'Photos activées' : 'Photos désactivées'}
        </button>
      </div>
    </div>
  );
}
