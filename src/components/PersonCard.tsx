'use client';

import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Elu } from '@/lib/types';
import { User, MapPin, Briefcase } from 'lucide-react';
import { useElus } from '@/hooks/useElus';

interface PersonCardProps {
  elu: Elu;
  index: number;
}

export default function PersonCard({ elu, index }: PersonCardProps) {
  const showPhotos = useElus((s) => s.showPhotos);

  const formatMoney = (value: number) => {
    if (!value) return '--';
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M EUR`;
    }
    return `${(value / 1000).toFixed(0)}K EUR`;
  };

  const photoSrc = showPhotos
    ? (elu.photo_url || (elu.photo !== '/photos/placeholder.jpg' ? elu.photo : ''))
    : '';
  const hasFinancialData = (elu.patrimoine || 0) > 0 || (elu.revenus || 0) > 0;
  const nbDeclarations = elu.hatvp?.nb_declarations_hatvp || elu.declarations_csv?.length || 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: Math.min(index * 0.03, 0.5) }}
    >
      <Link href={`/profils/${elu.id}`}>
        <motion.div
          whileHover={{ y: -4, boxShadow: '0 12px 24px rgba(0, 0, 0, 0.12)' }}
          transition={{ duration: 0.2 }}
          className="bg-white rounded-xl overflow-hidden shadow-md hover:shadow-xl cursor-pointer h-full flex flex-row"
        >
          {/* Photo ou icone */}
          <div className="relative w-28 sm:w-32 min-h-[8rem] flex-shrink-0 bg-gradient-to-br from-blue-100 to-green-100">
            {photoSrc ? (
              <Image
                src={photoSrc}
                alt={`${elu.prenom} ${elu.nom}`}
                fill
                className="object-cover"
                sizes="(max-width: 640px) 112px, 128px"
                unoptimized={!!elu.photo_url}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <User size={48} className="text-gray-300" />
              </div>
            )}
          </div>

          {/* Contenu */}
          <div className="flex-1 p-3 sm:p-4 flex flex-col justify-between min-w-0">
            <div>
              <h3 className="text-base sm:text-lg font-bold text-gray-900 truncate">
                {elu.prenom} {elu.nom}
              </h3>
              <p className="text-xs sm:text-sm text-blue-600 font-medium truncate mt-0.5">
                {elu.fonction}
              </p>
              {elu.region && (
                <p className="text-xs text-gray-500 flex items-center gap-1 mt-1 truncate">
                  <MapPin size={12} className="flex-shrink-0" />
                  {elu.region}
                </p>
              )}
              {elu.groupe && (
                <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5 truncate">
                  <Briefcase size={12} className="flex-shrink-0" />
                  {elu.groupe}
                </p>
              )}
            </div>

            {/* Badges */}
            <div className="flex gap-1.5 flex-wrap mt-2">
              {hasFinancialData ? (
                <>
                  {(elu.patrimoine || 0) > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-semibold bg-blue-100 text-blue-800">
                      Patrimoine: {formatMoney(elu.patrimoine || 0)}
                    </span>
                  )}
                  {(elu.revenus || 0) > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-semibold bg-green-100 text-green-800">
                      Revenus: {formatMoney(elu.revenus || 0)}
                    </span>
                  )}
                </>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-semibold bg-gray-100 text-gray-600">
                  {nbDeclarations > 0
                    ? `${nbDeclarations} declaration(s)`
                    : 'Donnees en cours'}
                </span>
              )}
            </div>
          </div>
        </motion.div>
      </Link>
    </motion.div>
  );
}
