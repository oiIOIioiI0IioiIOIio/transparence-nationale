'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { motion } from 'framer-motion';
import { useLang, t } from '@/lib/i18n';

interface PortfolioChartProps {
  immobilier: number;
  placements: number | number[];
  patrimoine: number;
}

const COLORS = {
  immobilier: '#DC2626', // red
  placements: '#F59E0B', // yellow
  autres: '#A3A3A3',     // neutral gray
};

export default function PortfolioChart({ immobilier, placements, patrimoine }: PortfolioChartProps) {
  const { lang } = useLang();
  // placements may be an array (legacy format, always empty) or a number; use placements_montant when available
  const placementsVal = typeof placements === 'number' ? placements : 0;
  const autres = Math.max(0, patrimoine - immobilier - placementsVal);

  const data = [
    { name: t('chart.immobilier', lang), value: immobilier, color: COLORS.immobilier },
    { name: t('chart.placements', lang), value: placementsVal, color: COLORS.placements },
    { name: t('chart.autres', lang), value: autres, color: COLORS.autres },
  ].filter(item => item.value > 0);

  // Don't show pie chart if there's only one category — it would be 100%
  if (data.length <= 1) return null;

  const formatMoney = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M\u00A0\u20AC`;
    }
    return `${(value / 1000).toFixed(0)}K\u00A0\u20AC`;
  };

  const formatPercent = (value: number) => {
    const percent = (value / patrimoine) * 100;
    return `${percent.toFixed(1)}%`;
  };

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
      
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, value }) => `${name}: ${formatPercent(value)}`}
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip 
            formatter={(value) => formatMoney(Number(value))}
            contentStyle={{ backgroundColor: 'var(--th-tooltip-bg)', border: '1px solid var(--th-tooltip-border)', borderRadius: '8px', color: 'var(--th-tooltip-text)' }}
            labelStyle={{ color: 'var(--th-text-secondary)' }}
          />
          <Legend wrapperStyle={{ color: 'var(--th-text-secondary)' }} />
        </PieChart>
      </ResponsiveContainer>

      {/* Légende détaillée */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
        {data.map((item) => (
          <div key={item.name} className="flex items-center gap-3">
            <div 
              className="w-4 h-4 rounded-full" 
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
