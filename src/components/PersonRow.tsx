'use client';

import Link from 'next/link';
import { Elu } from '@/lib/types';
import { MapPin } from 'lucide-react';
import { useLang, t } from '@/lib/i18n';

interface PersonRowProps {
  elu: Elu;
}

export default function PersonRow({ elu }: PersonRowProps) {
  const { lang } = useLang();

  const formatMoney = (value: number) => {
    if (!value) return '';
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M €`;
    return `${(value / 1000).toFixed(0)}K €`;
  };

  const patrimoine = formatMoney(elu.patrimoine || 0);
  const revenus = formatMoney(elu.revenus || 0);

  return (
    <Link
      href={`/profils/${elu.id}`}
      aria-label={`${elu.prenom} ${elu.nom}, ${elu.fonction}`}
      className="flex items-center gap-3 px-3 py-2.5 border-b border-th-border hover:bg-th-bg-secondary transition-colors group"
    >
      {/* Name — always visible */}
      <span className="font-semibold text-sm text-th-text group-hover:text-red-500 transition-colors w-44 sm:w-52 truncate flex-shrink-0">
        {elu.prenom} {elu.nom}
      </span>

      {/* Fonction — truncated, hidden on tiny screens */}
      <span className="hidden sm:block text-xs text-red-400 truncate flex-1 min-w-0">
        {elu.fonction}
      </span>

      {/* Region — hidden on small screens */}
      {elu.region && (
        <span className="hidden md:flex items-center gap-1 text-xs text-th-text-muted w-36 flex-shrink-0 truncate">
          <MapPin size={10} className="flex-shrink-0" />
          {elu.region}
        </span>
      )}

      {/* Financial badges */}
      <span className="flex gap-2 flex-shrink-0 text-right">
        {patrimoine && (
          <span className="text-xs font-semibold text-red-400">
            {t('card.patrimoine', lang)}: {patrimoine}
          </span>
        )}
        {revenus && (
          <span className="text-xs font-semibold text-yellow-500">
            {revenus}
          </span>
        )}
      </span>

      {/* Arrow */}
      <span className="text-th-text-muted group-hover:text-red-500 transition-colors flex-shrink-0" aria-hidden="true">
        ›
      </span>
    </Link>
  );
}
