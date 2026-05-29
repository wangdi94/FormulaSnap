import { invoke } from '@tauri-apps/api/core';
import type { AppSettings } from '../types/settings';

const DEFAULT_SETTINGS: AppSettings = {
  hotkey: 'Ctrl+Shift+C',
  default_backend: 'auto',
  api_keys: {},
  theme: 'system',
  monthly_budget_usd: 10,
  language: 'zh',
};

/**
 * 从 Tauri 后端加载设置
 */
export async function loadSettings(): Promise<AppSettings> {
  try {
    const raw = await invoke<string | null>('get_setting', { key: 'app_settings' });
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    }
  } catch (e) {
    console.warn('Failed to load settings, using defaults:', e);
  }
  return { ...DEFAULT_SETTINGS };
}

/**
 * 保存设置到 Tauri 后端
 */
export async function saveSettings(settings: AppSettings): Promise<void> {
  await invoke('save_setting', {
    key: 'app_settings',
    value: JSON.stringify(settings),
  });
}

/**
 * 重置设置为默认值
 */
export async function resetSettings(): Promise<AppSettings> {
  await saveSettings(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS };
}
