import { t, type TranslationKey } from './i18n';

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

export function getBackendOptions(): Array<{ value: string; label: string }> {
  return [
    { value: 'auto', label: t('backend.auto') },
    ...Object.entries(BACKEND_I18N_KEYS).map(([value, key]) => ({
      value,
      label: t(key),
    })),
  ];
}
