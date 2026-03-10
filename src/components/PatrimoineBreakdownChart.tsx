'use client';

import { useState, useMemo } from 'react';
import { scaleLinear } from 'd3-scale';
import { max } from 'd3-array';
import { motion } from 'framer-motion';
import { useLang } from '@/lib/i18n';

interface CategoryData {
  label: string;
  value: number;
  count: number;
}

interface PatrimoineBreakdownChartProps {
  categories: CategoryData[];
}

const COLORS = [
  '#DC2626', '#B91C1C', '#991B1B', // reds
  '#F59E0B', '#D97706', '#B45309', // yellows
  '#6B7280', '#4B5563', '#374151', // grays
  '#EF4444', '#F97316', '#A3A3A3', // more
];

export default function PatrimoineBreakdownChart({ categories }: PatrimoineBreakdownChartProps) {
  const { lang } = useLang();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Sort by value descending, only keep non-zero
  const data = useMemo(() =>
    [...categories]
      .filter(d => d.value > 0)
      .sort((a, b) => b.value - a.value),
    [categories]
  );

  if (data.length === 0) return null;

  const maxVal = max(data, d => d.value) || 0;
  const totalVal = data.reduce((sum, d) => sum + d.value, 0);
  const barScale = scaleLinear().domain([0, maxVal]).range([0, 100]); // percentage width

  const formatMoney = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M\u00A0€`;
    if (value >= 1000) return `${Math.round(value / 1000)}K\u00A0€`;
    return `${value}\u00A0€`;
  };

  const formatMoneyFull = (value: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(value);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.3 }}
      className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
    >
      <h3 className="text-lg sm:text-xl font-bold text-th-text mb-4">
        {lang === 'fr' ? 'Ventilation du patrimoine' : 'Wealth Breakdown'}
      </h3>

      <div className="space-y-2">
        {data.map((d, i) => {
          const isHovered = hoveredIndex === i;
          const pct = totalVal > 0 ? ((d.value / totalVal) * 100).toFixed(1) : '0';
          const barWidth = barScale(d.value);

          return (
            <div
              key={d.label}
              className={`flex items-center gap-2 sm:gap-3 py-1.5 px-2 rounded-lg transition-colors cursor-pointer ${isHovered ? 'bg-th-bg-secondary' : ''}`}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {/* Label */}
              <div className="w-36 sm:w-44 flex-shrink-0 text-right">
                <span className={`text-xs sm:text-sm truncate block ${isHovered ? 'text-th-text font-semibold' : 'text-th-text-secondary'}`}>
                  {d.label}
                </span>
              </div>

              {/* Bar */}
              <div className="flex-1 min-w-0">
                <div className="h-6 sm:h-7 bg-th-bg-secondary/50 rounded-md overflow-hidden relative">
                  <div
                    className="h-full rounded-md transition-all duration-300 ease-out"
                    style={{
                      width: `${barWidth}%`,
                      backgroundColor: COLORS[i % COLORS.length],
                      opacity: hoveredIndex !== null && !isHovered ? 0.4 : 1,
                    }}
                  />
                  {/* Inline count badge */}
                  {d.count > 0 && (
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-th-text-muted font-medium">
                      ×{d.count}
                    </span>
                  )}
                </div>
              </div>

              {/* Value */}
              <div className="w-20 sm:w-24 flex-shrink-0 text-right">
                <span className={`text-xs sm:text-sm font-bold tabular-nums ${isHovered ? 'text-red-500' : 'text-th-text'}`}>
                  {isHovered ? formatMoneyFull(d.value) : formatMoney(d.value)}
                </span>
                <span className="text-[10px] text-th-text-muted block">
                  {pct}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
