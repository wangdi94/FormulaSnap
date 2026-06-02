import zh from '../i18n/zh.json';
import en from '../i18n/en.json';

const translations = { zh, en } as const;

type Lang = keyof typeof translations;
export type TranslationKey = keyof typeof zh;

let cachedLang: Lang | null = null;

function detectLang(): Lang {
  if (cachedLang) return cachedLang;
  const saved = localStorage.getItem('language');
  if (saved === 'zh' || saved === 'en') {
    cachedLang = saved;
    return saved;
  }
  cachedLang = navigator.language.startsWith('zh') ? 'zh' : 'en';
  return cachedLang;
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

/** 将语言代码映射为 Intl 使用的 locale 字符串 */
export function getLocale(): string {
  const lang = detectLang();
  return lang === 'zh' ? 'zh-CN' : 'en-US';
}

/** @internal 仅用于测试 */
export function __resetLangCache(): void {
  cachedLang = null;
}

export function setLang(lang: Lang): void {
  localStorage.setItem('language', lang);
  cachedLang = lang;
}
