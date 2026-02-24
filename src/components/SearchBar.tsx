'use client';

import { Search } from 'lucide-react';
import { useElus } from '@/hooks/useElus';
import { SortBy } from '@/lib/types';

export default function SearchBar() {
  const { searchTerm, setSearchTerm, sortBy, setSortBy } = useElus();

  return (
    <div className="flex flex-col sm:flex-row gap-4 mb-8">
      {/* Barre de recherche */}
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

      {/* Dropdown de tri */}
      <select
        value={sortBy}
        onChange={(e) => setSortBy(e.target.value as SortBy)}
        className="px-6 py-3 border-2 border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none cursor-pointer bg-white transition-colors"
      >
        <option value="nom">Trier par Nom ↑</option>
        <option value="patrimoine">Trier par Patrimoine ↓</option>
        <option value="revenus">Trier par Revenus ↓</option>
      </select>
    </div>
  );
}
