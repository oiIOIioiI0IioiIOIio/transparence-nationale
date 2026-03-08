'use client';

import { useEffect } from 'react';
import { Sun, Moon } from 'lucide-react';
import { useLang, t } from '@/lib/i18n';
import { useTheme, initTheme } from '@/lib/theme';

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const { lang, setLang } = useLang();
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    initTheme();
  }, []);

  return (
    <>
      <header className="bg-th-bg-secondary border-b-4 border-red-600 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="flex items-center justify-between">
            <a href="/" className="flex items-center gap-3">
              <div className="w-10 h-10 bg-red-600 rounded-lg flex items-center justify-center shadow-md shadow-red-900/50">
                <span className="text-yellow-300 font-black text-xl">TN</span>
              </div>
              <div>
                <h1 className="text-lg font-black text-th-text tracking-tight">
                  {t('site.title', lang)}
                </h1>
                <p className="text-[10px] text-yellow-500 font-semibold uppercase tracking-widest">
                  {t('site.subtitle', lang)}
                </p>
              </div>
            </a>
            <div className="flex items-center gap-3">
              <nav className="hidden sm:flex gap-4">
                <a
                  href="https://www.hatvp.fr"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-th-text-muted hover:text-yellow-500 transition-colors"
                >
                  HATVP
                </a>
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-th-text-muted hover:text-yellow-500 transition-colors"
                >
                  GitHub
                </a>
              </nav>
              {/* Theme toggle */}
              <button
                onClick={toggleTheme}
                className="flex items-center justify-center w-9 h-9 rounded-md border-2 border-th-border hover:border-yellow-500 text-th-text-muted hover:text-yellow-500 transition-colors"
                aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>
              {/* Language toggle */}
              <button
                onClick={() => setLang(lang === 'fr' ? 'en' : 'fr')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold border-2 border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-neutral-900 transition-colors"
                aria-label={lang === 'fr' ? 'Switch to English' : 'Passer en français'}
              >
                {lang === 'fr' ? 'EN' : 'FR'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="min-h-screen">
        {children}
      </main>

      <footer className="bg-th-bg-secondary border-t-4 border-red-600 py-8 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <p className="text-sm text-th-text-muted">
              {t('footer.copy', lang)}{' '}
              <a
                href="https://www.hatvp.fr"
                className="text-yellow-500 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t('footer.hatvp', lang)}
              </a>
            </p>
            <p className="text-xs text-th-text-muted mt-2">
              {t('footer.opensource', lang)}
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
