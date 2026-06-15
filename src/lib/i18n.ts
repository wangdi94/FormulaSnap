/**
 * i18n — 使用 import.meta.glob 按需加载翻译 JSON。
 * 桌面应用本地加载 chunk 瞬时完成，但可减小初始 bundle（~13KB 从主 chunk 分离）。
 */
type Lang = 'zh' | 'en';

const modules = import.meta.glob<{ default: Record<string, string> }>('/src/i18n/*.json', {
  eager: false,
});

const langLoaders: Record<Lang, () => Promise<{ default: Record<string, string> }>> = {
  zh: modules['/src/i18n/zh.json'] as () => Promise<{ default: Record<string, string> }>,
  en: modules['/src/i18n/en.json'] as () => Promise<{ default: Record<string, string> }>,
};

const cache: Partial<Record<Lang, Record<string, string>>> = {};
const loaded = new Set<Lang>();

let cachedLang: Lang | null = null;

export type TranslationKey = string;

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

export async function loadLang(lang: Lang): Promise<void> {
  if (loaded.has(lang)) return;
  const mod = await langLoaders[lang]();
  cache[lang] = mod.default;
  loaded.add(lang);
}

/**
 * 同步 t() — 翻译未加载时返回 key 作为 fallback 并触发异步加载。
 * 桌面应用 chunk 通过 file:// 加载几乎瞬时，fallback 窗口极短。
 */
export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  const lang = detectLang();
  const langTranslations = cache[lang];
  if (!langTranslations) {
    loadLang(lang);
    return applyParams(key, params);
  }
  const text = langTranslations[key] || key;
  return applyParams(text, params);
}

function applyParams(text: string, params?: Record<string, string | number>): string {
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

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
  loadLang(lang);
}

const _initialLang = detectLang();
loadLang(_initialLang);
