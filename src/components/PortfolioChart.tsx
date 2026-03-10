'use client';

import { useState, useMemo } from 'react';
import { pie, arc, PieArcDatum } from 'd3-shape';
import { motion } from 'framer-motion';
import { useLang, t } from '@/lib/i18n';

interface PortfolioChartProps {
  immobilier: number;
  placements: number | number[];
  patrimoine: number;
}

interface SliceData {
  name: string;
  value: number;
  color: string;
}

const COLORS = {
  immobilier: '#DC2626', // red
  placements: '#F59E0B', // yellow
  autres: '#A3A3A3',     // neutral gray
};

const SIZE = 280;
const OUTER_R = SIZE / 2 - 10;
const INNER_R = OUTER_R * 0.55;

export default function PortfolioChart({ immobilier, placements, patrimoine }: PortfolioChartProps) {
  const { lang } = useLang();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // placements may be an array (legacy format, always empty) or a number; use placements_montant when available
  const placementsVal = typeof placements === 'number' ? placements : 0;
  const autres = Math.max(0, patrimoine - immobilier - placementsVal);

  const data: SliceData[] = useMemo(() =>
    [
      { name: t('chart.immobilier', lang), value: immobilier, color: COLORS.immobilier },
      { name: t('chart.placements', lang), value: placementsVal, color: COLORS.placements },
      { name: t('chart.autres', lang), value: autres, color: COLORS.autres },
    ].filter(item => item.value > 0),
    [immobilier, placementsVal, autres, lang]
  );

  // Don't show pie chart if there's only one category — it would be 100%
  if (data.length <= 1) return null;

  const formatMoney = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M\u00A0€`;
    if (value >= 1000) return `${(value / 1000).toFixed(0)}K\u00A0€`;
    return `${value}\u00A0€`;
  };

  const formatPercent = (value: number) => `${((value / patrimoine) * 100).toFixed(1)}%`;

  const pieGen = pie<SliceData>().value(d => d.value).sort(null).padAngle(0.02);
  const arcs = pieGen(data);

  const arcGen = arc<PieArcDatum<SliceData>>()
    .innerRadius(INNER_R)
    .outerRadius(OUTER_R)
    .cornerRadius(4);

  const arcHover = arc<PieArcDatum<SliceData>>()
    .innerRadius(INNER_R - 3)
    .outerRadius(OUTER_R + 8)
    .cornerRadius(4);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-th-card rounded-xl shadow-lg p-6 border border-th-border"
    >
      <h3 className="text-xl font-bold text-th-text mb-4">
        {t('profil.composition', lang)}
      </h3>

      <div className="flex flex-col items-center">
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`${-SIZE / 2} ${-SIZE / 2} ${SIZE} ${SIZE}`}
          className="overflow-visible"
          role="img"
          aria-label={t('profil.composition', lang)}
        >
          {arcs.map((d, i) => (
            <path
              key={i}
              d={(hoveredIndex === i ? arcHover(d) : arcGen(d)) || ''}
              fill={d.data.color}
              opacity={hoveredIndex !== null && hoveredIndex !== i ? 0.4 : 1}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              style={{ transition: 'opacity 0.2s ease, d 0.2s ease' }}
              className="cursor-pointer"
            />
          ))}
          {/* Center text */}
          <text textAnchor="middle" dy="-0.3em" className="fill-th-text text-sm font-bold" style={{ fontSize: 14 }}>
            {hoveredIndex !== null ? data[hoveredIndex].name : 'Total'}
          </text>
          <text textAnchor="middle" dy="1.1em" className="fill-th-text-secondary" style={{ fontSize: 13 }}>
            {hoveredIndex !== null ? formatMoney(data[hoveredIndex].value) : formatMoney(patrimoine)}
          </text>
          <text textAnchor="middle" dy="2.4em" className="fill-th-text-muted" style={{ fontSize: 11 }}>
            {hoveredIndex !== null ? formatPercent(data[hoveredIndex].value) : ''}
          </text>
        </svg>
      </div>

      {/* Légende détaillée */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
        {data.map((item, i) => (
          <div
            key={item.name}
            className={`flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer ${hoveredIndex === i ? 'bg-th-bg-secondary' : ''}`}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <div
              className="w-4 h-4 rounded-full flex-shrink-0"
              style={{ backgroundColor: item.color }}
            />
            <div>
              <p className="text-sm font-semibold text-th-text-secondary">{item.name}</p>
              <p className="text-lg font-bold text-th-text">{formatMoney(item.value)}</p>
              <p className="text-xs text-th-text-muted">{formatPercent(item.value)}</p>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
