'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Elu } from '@/lib/types';
import { User, MapPin, Briefcase } from 'lucide-react';
import { useLang, t } from '@/lib/i18n';

interface PersonCardProps {
  elu: Elu;
  index: number;
}

export default function PersonCard({ elu, index }: PersonCardProps) {
  const { lang } = useLang();

  const formatMoney = (value: number) => {
    if (!value) return '--';
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M EUR`;
    }
    return `${(value / 1000).toFixed(0)}K EUR`;
  };

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
          whileHover={{ y: -4, boxShadow: '0 12px 24px rgba(220, 38, 38, 0.15)' }}
          transition={{ duration: 0.2 }}
          className="bg-neutral-800 rounded-xl overflow-hidden shadow-md hover:shadow-xl cursor-pointer h-full flex flex-row border border-neutral-700 hover:border-red-600 transition-colors"
        >
          {/* Icone placeholder (photos désactivées dans la liste) */}
          <div className="relative w-20 sm:w-24 min-h-[8rem] flex-shrink-0 bg-gradient-to-br from-red-900/40 to-neutral-800">
            <div className="w-full h-full flex items-center justify-center">
              <User size={40} className="text-neutral-600" />
            </div>
          </div>

          {/* Contenu */}
          <div className="flex-1 p-3 sm:p-4 flex flex-col justify-between min-w-0">
            <div>
              <h3 className="text-base sm:text-lg font-bold text-white truncate">
                {elu.prenom} {elu.nom}
              </h3>
              <p className="text-xs sm:text-sm text-red-400 font-medium truncate mt-0.5">
                {elu.fonction}
              </p>
              {elu.region && (
                <p className="text-xs text-neutral-400 flex items-center gap-1 mt-1 truncate">
                  <MapPin size={12} className="flex-shrink-0" />
                  {elu.region}
                </p>
              )}
              {elu.groupe && (
                <p className="text-xs text-neutral-400 flex items-center gap-1 mt-0.5 truncate">
                  <Briefcase size={12} className="flex-shrink-0" />
                  {elu.groupe}
                </p>
              )}
            </div>

            {/* Badges — taille augmentée */}
            <div className="flex gap-2 flex-wrap mt-2">
              {hasFinancialData ? (
                <>
                  {(elu.patrimoine || 0) > 0 && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs sm:text-sm font-semibold bg-red-900/60 text-red-300 border border-red-700">
                      {t('card.patrimoine', lang)}: {formatMoney(elu.patrimoine || 0)}
                    </span>
                  )}
                  {(elu.revenus || 0) > 0 && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs sm:text-sm font-semibold bg-yellow-900/60 text-yellow-300 border border-yellow-700">
                      {t('card.revenus', lang)}: {formatMoney(elu.revenus || 0)}
                    </span>
                  )}
                </>
              ) : (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs sm:text-sm font-semibold bg-neutral-700 text-neutral-300">
                  {nbDeclarations > 0
                    ? `${nbDeclarations} ${t('card.declarations', lang)}`
                    : t('card.data_pending', lang)}
                </span>
              )}
            </div>
          </div>
        </motion.div>
      </Link>
    </motion.div>
  );
}
