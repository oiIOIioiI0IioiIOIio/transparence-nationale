'use client';

import { useState, useMemo, useRef } from 'react';
import { scaleLinear, scaleBand } from 'd3-scale';
import { max } from 'd3-array';
import { motion } from 'framer-motion';
import { useLang } from '@/lib/i18n';

interface YearRevenue {
  annee: string;
  montant: number;
}

interface RevenueTimelineChartProps {
  /** Revenue data aggregated by year, e.g. from details_activites + details_mandats */
  yearlyData: YearRevenue[];
}

const MARGIN = { top: 16, right: 16, bottom: 32, left: 60 };
export default function RevenueTimelineChart({ yearlyData }: RevenueTimelineChartProps) {
  const { lang } = useLang();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Sort by year ascending and deduplicate
  const data = useMemo(() => {
    const merged = new Map<string, number>();
    for (const d of yearlyData) {
      if (d.annee && d.montant > 0) {
        merged.set(d.annee, (merged.get(d.annee) || 0) + d.montant);
      }
    }
    return Array.from(merged.entries())
      .map(([annee, montant]) => ({ annee, montant }))
      .sort((a, b) => a.annee.localeCompare(b.annee));
  }, [yearlyData]);

  if (data.length < 2) return null;

  const width = 500;
  const height = 220;
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;

  const xScale = scaleBand<string>()
    .domain(data.map(d => d.annee))
    .range([0, innerW])
    .padding(0.3);

  const yMax = max(data, d => d.montant) || 0;
  const yScale = scaleLinear()
    .domain([0, yMax * 1.1])
    .range([innerH, 0]);

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

  // Y-axis ticks (3-4 ticks)
  const yTicks = yScale.ticks(4);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.25 }}
      className="bg-th-card rounded-xl shadow-lg p-4 sm:p-6 border border-th-border"
    >
      <h3 className="text-lg sm:text-xl font-bold text-th-text mb-4">
        {lang === 'fr' ? 'Évolution des revenus déclarés' : 'Declared income over time'}
      </h3>

      <div ref={containerRef} className="w-full overflow-x-auto">
        <svg
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="xMidYMid meet"
          className="overflow-visible"
          role="img"
          aria-label={lang === 'fr' ? 'Graphique des revenus par année' : 'Revenue chart by year'}
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {/* Grid lines */}
            {yTicks.map(tick => (
              <line
                key={tick}
                x1={0}
                x2={innerW}
                y1={yScale(tick)}
                y2={yScale(tick)}
                stroke="var(--th-border)"
                strokeDasharray="3,3"
                opacity={0.5}
              />
            ))}

            {/* Y axis labels */}
            {yTicks.map(tick => (
              <text
                key={tick}
                x={-8}
                y={yScale(tick)}
                textAnchor="end"
                dy="0.35em"
                className="fill-th-text-muted"
                style={{ fontSize: 11 }}
              >
                {formatMoney(tick)}
              </text>
            ))}

            {/* Bars */}
            {data.map((d, i) => {
              const barH = innerH - yScale(d.montant);
              const isHovered = hoveredIndex === i;
              return (
                <g key={d.annee}>
                  <rect
                    x={xScale(d.annee)}
                    y={yScale(d.montant) - (isHovered ? 2 : 0)}
                    width={xScale.bandwidth()}
                    height={barH + (isHovered ? 2 : 0)}
                    rx={3}
                    fill={isHovered ? '#F59E0B' : '#FBBF24'}
                    opacity={hoveredIndex !== null && !isHovered ? 0.5 : 1}
                    onMouseEnter={() => setHoveredIndex(i)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className="cursor-pointer"
                    style={{ transition: 'opacity 0.15s ease, y 0.15s ease, height 0.15s ease' }}
                  />
                  {/* X axis label */}
                  <text
                    x={(xScale(d.annee) || 0) + xScale.bandwidth() / 2}
                    y={innerH + 18}
                    textAnchor="middle"
                    className={`${isHovered ? 'fill-th-text font-semibold' : 'fill-th-text-muted'}`}
                    style={{ fontSize: 12, transition: 'fill 0.15s ease' }}
                  >
                    {d.annee}
                  </text>
                  {/* Hover label on bar */}
                  {isHovered && (
                    <text
                      x={(xScale(d.annee) || 0) + xScale.bandwidth() / 2}
                      y={yScale(d.montant) - 8}
                      textAnchor="middle"
                      className="fill-yellow-500 font-bold"
                      style={{ fontSize: 12 }}
                    >
                      {formatMoneyFull(d.montant)}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </motion.div>
  );
}
