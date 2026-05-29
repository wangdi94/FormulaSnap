import zh from '../i18n/zh.json';
import en from '../i18n/en.json';

const translations = { zh, en } as const;

type Lang = keyof typeof translations;
type TranslationKey = keyof typeof zh;

function detectLang(): Lang {
  const saved = localStorage.getItem('language');
  if (saved === 'zh' || saved === 'en') return saved;
  return navigator.language.startsWith('zh') ? 'zh' : 'en';
}

export function t(key: TranslationKey): string {
  const lang = detectLang();
  return translations[lang][key] || key;
}

export function getLang(): Lang {
  return detectLang();
}

export function setLang(lang: Lang): void {
  localStorage.setItem('language', lang);
}
