import { useState, useEffect, useCallback, useRef, startTransition } from 'react';
import type { AppSettings } from '../types/settings';
import { loadSettings, saveSettings, resetSettings } from '../lib/settings';
import { getStats, saveApiKey, getApiKeys, type StatsResponse } from '../lib/sidecarClient';
import { setLang, t } from '../lib/i18n';
import { Spinner } from '../components/Spinner';
import {
  ApiKeySection,
  API_KEY_FIELDS,
  PreferencesSection,
  normalizeModifiers,
  keyToReadable,
  StatsSection,
  AboutSection,
} from '../components/settings';

/* ─── 组件 ─── */
export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);
  const [recording, setRecording] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [configuredKeys, setConfiguredKeys] = useState<Record<string, boolean>>({});
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
    abortRef.current = new AbortController();

    setStatsError(null);
    const timeout = setTimeout(() => abortRef.current?.abort(), 5000);

    try {
      const result = await getStats();
      if (result === null) {
        setStatsError(t('settings.stats_unavailable'));
      } else {
        setStats(result);
      }
    } catch (e) {
      console.warn('Failed to load stats:', e);
      setStatsError(t('settings.stats_unavailable'));
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
        setLang('zh');
      })
      .finally(() => setLoading(false));
  }, []);

  /* ── 独立加载统计 ── */
  useEffect(() => {
    startTransition(() => {
      fetchStats();
    });
    return () => abortRef.current?.abort();
  }, [fetchStats]);

  /* ── 同步 sidecar key 状态 ── */
  useEffect(() => {
    getApiKeys()
      .then((resp) => {
        const map: Record<string, boolean> = {};
        for (const item of resp.keys) {
          map[item.backend] = item.configured;
        }
        setConfiguredKeys(map);
      })
      .catch((e) => console.warn('Failed to load key status:', e));
  }, []);

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
  const updateApiKey = (field: keyof NonNullable<AppSettings['api_keys']>, value: string) => {
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
      const keyErrors: string[] = [];
      for (const { key } of API_KEY_FIELDS) {
        const value = settings.api_keys?.[key];
        if (value) {
          try {
            await saveApiKey(key, value);
          } catch (e) {
            keyErrors.push(`${key}: ${String(e)}`);
          }
        }
      }

      const { api_keys: _ignored, ...settingsWithoutKeys } = settings;
      await saveSettings(settingsWithoutKeys);

      if (keyErrors.length > 0) {
        setSaveMsg(t('settings.save_partial', { errors: keyErrors.join(', ') }));
        setIsError(true);
      } else {
        setSaveMsg(t('settings.saved'));
        setIsError(false);
      }
      if (saveMsgTimeoutRef.current) clearTimeout(saveMsgTimeoutRef.current);
      saveMsgTimeoutRef.current = setTimeout(() => { setSaveMsg(null); setIsError(false); }, 2500);
    } catch (e) {
      setSaveMsg(t('settings.save_failed', { error: String(e) }));
      setIsError(true);
    } finally {
      setSaving(false);
    }
  };

  /* ── 加载中 ── */
  if (loading || !settings) {
    return (
      <div className="flex items-center justify-center h-full" role="status" aria-live="polite">
        <div className="flex items-center gap-3 text-gray-400 dark:text-gray-500">
          <Spinner title={t('common.loading')} />
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
      <ApiKeySection
        settings={settings}
        updateApiKey={updateApiKey}
        showKeys={showKeys}
        setShowKeys={setShowKeys}
        configuredKeys={configuredKeys}
      />

      {/* ━━━ 2. 偏好设置（后端、快捷键、预算） ━━━ */}
      <PreferencesSection
        settings={settings}
        setSettings={setSettings}
        recording={recording}
        setRecording={setRecording}
        handleRecordHotkey={handleRecordHotkey}
        hotkeyRef={hotkeyRef}
        stats={stats}
      />

      {/* ━━━ 3. 成本统计 ━━━ */}
      <StatsSection
        stats={stats}
        statsError={statsError}
        fetchStats={fetchStats}
      />

      {/* ━━━ 4. 关于 ━━━ */}
      <AboutSection />

      {/* ━━━ 底部操作栏 ━━━ */}
      <div className="sticky bottom-0 -mx-6 px-6 py-4 bg-gradient-to-t from-gray-50 via-gray-50 to-transparent
                      dark:from-gray-900 dark:via-gray-900 dark:to-transparent">
        <div className="flex items-center justify-between">
          <div className="text-sm">
            {saveMsg && (
              <span className={`transition-opacity ${isError ? 'text-red-500' : 'text-green-600 dark:text-green-400'}`}>
                {saveMsg}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={async () => {
                if (window.confirm(t('settings.reset_confirm'))) {
                  try {
                    const defaults = await resetSettings();
                    setSettings(defaults);
                    setSaveMsg(t('settings.reset_done'));
                    setIsError(false);
                    setTimeout(() => { setSaveMsg(null); setIsError(false); }, 2500);
                  } catch (e) {
                    console.warn('Failed to reset settings:', e);
                    setSaveMsg(t('settings.save_failed', { error: String(e) }));
                    setIsError(true);
                  }
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
                  <Spinner size="sm" title={t('settings.saving')} />
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
