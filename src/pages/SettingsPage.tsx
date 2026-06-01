import { useState, useEffect, useCallback, useRef } from 'react';
import type { AppSettings } from '../types/settings';
import { loadSettings, saveSettings, resetSettings } from '../lib/settings';
import { getStats, type StatsResponse } from '../lib/sidecarClient';
import { setLang, t } from '../lib/i18n';
import { getBackendOptions } from '../lib/constants';

/* ─── API Key 字段定义 ─── */
const API_KEY_FIELDS: {
  key: keyof AppSettings['api_keys'];
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

/* ─── 快捷键辅助 ─── */
function formatHotkey(hotkey: string): string {
  return hotkey || t('settings.not_set');
}

function normalizeModifiers(e: KeyboardEvent): string[] {
  const mods: string[] = [];
  if (e.ctrlKey) mods.push('Ctrl');
  if (e.altKey) mods.push('Alt');
  if (e.shiftKey) mods.push('Shift');
  if (e.metaKey) mods.push('Super');
  return mods;
}

function keyToReadable(code: string): string {
  const map: Record<string, string> = {
    KeyA: 'A', KeyB: 'B', KeyC: 'C', KeyD: 'D', KeyE: 'E',
    KeyF: 'F', KeyG: 'G', KeyH: 'H', KeyI: 'I', KeyJ: 'J',
    KeyK: 'K', KeyL: 'L', KeyM: 'M', KeyN: 'N', KeyO: 'O',
    KeyP: 'P', KeyQ: 'Q', KeyR: 'R', KeyS: 'S', KeyT: 'T',
    KeyU: 'U', KeyV: 'V', KeyW: 'W', KeyX: 'X', KeyY: 'Y', KeyZ: 'Z',
    Digit0: '0', Digit1: '1', Digit2: '2', Digit3: '3', Digit4: '4',
    Digit5: '5', Digit6: '6', Digit7: '7', Digit8: '8', Digit9: '9',
    Space: 'Space', Enter: 'Enter', Escape: 'Escape', Tab: 'Tab',
    Backspace: 'Backspace', Delete: 'Delete',
    ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→',
    F1: 'F1', F2: 'F2', F3: 'F3', F4: 'F4', F5: 'F5', F6: 'F6',
    F7: 'F7', F8: 'F8', F9: 'F9', F10: 'F10', F11: 'F11', F12: 'F12',
  };
  return map[code] || code;
}

/* ─── 组件 ─── */
export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [statsError, setStatsError] = useState<string | null>(null);
  const hotkeyRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const saveMsgTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (saveMsgTimeoutRef.current) clearTimeout(saveMsgTimeoutRef.current);
    };
  }, []);

  /* ── 加载统计（带 5 秒超时） ── */
  const fetchStats = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatsError(null);
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const result = await getStats();
      if (!controller.signal.aborted) {
        if (result === null) {
          setStatsError(t('settings.stats_unavailable'));
        } else {
          setStats(result);
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        console.warn('Failed to load stats:', e);
        setStatsError(t('settings.stats_unavailable'));
      }
    } finally {
      clearTimeout(timeout);
    }
  }, []);

  /* ── 独立加载设置 ── */
  useEffect(() => {
    loadSettings()
      .then((s) => {
        setSettings(s);
        setLang(s.language);
      })
      .catch((e) => {
        console.warn('Failed to load settings, using defaults:', e);
        setSettings({
          hotkey: 'Ctrl+Shift+C',
          default_backend: 'auto',
          api_keys: {},
          theme: 'system',
          monthly_budget_usd: 10,
          language: 'zh',
        });
      })
      .finally(() => setLoading(false));
  }, []);

  /* ── 独立加载统计 ── */
  useEffect(() => {
    fetchStats();
    return () => abortRef.current?.abort();
  }, [fetchStats]);

  /* ── 快捷键录制 ── */
  const handleRecordHotkey = useCallback(() => {
    setRecording(true);
  }, []);

  useEffect(() => {
    if (!recording) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      // 忽略单独的修饰键
      if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) return;

      const mods = normalizeModifiers(e);
      const key = keyToReadable(e.code);
      if (mods.length === 0) return; // 至少需要一个修饰键

      const hotkey = [...mods, key].join('+');
      setSettings((prev) => prev ? { ...prev, hotkey } : prev);
      setRecording(false);
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [recording]);

  /* ── 更新 API Key ── */
  const updateApiKey = (field: keyof AppSettings['api_keys'], value: string) => {
    setSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        api_keys: { ...prev.api_keys, [field]: value },
      };
    });
  };

  /* ── 保存 ── */
  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await saveSettings(settings);
      setSaveMsg(t('settings.saved'));
      if (saveMsgTimeoutRef.current) clearTimeout(saveMsgTimeoutRef.current);
      saveMsgTimeoutRef.current = setTimeout(() => setSaveMsg(null), 2500);
    } catch (e) {
      setSaveMsg(t('settings.save_failed', { error: String(e) }));
    } finally {
      setSaving(false);
    }
  };

  /* ── 加载中 ── */
  if (loading || !settings) {
    return (
      <div className="flex items-center justify-center h-full" role="status" aria-live="polite">
        <div className="flex items-center gap-3 text-gray-400 dark:text-gray-500">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <title>{t('common.loading')}</title>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span>{t('settings.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
      {/* ── 标题 ── */}
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">{t('settings.page_title')}</h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {t('settings.description')}
        </p>
      </div>

      {/* ━━━ 1. API Key 管理 ━━━ */}
      <Section title={t('settings.api_key_management')} description={t('settings.api_key_description')}>
        <div className="space-y-4">
          {API_KEY_FIELDS.map(({ key, label, placeholder, link }) => (
            <div key={key}>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor={`apikey-${key}`} className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  {label}
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
                  value={settings.api_keys[key] || ''}
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

      {/* ━━━ 2. 后端选择 ━━━ */}
      <Section title={t('settings.recognition_backend')} description={t('settings.backend_description')} icon="⚡">
        <div>
          <label htmlFor="default-backend" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            {t('settings.default_backend')}
          </label>
          <select
            id="default-backend"
            value={settings.default_backend}
            onChange={(e) =>
              setSettings((prev) => prev ? { ...prev, default_backend: e.target.value as AppSettings['default_backend'] } : prev)
            }
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg
                       bg-white dark:bg-gray-700 text-gray-900 dark:text-white
                       focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                       dark:focus:ring-blue-400 dark:focus:border-blue-400
                       transition-colors text-sm"
          >
            {getBackendOptions().map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
          {settings.default_backend === 'auto' && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {t('settings.auto_mode_hint')}
            </p>
          )}
        </div>
      </Section>

      {/* ━━━ 3. 快捷键配置 ━━━ */}
      <Section title={t('settings.hotkey_section')} description={t('settings.hotkey_description')} icon="⌨️">
        <div>
          <label htmlFor="hotkey-display" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            {t('settings.capture_hotkey')}
          </label>
          <div className="flex items-center gap-3" ref={hotkeyRef}>
            <div
              id="hotkey-display"
              role="status"
              aria-live="polite"
              className={`flex-1 px-3 py-2 border rounded-lg text-sm font-mono text-center
                ${recording
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 ring-2 ring-blue-500/30'
                  : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white'
                } transition-all`}
            >
              {recording ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  {t('settings.press_hotkey')}
                </span>
              ) : (
                formatHotkey(settings.hotkey)
              )}
            </div>
            <button
              type="button"
              onClick={recording ? () => setRecording(false) : handleRecordHotkey}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors
                ${recording
                  ? 'bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
                }`}
            >
              {recording ? t('common.cancel') : t('settings.record')}
            </button>
            <button
              type="button"
              onClick={() => setSettings((prev) => prev ? { ...prev, hotkey: 'Ctrl+Shift+C' } : prev)}
              className="px-4 py-2 rounded-lg text-sm font-medium
                         bg-gray-100 text-gray-700 hover:bg-gray-200
                         dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600
                         transition-colors"
            >
              {t('settings.reset')}
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            {t('settings.hotkey_default_hint', { hotkey: navigator.userAgent.includes('Mac') ? 'Cmd+Shift+C' : 'Ctrl+Shift+C' })}
          </p>
        </div>
      </Section>

      {/* ━━━ 4. 成本统计 ━━━ */}
      <Section title={t('settings.cost_stats')} description={t('settings.cost_description')} icon="📊">
        {stats ? (
          <div className="grid grid-cols-3 gap-4">
            <StatCard label={t('settings.total_calls')} value={stats.total_calls.toLocaleString()} unit={t('settings.calls_unit')} />
            <StatCard label={t('settings.total_tokens')} value={stats.total_tokens.toLocaleString()} unit="tokens" />
            <StatCard
              label={t('settings.estimated_cost')}
              value={`$${stats.estimated_cost_usd.toFixed(2)}`}
              unit="USD"
              highlight={stats.estimated_cost_usd > 0}
            />
          </div>
        ) : statsError ? (
          <div className="flex items-center justify-between text-sm">
            <span className="text-red-500 dark:text-red-400">{statsError}</span>
            <button
              type="button"
              onClick={fetchStats}
              className="px-3 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
            >
              {t('common.retry')}
            </button>
          </div>
        ) : (
          <div className="text-sm text-gray-400 dark:text-gray-500">{t('settings.loading_stats')}</div>
        )}
      </Section>

      {/* ━━━ 5. 月度预算 ━━━ */}
      <Section title={t('settings.monthly_budget')} description={t('settings.budget_description')} icon="💰">
        <div>
          <div className="flex items-center justify-between mb-2">
            <label htmlFor="budget-slider" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {t('settings.budget_limit')}
            </label>
            <span className="text-sm font-mono font-semibold text-gray-900 dark:text-white">
              ${settings.monthly_budget_usd.toFixed(2)}
            </span>
          </div>
          <input
            id="budget-slider"
            type="range"
            min={0}
            max={100}
            step={1}
            value={settings.monthly_budget_usd}
            onChange={(e) =>
              setSettings((prev) => prev ? { ...prev, monthly_budget_usd: Number(e.target.value) } : prev)
            }
            className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer
                       accent-blue-500 dark:accent-blue-400"
          />
          <div className="flex justify-between mt-1 text-xs text-gray-400 dark:text-gray-500">
            <span>{t('settings.budget_min')}</span>
            <span>{t('settings.budget_max')}</span>
          </div>
          {stats && stats.estimated_cost_usd > 0 && settings.monthly_budget_usd > 0 && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                <span>{t('settings.used')}</span>
                <span>{Math.min(100, (stats.estimated_cost_usd / settings.monthly_budget_usd) * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    (stats.estimated_cost_usd / settings.monthly_budget_usd) > 0.8
                      ? 'bg-red-500'
                      : (stats.estimated_cost_usd / settings.monthly_budget_usd) > 0.5
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.min(100, (stats.estimated_cost_usd / settings.monthly_budget_usd) * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </Section>

      {/* ━━━ 底部操作栏 ━━━ */}
      <div className="sticky bottom-0 -mx-6 px-6 py-4 bg-gradient-to-t from-gray-50 via-gray-50 to-transparent
                      dark:from-gray-900 dark:via-gray-900 dark:to-transparent">
        <div className="flex items-center justify-between">
          <div className="text-sm">
            {saveMsg && (
              <span className={`transition-opacity ${saveMsg.includes(t('settings.save_failed', { error: '' }).replace(': ', '')) ? 'text-red-500' : 'text-green-600 dark:text-green-400'}`}>
                {saveMsg}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={async () => {
                if (window.confirm(t('settings.reset_confirm'))) {
                  const defaults = await resetSettings();
                  setSettings(defaults);
                  setSaveMsg(t('settings.reset_done'));
                  setTimeout(() => setSaveMsg(null), 2500);
                }
              }}
              className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400
                         hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            >
              {t('settings.reset_default')}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400
                         text-white text-sm font-medium rounded-lg
                         focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                         dark:focus:ring-offset-gray-900
                         transition-colors disabled:cursor-not-allowed"
            >
              {saving ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <title>{t('settings.saving')}</title>
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {t('settings.saving')}
                </span>
              ) : (
                t('settings.save_settings')
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ━━━ 子组件 ━━━ */

function Section({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description: string;
  icon?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          {icon && <span>{icon}</span>}
          {title}
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>
      </div>
      {children}
    </section>
  );
}

function StatCard({
  label,
  value,
  unit,
  highlight,
}: {
  label: string;
  value: string;
  unit: string;
  highlight?: boolean;
}) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
      <div className={`text-lg font-semibold font-mono ${highlight ? 'text-blue-600 dark:text-blue-400' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        {label}
        <span className="ml-1 text-gray-400 dark:text-gray-500">{unit}</span>
      </div>
    </div>
  );
}

function EyeIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <title>{t('settings.show_key')}</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <title>{t('settings.hide_key')}</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  );
}
