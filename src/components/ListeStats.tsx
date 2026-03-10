'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { BarChart3, ChevronDown, ChevronUp } from 'lucide-react';
import { Elu, MandatFilter } from '@/lib/types';
import { useLang, t } from '@/lib/i18n';

interface ListeStatsProps {
  elus: Elu[];
  mandatFilter: MandatFilter;
  onMandatFilter: (filter: MandatFilter) => void;
}

/* ── Mandate type display order ─────────────────────────────────────────── */
const MANDAT_ORDER: MandatFilter[] = [
  'depute', 'senateur', 'gouvernement', 'president', 'europe',
  'region', 'departement', 'commune', 'epci', 'ctsp', 'autre',
];

const MANDAT_COLORS: Record<string, string> = {
  depute: '#DC2626',
  senateur: '#2563EB',
  gouvernement: '#7C3AED',
  president: '#B91C1C',
  europe: '#0891B2',
  region: '#059669',
  departement: '#D97706',
  commune: '#4B5563',
  epci: '#6366F1',
  ctsp: '#0D9488',
  autre: '#9CA3AF',
};

/* ── Patrimoine range bins ──────────────────────────────────────────────── */
const PATRIMOINE_BINS = [
  { min: 0, max: 0, label: '' },
  { min: 1, max: 100_000, label: '< 100K' },
  { min: 100_000, max: 500_000, label: '100–500K' },
  { min: 500_000, max: 1_000_000, label: '500K–1M' },
  { min: 1_000_000, max: 5_000_000, label: '1–5M' },
  { min: 5_000_000, max: Infinity, label: '> 5M' },
];

export default function ListeStats({ elus, mandatFilter, onMandatFilter }: ListeStatsProps) {
  const { lang } = useLang();
  const mandatSvgRef = useRef<SVGSVGElement>(null);
  const patrimoineSvgRef = useRef<SVGSVGElement>(null);
  const [open, setOpen] = useState(false);
  const [chartState, setChartState] = useState<'idle' | 'ready' | 'error'>('idle');

  /* ── Compute mandate counts ─────────────────────────────────────────── */
  const mandatCounts = useCallback(() => {
    const counts: Record<string, number> = {};
    for (const m of MANDAT_ORDER) counts[m] = 0;
    for (const elu of elus) {
      for (const tp of elu.types_mandat ?? []) {
        if (tp in counts) counts[tp]++;
      }
    }
    return MANDAT_ORDER.map(m => ({ type: m, count: counts[m] })).filter(d => d.count > 0);
  }, [elus]);

  /* ── Compute patrimoine histogram ───────────────────────────────────── */
  const patrimoineHist = useCallback(() => {
    const bins = PATRIMOINE_BINS.map(b => ({ ...b, count: 0 }));
    for (const elu of elus) {
      const p = elu.patrimoine ?? 0;
      if (p <= 0) { bins[0].count++; continue; }
      for (let i = 1; i < bins.length; i++) {
        if (p >= bins[i].min && p < bins[i].max) { bins[i].count++; break; }
      }
    }
    return bins;
  }, [elus]);

  /* ── Draw both charts ───────────────────────────────────────────────── */
  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    Promise.all([
      import('d3-selection'),
      import('d3-scale'),
      import('d3-axis'),
      import('d3-array'),
    ]).then(([d3Sel, d3Scale, d3Axis, d3Arr]) => {
      if (cancelled) return;
      setChartState('ready');

      /* ── Mandate bar chart ──────────────────────────────────────────── */
      if (mandatSvgRef.current) {
        const data = mandatCounts();
        const svg = d3Sel.select(mandatSvgRef.current);
        svg.selectAll('*').remove();

        const margin = { top: 8, right: 12, bottom: 60, left: 50 };
        const width = 500;
        const height = 240;
        const innerW = width - margin.left - margin.right;
        const innerH = height - margin.top - margin.bottom;

        svg.attr('viewBox', `0 0 ${width} ${height}`);

        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3Scale.scaleBand<string>()
          .domain(data.map(d => d.type))
          .range([0, innerW])
          .padding(0.25);

        const y = d3Scale.scaleLinear()
          .domain([0, d3Arr.max(data, d => d.count) ?? 1])
          .nice()
          .range([innerH, 0]);

        // Y axis
        g.append('g')
          .call(d3Axis.axisLeft(y).ticks(5).tickSize(-innerW))
          .call(g => g.select('.domain').remove())
          .call(g => g.selectAll('.tick line').attr('stroke', 'var(--th-border)').attr('stroke-dasharray', '2,2'))
          .call(g => g.selectAll('.tick text').attr('fill', 'var(--th-text-muted)').style('font-size', '11px'));

        // X axis labels
        g.append('g')
          .attr('transform', `translate(0,${innerH})`)
          .call(d3Axis.axisBottom(x).tickSize(0).tickFormat(d => t(`mandat.${d}`, lang)))
          .call(g => g.select('.domain').attr('stroke', 'var(--th-border)'))
          .selectAll('text')
          .attr('fill', d => (d as string) === mandatFilter ? '#DC2626' : 'var(--th-text-muted)')
          .style('font-size', '10px')
          .style('font-weight', d => (d as string) === mandatFilter ? '700' : '400')
          .attr('transform', 'rotate(-35)')
          .attr('text-anchor', 'end')
          .attr('dx', '-0.5em')
          .attr('dy', '0.3em');

        // Bars
        g.selectAll('rect.bar')
          .data(data)
          .join('rect')
          .attr('class', 'bar')
          .attr('x', d => x(d.type)!)
          .attr('y', d => y(d.count))
          .attr('width', x.bandwidth())
          .attr('height', d => innerH - y(d.count))
          .attr('rx', 3)
          .attr('fill', d => d.type === mandatFilter ? MANDAT_COLORS[d.type] : `${MANDAT_COLORS[d.type]}99`)
          .attr('stroke', d => d.type === mandatFilter ? MANDAT_COLORS[d.type] : 'none')
          .attr('stroke-width', 2)
          .style('cursor', 'pointer')
          .attr('role', 'button')
          .attr('tabindex', '0')
          .attr('aria-label', d => `${t(`mandat.${d.type}`, lang)}: ${d.count} ${t('stats.count', lang)}`)
          .on('click', (_event, d) => {
            onMandatFilter(d.type === mandatFilter ? '' : d.type as MandatFilter);
          })
          .on('touchend', (_event, d) => {
            onMandatFilter(d.type === mandatFilter ? '' : d.type as MandatFilter);
          })
          .on('keydown', (event: KeyboardEvent, d) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onMandatFilter(d.type === mandatFilter ? '' : d.type as MandatFilter);
            }
          })
          .on('mouseenter', function () {
            d3Sel.select(this).attr('opacity', 0.8);
          })
          .on('mouseleave', function () {
            d3Sel.select(this).attr('opacity', 1);
          });

        // Count labels on top of bars
        g.selectAll('.bar-label')
          .data(data)
          .join('text')
          .attr('class', 'bar-label')
          .attr('x', d => x(d.type)! + x.bandwidth() / 2)
          .attr('y', d => y(d.count) - 4)
          .attr('text-anchor', 'middle')
          .attr('fill', 'var(--th-text-muted)')
          .style('font-size', '10px')
          .style('font-weight', '600')
          .text(d => d.count > 0 ? d.count.toLocaleString('fr-FR') : '');
      }

      /* ── Patrimoine histogram ───────────────────────────────────────── */
      if (patrimoineSvgRef.current) {
        const bins = patrimoineHist();
        const displayBins = bins.filter(b => b.count > 0);
        const svg = d3Sel.select(patrimoineSvgRef.current);
        svg.selectAll('*').remove();

        const margin = { top: 8, right: 12, bottom: 40, left: 50 };
        const width = 400;
        const height = 200;
        const innerW = width - margin.left - margin.right;
        const innerH = height - margin.top - margin.bottom;

        svg.attr('viewBox', `0 0 ${width} ${height}`);

        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const noDataLabel = t('stats.no_data', lang);
        const x = d3Scale.scaleBand<string>()
          .domain(displayBins.map(b => b.label || noDataLabel))
          .range([0, innerW])
          .padding(0.2);

        const y = d3Scale.scaleLinear()
          .domain([0, d3Arr.max(displayBins, b => b.count) ?? 1])
          .nice()
          .range([innerH, 0]);

        // Y axis
        g.append('g')
          .call(d3Axis.axisLeft(y).ticks(4).tickSize(-innerW))
          .call(g => g.select('.domain').remove())
          .call(g => g.selectAll('.tick line').attr('stroke', 'var(--th-border)').attr('stroke-dasharray', '2,2'))
          .call(g => g.selectAll('.tick text').attr('fill', 'var(--th-text-muted)').style('font-size', '11px'));

        // X axis
        g.append('g')
          .attr('transform', `translate(0,${innerH})`)
          .call(d3Axis.axisBottom(x).tickSize(0))
          .call(g => g.select('.domain').attr('stroke', 'var(--th-border)'))
          .selectAll('text')
          .attr('fill', 'var(--th-text-muted)')
          .style('font-size', '10px');

        // Bars
        const barColor = '#DC2626';
        g.selectAll('rect.bar')
          .data(displayBins)
          .join('rect')
          .attr('class', 'bar')
          .attr('x', b => x(b.label || noDataLabel)!)
          .attr('y', b => y(b.count))
          .attr('width', x.bandwidth())
          .attr('height', b => innerH - y(b.count))
          .attr('rx', 3)
          .attr('fill', (_d, i) => i === 0 && !_d.label ? '#6B728066' : `${barColor}${i === 0 ? '55' : '99'}`)
          .attr('role', 'img')
          .attr('aria-label', b => `${b.label || noDataLabel}: ${b.count} ${t('stats.count', lang)}`);

        // Count labels
        g.selectAll('.hist-label')
          .data(displayBins)
          .join('text')
          .attr('class', 'hist-label')
          .attr('x', b => x(b.label || noDataLabel)! + x.bandwidth() / 2)
          .attr('y', b => y(b.count) - 4)
          .attr('text-anchor', 'middle')
          .attr('fill', 'var(--th-text-muted)')
          .style('font-size', '10px')
          .style('font-weight', '600')
          .text(b => b.count > 0 ? b.count.toLocaleString('fr-FR') : '');
      }
    }).catch(() => {
      if (!cancelled) setChartState('error');
    });

    return () => { cancelled = true; };
  }, [open, mandatCounts, patrimoineHist, mandatFilter, onMandatFilter, lang]);

  const totalWithPatrimoine = elus.filter(e => (e.patrimoine ?? 0) > 0).length;

  return (
    <div className="mb-8">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 text-sm font-medium text-th-text-secondary hover:text-red-500 transition-colors mb-3"
        aria-expanded={open}
        aria-controls="liste-stats-panel"
      >
        <BarChart3 size={16} />
        {open ? t('stats.toggle_hide', lang) : t('stats.toggle_show', lang)}
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {open && (
        <div
          id="liste-stats-panel"
          role="region"
          aria-label={t('stats.title', lang)}
          className="grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fade-in"
        >
          {/* Mandate type bar chart */}
          <div className="bg-th-card rounded-xl border border-th-border p-4">
            <h4 className="text-sm font-bold text-th-text mb-1">{t('stats.mandats', lang)}</h4>
            <p className="text-xs text-th-text-muted mb-3">{t('stats.click_filter', lang)}</p>
            {chartState !== 'error' ? (
              <>
                <svg
                  ref={mandatSvgRef}
                  className="w-full"
                  role="img"
                  aria-label={t('stats.mandats', lang)}
                />
                {chartState === 'idle' && (
                  <div className="h-48 flex items-center justify-center" aria-hidden="true">
                    <div className="w-6 h-6 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-th-text-muted italic py-8 text-center">
                {t('stats.mandats', lang)} — {mandatCounts().map(d => `${t(`mandat.${d.type}`, lang)}: ${d.count}`).join(', ')}
              </p>
            )}
          </div>

          {/* Patrimoine histogram */}
          <div className="bg-th-card rounded-xl border border-th-border p-4">
            <h4 className="text-sm font-bold text-th-text mb-1">{t('stats.patrimoine', lang)}</h4>
            <p className="text-xs text-th-text-muted mb-3">
              {totalWithPatrimoine.toLocaleString('fr-FR')} {t('stats.total_with_data', lang)}
            </p>
            {chartState !== 'error' ? (
              <svg
                ref={patrimoineSvgRef}
                className="w-full"
                role="img"
                aria-label={t('stats.patrimoine', lang)}
              />
            ) : (
              <p className="text-xs text-th-text-muted italic py-8 text-center">
                {t('stats.patrimoine', lang)} — {patrimoineHist().filter(b => b.count > 0).map(b => `${b.label || t('stats.no_data', lang)}: ${b.count}`).join(', ')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
