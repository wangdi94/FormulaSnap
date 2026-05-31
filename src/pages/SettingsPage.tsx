import { useState, useEffect, useCallback, useRef } from 'react';
import type { AppSettings } from '../types/settings';
import { loadSettings, saveSettings, resetSettings } from '../lib/settings';
import { getStats, type StatsResponse } from '../lib/sidecarClient';
import { setLang } from '../lib/i18n';

/* ─── 后端选项 ─── */
const BACKENDS = [
  { value: 'auto', label: '自动选择' },
  { value: 'pix2text', label: 'Pix2Text（本地）' },
  { value: 'mathpix', label: 'Mathpix' },
  { value: 'openai', label: 'OpenAI GPT-4o' },
  { value: 'claude', label: 'Claude' },
  { value: 'gemini', label: 'Gemini' },
] as const;

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
  return hotkey || '未设置';
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
          setStatsError('统计数据不可用');
        } else {
          setStats(result);
        }
      }
    } catch (e) {
      if (!controller.signal.aborted) {
        console.warn('Failed to load stats:', e);
        setStatsError('统计数据不可用');
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
      setSaveMsg('设置已保存');
      if (saveMsgTimeoutRef.current) clearTimeout(saveMsgTimeoutRef.current);
      saveMsgTimeoutRef.current = setTimeout(() => setSaveMsg(null), 2500);
    } catch (e) {
      setSaveMsg(`保存失败: ${e}`);
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
            <title>加载中</title>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span>加载设置中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
      {/* ── 标题 ── */}
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">设置</h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          管理 API 密钥、识别后端和应用偏好
        </p>
      </div>

      {/* ━━━ 1. API Key 管理 ━━━ */}
      <Section title="API Key 管理" description="配置各识别引擎的 API 凭证。密钥仅存储在本地，不会上传。">
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
                    获取密钥 ↗
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
                  aria-label={showKeys[key] ? '隐藏密钥' : '显示密钥'}
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
      <Section title="识别后端" description="选择默认的数学公式识别引擎。" icon="⚡">
        <div>
          <label htmlFor="default-backend" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            默认后端
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
            {BACKENDS.map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
          {settings.default_backend === 'auto' && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              自动模式将优先使用本地 Pix2Text，失败时回退到已配置的云端服务。
            </p>
          )}
        </div>
      </Section>

      {/* ━━━ 3. 快捷键配置 ━━━ */}
      <Section title="快捷键" description="自定义截图识别的全局快捷键。" icon="⌨️">
        <div>
          <label htmlFor="hotkey-display" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            截图快捷键
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
                  按下快捷键组合...
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
              {recording ? '取消' : '录制'}
            </button>
            <button
              type="button"
              onClick={() => setSettings((prev) => prev ? { ...prev, hotkey: 'Ctrl+Shift+C' } : prev)}
              className="px-4 py-2 rounded-lg text-sm font-medium
                         bg-gray-100 text-gray-700 hover:bg-gray-200
                         dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600
                         transition-colors"
            >
              重置
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
            默认：{navigator.userAgent.includes('Mac') ? 'Cmd+Shift+C' : 'Ctrl+Shift+C'}。需包含至少一个修饰键（Ctrl/Alt/Shift/Super）。
          </p>
        </div>
      </Section>

      {/* ━━━ 4. 成本统计 ━━━ */}
      <Section title="成本统计" description="本月 API 调用情况。" icon="📊">
        {stats ? (
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="调用次数" value={stats.total_calls.toLocaleString()} unit="次" />
            <StatCard label="总 Tokens" value={stats.total_tokens.toLocaleString()} unit="tokens" />
            <StatCard
              label="预估成本"
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
              重试
            </button>
          </div>
        ) : (
          <div className="text-sm text-gray-400 dark:text-gray-500">加载统计中...</div>
        )}
      </Section>

      {/* ━━━ 5. 月度预算 ━━━ */}
      <Section title="月度预算" description="设置每月 API 调用的费用上限。" icon="💰">
        <div>
          <div className="flex items-center justify-between mb-2">
            <label htmlFor="budget-slider" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              预算上限
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
            <span>$0（禁用云端）</span>
            <span>$100/月</span>
          </div>
          {stats && stats.estimated_cost_usd > 0 && settings.monthly_budget_usd > 0 && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
                <span>已使用</span>
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
              <span className={`transition-opacity ${saveMsg.includes('失败') ? 'text-red-500' : 'text-green-600 dark:text-green-400'}`}>
                {saveMsg}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={async () => {
                if (window.confirm('确定要重置所有设置为默认值吗？')) {
                  const defaults = await resetSettings();
                  setSettings(defaults);
                  setSaveMsg('已重置为默认设置');
                  setTimeout(() => setSaveMsg(null), 2500);
                }
              }}
              className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400
                         hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
            >
              重置默认
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
                    <title>保存中</title>
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  保存中...
                </span>
              ) : (
                '保存设置'
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
      <title>显示</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <title>隐藏</title>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
    </svg>
  );
}
