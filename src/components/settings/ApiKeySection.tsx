import { memo } from 'react';
import type { AppSettings } from '../../types/settings';
import { t } from '../../lib/i18n';
import { Section } from './Section';

/* ─── API Key 字段定义 ─── */
export const API_KEY_FIELDS: {
  key: keyof NonNullable<AppSettings['api_keys']>;
  label: string;
  placeholder: string;
  link?: string;
}[] = [
  { key: 'openai', label: 'OpenAI API Key', placeholder: 'sk-...', link: 'https://platform.openai.com/api-keys' },
  { key: 'claude', label: 'Claude API Key', placeholder: 'sk-ant-...', link: 'https://console.anthropic.com/settings/keys' },
  { key: 'gemini', label: 'Gemini API Key', placeholder: 'AIza...', link: 'https://aistudio.google.com/app/apikey' },
  { key: 'mathpix_app_id', label: 'Mathpix App ID', placeholder: 'app_id' },
  { key: 'mathpix_app_key', label: 'Mathpix App Key', placeholder: 'app_key' },
];

/* ─── 图标 ─── */
const EyeIcon = memo(function EyeIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <title>{t('settings.show_key')}</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );
});

const EyeOffIcon = memo(function EyeOffIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <title>{t('settings.hide_key')}</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  );
});

/* ─── 组件 ─── */
interface ApiKeySectionProps {
  settings: AppSettings;
  updateApiKey: (field: keyof NonNullable<AppSettings['api_keys']>, value: string) => void;
  showKeys: Record<string, boolean>;
  setShowKeys: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  configuredKeys: Record<string, boolean>;
}

export const ApiKeySection = memo(function ApiKeySection({
  settings,
  updateApiKey,
  showKeys,
  setShowKeys,
  configuredKeys,
}: ApiKeySectionProps) {
  return (
    <Section title={t('settings.api_key_management')} description={t('settings.api_key_description')}>
      <div className="space-y-4">
        {API_KEY_FIELDS.map(({ key, label, placeholder, link }) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor={`apikey-${key}`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                {label}
                {configuredKeys[key] && (
                  <span className="ml-2 inline-flex items-center px-1.5 py-0.5 text-xs font-medium rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                    {t('settings.key_configured')}
                  </span>
                )}
              </label>
              {link && (
                <a
                  href={link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
                >
                  {t('settings.get_key')}
                </a>
              )}
            </div>
            <div className="relative">
              <input
                id={`apikey-${key}`}
                type={showKeys[key] ? 'text' : 'password'}
                value={settings.api_keys?.[key] || ''}
                onChange={(e) => updateApiKey(key, e.target.value)}
                placeholder={placeholder}
                className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg
                           bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                           placeholder-gray-400 dark:placeholder-gray-500
                           focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                           dark:focus:ring-blue-400 dark:focus:border-blue-400
                           transition-colors text-sm font-mono"
                autoComplete="off"
                spellCheck={false}
              />
              <button
                type="button"
                onClick={() => setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600
                           dark:hover:text-gray-300 transition-colors"
                aria-label={showKeys[key] ? t('settings.hide_key') : t('settings.show_key')}
              >
                {showKeys[key] ? (
                  <EyeOffIcon />
                ) : (
                  <EyeIcon />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
});
