'use client';

import { useLang, t } from '@/lib/i18n';
import Link from 'next/link';
import {
  Scale,
  Wallet,
  FileText,
  Briefcase,
  ExternalLink,
  ArrowRight,
  MapPin,
  Users as UsersIcon,
} from 'lucide-react';

export default function HomePage() {
  const { lang } = useLang();

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero */}
      <section className="text-center mb-16">
        <h2 className="text-4xl sm:text-5xl font-black text-white mb-4 tracking-tight">
          {t('home.hero.title', lang)}
        </h2>
        <p className="text-base sm:text-lg text-neutral-300 max-w-2xl mx-auto leading-relaxed">
          {t('home.hero.lead', lang)}
        </p>
        <p className="text-xs text-neutral-500 mt-4">
          {t('home.hero.source', lang)}
        </p>
      </section>

      {/* Example card with legend */}
      <section className="mb-16">
        <h3 className="text-xl font-bold text-yellow-400 mb-6 text-center">
          {t('home.how.title', lang)}
        </h3>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Annotated example card */}
          <div className="lg:col-span-2 bg-neutral-800 rounded-2xl border-2 border-red-600 overflow-hidden shadow-xl">
            <div className="bg-gradient-to-br from-red-700 to-red-900 h-36 flex items-center justify-center">
              <div className="w-20 h-20 rounded-full bg-neutral-700 flex items-center justify-center">
                <span className="text-neutral-400 text-3xl font-black">?</span>
              </div>
            </div>
            <div className="p-5 space-y-3">
              <h4 className="text-lg font-bold text-white">{t('home.example.name', lang)}</h4>
              <p className="text-sm text-red-400 font-semibold">{t('home.example.fonction', lang)}</p>
              <p className="text-xs text-neutral-400 flex items-center gap-1">
                <MapPin size={12} className="text-neutral-500" />
                {t('home.example.region', lang)}
              </p>
              <p className="text-xs text-neutral-400 flex items-center gap-1">
                <UsersIcon size={12} className="text-neutral-500" />
                {t('home.example.groupe', lang)}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-900/60 text-red-300 border border-red-700">
                  {t('card.patrimoine', lang)}: 1.2M EUR
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-yellow-900/60 text-yellow-300 border border-yellow-700">
                  {t('card.revenus', lang)}: 85K EUR
                </span>
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="lg:col-span-3 space-y-3">
            {[
              { icon: Scale, color: 'text-red-400', bg: 'bg-red-900/30', key: 'home.legend.patrimoine' },
              { icon: Wallet, color: 'text-yellow-400', bg: 'bg-yellow-900/30', key: 'home.legend.revenus' },
              { icon: FileText, color: 'text-neutral-300', bg: 'bg-neutral-800', key: 'home.legend.declarations' },
              { icon: Briefcase, color: 'text-neutral-300', bg: 'bg-neutral-800', key: 'home.legend.mandats' },
              { icon: ExternalLink, color: 'text-neutral-300', bg: 'bg-neutral-800', key: 'home.legend.liens' },
            ].map(({ icon: Icon, color, bg, key }) => (
              <div key={key} className={`flex items-start gap-3 ${bg} rounded-xl p-3 border border-neutral-700`}>
                <Icon size={18} className={`${color} mt-0.5 flex-shrink-0`} />
                <p className="text-sm text-neutral-200">{t(key, lang)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="mb-16 bg-neutral-800 rounded-2xl border border-neutral-700 p-6 sm:p-8">
        <h3 className="text-lg font-bold text-yellow-400 mb-4">
          {t('home.methodo.title', lang)}
        </h3>
        <ol className="space-y-2 text-sm text-neutral-300 list-decimal list-inside">
          <li>{t('home.methodo.1', lang)}</li>
          <li>{t('home.methodo.2', lang)}</li>
          <li>{t('home.methodo.3', lang)}</li>
        </ol>
      </section>

      {/* CTA */}
      <div className="text-center">
        <Link
          href="/liste"
          className="inline-flex items-center gap-3 px-8 py-4 bg-red-600 hover:bg-red-700 text-white rounded-xl shadow-lg hover:shadow-xl font-bold text-lg transition-colors"
        >
          {t('home.cta', lang)}
          <ArrowRight className="w-5 h-5" />
        </Link>
      </div>
    </div>
  );
}
