'use client';

import Image from 'next/image';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Elu } from '@/lib/types';
import { User } from 'lucide-react';

interface PersonCardProps {
  elu: Elu;
  index: number;
}

export default function PersonCard({ elu, index }: PersonCardProps) {
  const formatMoney = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M€`;
    }
    return `${(value / 1000).toFixed(0)}K€`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Link href={`/profils/${elu.id}`}>
        <motion.div
          whileHover={{ y: -8, boxShadow: '0 20px 40px rgba(0, 0, 0, 0.15)' }}
          transition={{ duration: 0.2 }}
          className="bg-white rounded-xl overflow-hidden shadow-md hover:shadow-2xl cursor-pointer h-full"
        >
          {/* Photo */}
          <div className="relative h-64 bg-gradient-to-br from-blue-100 to-green-100">
            {elu.photo ? (
              <Image
                src={elu.photo}
                alt={`${elu.prenom} ${elu.nom}`}
                fill
                className="object-cover"
                sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <User size={80} className="text-gray-300" />
              </div>
            )}
          </div>

          {/* Contenu */}
          <div className="p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-1">
              {elu.prenom} {elu.nom}
            </h3>
            <p className="text-sm text-blue-600 font-medium mb-3">
              {elu.fonction}
            </p>
            {elu.region && (
              <p className="text-sm text-gray-500 mb-4">{elu.region}</p>
            )}

            {/* Badges */}
            <div className="flex gap-2 flex-wrap">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                Patrimoine: {formatMoney(elu.patrimoine)}
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                Revenus: {formatMoney(elu.revenus)}
              </span>
            </div>
          </div>
        </motion.div>
      </Link>
    </motion.div>
  );
}
