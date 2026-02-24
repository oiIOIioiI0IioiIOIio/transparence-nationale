'use client';

import { useEffect } from 'react';
import { useElus, loadElus } from '@/hooks/useElus';
import PersonCard from '@/components/PersonCard';
import SearchBar from '@/components/SearchBar';
import { Loader2 } from 'lucide-react';

export default function HomePage() {
  const { loading, getFiltered } = useElus();
  const filteredElus = getFiltered();

  useEffect(() => {
    loadElus();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Chargement des données...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4">
          Patrimoine des Élus Français
        </h2>
        <p className="text-lg text-gray-600 max-w-3xl mx-auto">
          Explorez de manière interactive le patrimoine et les revenus des représentants 
          de la République grâce aux données officielles de la HATVP
        </p>
        <div className="flex items-center justify-center gap-6 mt-6 text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
            <span>{filteredElus.length} élus recensés</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <span>Données HATVP officielles</span>
          </div>
        </div>
      </div>

      {/* SearchBar */}
      <SearchBar />

      {/* Galerie */}
      {filteredElus.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredElus.map((elu, index) => (
            <PersonCard key={elu.id} elu={elu} index={index} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">🔍</div>
          <h3 className="text-2xl font-bold text-gray-900 mb-2">
            Aucun résultat trouvé
          </h3>
          <p className="text-gray-600">
            Essayez de modifier votre recherche
          </p>
        </div>
      )}
    </div>
  );
}
