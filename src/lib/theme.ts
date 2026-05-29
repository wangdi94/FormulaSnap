import type { Theme } from '../types/settings';

export type { Theme };

export function getTheme(): Theme {
  return (localStorage.getItem('theme') as Theme) || 'system';
}

export function setTheme(theme: Theme): void {
  localStorage.setItem('theme', theme);
  applyTheme(theme);
}

export function applyTheme(theme: Theme): void {
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', isDark);
}
