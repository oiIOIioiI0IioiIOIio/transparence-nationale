'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { motion } from 'framer-motion';

interface PortfolioChartProps {
  immobilier: number;
  placements: number;
  patrimoine: number;
}

const COLORS = {
  immobilier: '#3b82f6', // bleu
  placements: '#10b981',  // vert
  autres: '#f97316',      // orange
};

export default function PortfolioChart({ immobilier, placements, patrimoine }: PortfolioChartProps) {
  const autres = Math.max(0, patrimoine - immobilier - placements);

  const data = [
    { name: 'Immobilier', value: immobilier, color: COLORS.immobilier },
    { name: 'Placements', value: placements, color: COLORS.placements },
    { name: 'Autres', value: autres, color: COLORS.autres },
  ].filter(item => item.value > 0);

  const formatMoney = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M€`;
    }
    return `${(value / 1000).toFixed(0)}K€`;
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
      className="bg-white rounded-xl shadow-lg p-6"
    >
      <h3 className="text-xl font-bold text-gray-900 mb-4">
        Composition du Patrimoine
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
            formatter={(value: number) => formatMoney(value)}
          />
          <Legend />
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
              <p className="text-sm font-semibold text-gray-700">{item.name}</p>
              <p className="text-lg font-bold text-gray-900">{formatMoney(item.value)}</p>
              <p className="text-xs text-gray-500">{formatPercent(item.value)}</p>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
