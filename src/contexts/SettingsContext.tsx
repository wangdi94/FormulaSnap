import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import type { AppSettings } from '../types/settings';
import { loadSettings, saveSettings as saveSettingsToBackend } from '../lib/settings';

/** 应用启动时的默认设置（与 settings.ts 中保持一致） */
const DEFAULT_SETTINGS: AppSettings = {
  hotkey: 'Ctrl+Shift+C',
  default_backend: 'auto',
  api_keys: {},
  theme: 'system',
  monthly_budget_usd: 10,
  language: 'zh',
};

interface SettingsContextValue {
  /** 当前设置（加载完成前为默认值） */
  settings: AppSettings;
  /** 是否正在从后端加载设置 */
  loading: boolean;
  /** 从后端重新加载设置 */
  refreshSettings: () => Promise<void>;
  /** 局部更新设置（仅更新本地状态，不持久化） */
  updateSettings: (partial: Partial<AppSettings>) => void;
  /** 保存设置到后端 */
  saveSettings: (settings: AppSettings) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

interface SettingsProviderProps {
  children: ReactNode;
}

export function SettingsProvider({ children }: SettingsProviderProps) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);

  const refreshSettings = useCallback(async () => {
    try {
      const loaded = await loadSettings();
      setSettings(loaded);
    } catch (e) {
      console.warn('Failed to load settings, using defaults:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load on mount — refreshSettings calls setState but that's
  // the intended pattern for reading external state (Tauri backend)
  useEffect(() => { refreshSettings(); }, [refreshSettings]); // eslint-disable-line react-hooks/set-state-in-effect

  const updateSettings = useCallback((partial: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...partial }));
  }, []);

  const save = useCallback(async (newSettings: AppSettings) => {
    await saveSettingsToBackend(newSettings);
    setSettings(newSettings);
  }, []);

  const value = useMemo<SettingsContextValue>(
    () => ({ settings, loading, refreshSettings, updateSettings, saveSettings: save }),
    [settings, loading, refreshSettings, updateSettings, save],
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

/**
 * 获取设置上下文。
 * 必须在 SettingsProvider 内部使用。
 */
export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return ctx;
}
