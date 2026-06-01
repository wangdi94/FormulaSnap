import { t, type TranslationKey } from './i18n';

export const BACKEND_LABELS: Record<string, string> = {
  pix2text: "Pix2Text（本地）",
  mathpix: "Mathpix",
  openai: "OpenAI GPT-4o",
  claude: "Claude",
  gemini: "Gemini",
};

const BACKEND_I18N_KEYS: Record<string, TranslationKey> = {
  pix2text: 'backend.pix2text',
  mathpix: 'backend.mathpix',
  openai: 'backend.openai',
  claude: 'backend.claude',
  gemini: 'backend.gemini',
};

export function getBackendLabel(backend: string): string {
  const key = BACKEND_I18N_KEYS[backend];
  return key ? t(key) : backend;
}

export const BACKENDS: Array<{ value: string; label: string }> = [
  { value: 'auto', label: '自动选择' },
  ...Object.entries(BACKEND_LABELS).map(([value, label]) => ({ value, label })),
];

export function getBackendOptions(): Array<{ value: string; label: string }> {
  return [
    { value: 'auto', label: t('backend.auto') },
    ...Object.entries(BACKEND_I18N_KEYS).map(([value, key]) => ({
      value,
      label: t(key),
    })),
  ];
}
