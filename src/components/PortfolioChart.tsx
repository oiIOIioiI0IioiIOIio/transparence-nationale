'use client';

import { useEffect, useRef, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useLang, t } from '@/lib/i18n';
import type { PieArcDatum } from 'd3-shape';

interface PortfolioChartProps {
  immobilier: number;
  placements: number | number[];
  patrimoine: number;
}

const COLORS = {
  immobilier: '#DC2626',
  placements: '#F59E0B',
  autres: '#A3A3A3',
};

export default function PortfolioChart({ immobilier, placements, patrimoine }: PortfolioChartProps) {
  const { lang } = useLang();
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const [chartState, setChartState] = useState<'loading' | 'ready' | 'error'>('loading');

  const placementsVal = typeof placements === 'number' ? placements : 0;
  const autres = Math.max(0, patrimoine - immobilier - placementsVal);

  const data = useMemo(() => [
    { name: t('chart.immobilier', lang), value: immobilier, color: COLORS.immobilier },
    { name: t('chart.placements', lang), value: placementsVal, color: COLORS.placements },
    { name: t('chart.autres', lang), value: autres, color: COLORS.autres },
  ].filter(item => item.value > 0), [immobilier, placementsVal, autres, lang]);

  const dataKey = data.map(d => `${d.name}:${d.value}`).join('|');
  const shouldRender = data.length > 1;

  const formatMoney = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M\u00A0\u20AC`;
    return `${(value / 1000).toFixed(0)}K\u00A0\u20AC`;
  };

  const formatPercent = (value: number) => {
    const percent = (value / patrimoine) * 100;
    return `${percent.toFixed(1)}%`;
  };

  const activeIndex = hoveredIndex ?? focusedIndex;

  useEffect(() => {
    if (!shouldRender || !svgRef.current) return;

    let cancelled = false;

    Promise.all([
      import('d3-selection'),
      import('d3-shape'),
    ]).then(([d3Selection, d3Shape]) => {
      if (cancelled || !svgRef.current) return;
      setChartState('ready');

      const width = 240;
      const height = 240;
      const radius = Math.min(width, height) / 2;

      const sel = d3Selection.select(svgRef.current);
      sel.selectAll('*').remove();

      const g = sel
        .attr('viewBox', `0 0 ${width} ${height}`)
        .append('g')
        .attr('transform', `translate(${width / 2},${height / 2})`);

      const pie = d3Shape.pie<(typeof data)[0]>().value(d => d.value).sort(null);
      const arc = d3Shape.arc<PieArcDatum<(typeof data)[0]>>()
        .innerRadius(radius * 0.5)
        .outerRadius(radius * 0.85);
      const arcHover = d3Shape.arc<PieArcDatum<(typeof data)[0]>>()
        .innerRadius(radius * 0.48)
        .outerRadius(radius * 0.9);

      const arcs = pie(data);

      g.selectAll('path')
        .data(arcs)
        .join('path')
        .attr('d', arc)
        .attr('fill', d => d.data.color)
        .attr('stroke', 'var(--th-card)')
        .attr('stroke-width', 2)
        .style('cursor', 'pointer')
        .on('mouseenter', function (_event, d) {
          d3Selection.select(this).attr('d', arcHover(d));
          setHoveredIndex(d.index);
        })
        .on('mouseleave', function (_event, d) {
          d3Selection.select(this).attr('d', arc(d));
          setHoveredIndex(null);
        })
        .on('touchstart', function (_event, d) {
          setHoveredIndex(prev => prev === d.index ? null : d.index);
        }, { passive: true });

      // Center total
      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '-0.2em')
        .attr('fill', 'var(--th-text-muted)')
        .style('font-size', '11px')
        .text('Total');

      g.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '1.2em')
        .attr('fill', 'var(--th-text)')
        .style('font-size', '14px')
        .style('font-weight', '700')
        .text(formatMoney(patrimoine));
    }).catch(() => {
      if (!cancelled) setChartState('error');
    });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey, lang, shouldRender]);

  // Don't show pie chart if there's only one category — it would be 100%
  if (!shouldRender) return null;

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

      {chartState !== 'error' && (
        <div className="flex flex-col items-center">
          <svg
            ref={svgRef}
            className="w-full max-w-[240px]"
            role="img"
            aria-label={t('profil.composition', lang)}
          />
          {chartState === 'loading' && (
            <div className="w-60 h-60 flex items-center justify-center" aria-hidden="true">
              <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>
      )}

      {/* Detailed legend — always visible, serves as fallback if chart fails */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6" role="list" aria-label={t('profil.composition', lang)}>
        {data.map((item, i) => (
          <div
            key={item.name}
            role="listitem"
            className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${activeIndex === i ? 'bg-th-bg-secondary' : ''}`}
            onMouseEnter={() => setHoveredIndex(i)}
            onMouseLeave={() => setHoveredIndex(null)}
            onFocus={() => setFocusedIndex(i)}
            onBlur={() => setFocusedIndex(null)}
            tabIndex={0}
            aria-label={`${item.name}: ${formatMoney(item.value)} (${formatPercent(item.value)})`}
          >
            <div
              className="w-4 h-4 rounded-full flex-shrink-0"
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
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
