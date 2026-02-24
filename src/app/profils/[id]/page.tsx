'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ArrowLeft, ExternalLink, User, Briefcase, MapPin } from 'lucide-react';
import { Elu } from '@/lib/types';
import PortfolioChart from '@/components/PortfolioChart';

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
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(value);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Bouton retour */}
      <motion.button
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        onClick={() => router.push('/')}
        className="flex items-center gap-2 text-gray-600 hover:text-blue-600 mb-8 transition-colors"
      >
        <ArrowLeft size={20} />
        <span className="font-medium">Retour à la galerie</span>
      </motion.button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Colonne gauche - Photo et infos */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="lg:col-span-1"
        >
          <div className="bg-white rounded-xl shadow-lg overflow-hidden sticky top-24">
            {/* Photo */}
            <div className="relative h-80 bg-gradient-to-br from-blue-100 to-green-100">
              {elu.photo ? (
                <Image
                  src={elu.photo}
                  alt={`${elu.prenom} ${elu.nom}`}
                  fill
                  className="object-cover"
                  priority
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <User size={120} className="text-gray-300" />
                </div>
              )}
            </div>

            {/* Infos de base */}
            <div className="p-6">
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {elu.prenom} {elu.nom}
              </h1>
              
              <div className="space-y-3 mb-6">
                <div className="flex items-start gap-3">
                  <Briefcase size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-sm text-gray-500">Fonction</p>
                    <p className="font-semibold text-gray-900">{elu.fonction}</p>
                  </div>
                </div>
                
                {elu.region && (
                  <div className="flex items-start gap-3">
                    <MapPin size={20} className="text-blue-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm text-gray-500">Région</p>
                      <p className="font-semibold text-gray-900">{elu.region}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Liens externes */}
              {(elu.liens.assemblee || elu.liens.hatvp || elu.liens.wikipedia) && (
                <div className="border-t pt-4">
                  <p className="text-sm font-semibold text-gray-700 mb-3">
                    Liens externes
                  </p>
                  <div className="space-y-2">
                    {elu.liens.assemblee && (
                      <a
                        href={elu.liens.assemblee}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                      >
                        <ExternalLink size={16} />
                        Assemblée Nationale
                      </a>
                    )}
                    {elu.liens.hatvp && (
                      <a
                        href={elu.liens.hatvp}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                      >
                        <ExternalLink size={16} />
                        Déclaration HATVP
                      </a>
                    )}
                    {elu.liens.wikipedia && (
                      <a
                        href={elu.liens.wikipedia}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                      >
                        <ExternalLink size={16} />
                        Wikipedia
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* Colonne droite - Stats et graphiques */}
        <div className="lg:col-span-2 space-y-6">
          {/* Stats Cards */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="grid grid-cols-1 sm:grid-cols-2 gap-6"
          >
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-6 text-white">
              <p className="text-blue-100 text-sm font-medium mb-2">
                Patrimoine Total
              </p>
              <p className="text-3xl font-bold mb-1">
                {formatMoney(elu.patrimoine)}
              </p>
              <p className="text-blue-100 text-xs">
                Déclaré à la HATVP
              </p>
            </div>

            <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl shadow-lg p-6 text-white">
              <p className="text-green-100 text-sm font-medium mb-2">
                Revenus Annuels
              </p>
              <p className="text-3xl font-bold mb-1">
                {formatMoney(elu.revenus)}
              </p>
              <p className="text-green-100 text-xs">
                Bruts déclarés
              </p>
            </div>
          </motion.div>

          {/* Graphique */}
          <PortfolioChart
            immobilier={elu.immobilier}
            placements={elu.placements}
            patrimoine={elu.patrimoine}
          />

          {/* Mandats */}
          {elu.mandats.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.3 }}
              className="bg-white rounded-xl shadow-lg p-6"
            >
              <h3 className="text-xl font-bold text-gray-900 mb-4">
                Mandats et Fonctions
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
        </div>
      </div>
    </div>
  );
}
