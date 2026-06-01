import zh from '../i18n/zh.json';
import en from '../i18n/en.json';

const translations = { zh, en } as const;

type Lang = keyof typeof translations;
export type TranslationKey = keyof typeof zh;

function detectLang(): Lang {
  const saved = localStorage.getItem('language');
  if (saved === 'zh' || saved === 'en') return saved;
  return navigator.language.startsWith('zh') ? 'zh' : 'en';
}

export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  const lang = detectLang();
  const langTranslations = translations[lang] as Record<string, string>;
  let text = langTranslations[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

export function getLang(): Lang {
  return detectLang();
}

export function setLang(lang: Lang): void {
  localStorage.setItem('language', lang);
}
