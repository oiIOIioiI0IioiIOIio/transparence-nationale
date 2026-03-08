'use client';

import { create } from 'zustand';

export type Theme = 'light' | 'dark';

interface ThemeStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export const useTheme = create<ThemeStore>((set, get) => ({
  theme: 'light',
  setTheme: (theme) => {
    set({ theme });
    if (typeof window !== 'undefined') {
      localStorage.setItem('theme', theme);
      document.documentElement.classList.toggle('dark', theme === 'dark');
    }
  },
  toggleTheme: () => {
    const next = get().theme === 'light' ? 'dark' : 'light';
    get().setTheme(next);
  },
}));

/** Call once on mount to sync with localStorage / system preference */
export function initTheme() {
  if (typeof window === 'undefined') return;
  const stored = localStorage.getItem('theme') as Theme | null;
  const theme = stored || 'light';
  useTheme.getState().setTheme(theme);
}
