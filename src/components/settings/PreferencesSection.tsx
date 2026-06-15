import { memo } from 'react';
import type { AppSettings } from '../../types/settings';
import type { StatsResponse } from '../../lib/sidecarClient';
import { t } from '../../lib/i18n';
import { getBackendOptions } from '../../lib/constants';
import { Section } from './Section';

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

/* ─── 导出辅助函数供 SettingsPage 使用 ─── */
export { normalizeModifiers, keyToReadable };

/* ─── 组件 ─── */
interface PreferencesSectionProps {
  settings: AppSettings;
  setSettings: React.Dispatch<React.SetStateAction<AppSettings | null>>;
  recording: boolean;
  setRecording: React.Dispatch<React.SetStateAction<boolean>>;
  handleRecordHotkey: () => void;
  hotkeyRef: React.RefObject<HTMLDivElement | null>;
  stats: StatsResponse | null;
}

export const PreferencesSection = memo(function PreferencesSection({
  settings,
  setSettings,
  recording,
  setRecording,
  handleRecordHotkey,
  hotkeyRef,
  stats,
}: PreferencesSectionProps) {
  return (
    <>
      {/* ━━━ 后端选择 ━━━ */}
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

      {/* ━━━ 快捷键配置 ━━━ */}
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

      {/* ━━━ 月度预算 ━━━ */}
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
    </>
  );
});
