import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockInvoke = vi.fn();

vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => mockInvoke(...args),
}));

import { loadSettings, saveSettings, resetSettings } from '../lib/settings';

describe('settings', () => {
  beforeEach(() => {
    mockInvoke.mockReset();
  });

  describe('loadSettings', () => {
    it('后端返回有效 JSON 时合并默认设置', async () => {
      const stored = JSON.stringify({ hotkey: 'Alt+X', theme: 'dark' });
      mockInvoke.mockResolvedValueOnce(stored);

      const result = await loadSettings();
      expect(result.hotkey).toBe('Alt+X');
      expect(result.theme).toBe('dark');
      expect(result.default_backend).toBe('auto'); // 默认值
    });

    it('后端返回 null 时使用默认设置', async () => {
      mockInvoke.mockResolvedValueOnce(null);

      const result = await loadSettings();
      expect(result.hotkey).toBe('Ctrl+Shift+C');
      expect(result.default_backend).toBe('auto');
      expect(result.theme).toBe('system');
      expect(result.monthly_budget_usd).toBe(10);
    });

    it('invoke 抛出异常时回退到默认设置', async () => {
      mockInvoke.mockRejectedValueOnce(new Error('connection failed'));

      const result = await loadSettings();
      expect(result.hotkey).toBe('Ctrl+Shift+C');
      expect(result.default_backend).toBe('auto');
    });

    it('调用 get_setting 命令并传入正确 key', async () => {
      mockInvoke.mockResolvedValueOnce(null);
      await loadSettings();
      expect(mockInvoke).toHaveBeenCalledWith('get_setting', { key: 'app_settings' });
    });
  });

  describe('saveSettings', () => {
    it('调用 save_setting 命令并序列化设置', async () => {
      mockInvoke.mockResolvedValueOnce(undefined);
      const settings = {
        hotkey: 'Ctrl+Shift+C',
        default_backend: 'auto' as const,
        api_keys: {},
        theme: 'system' as const,
        monthly_budget_usd: 10,
        language: 'zh' as const,
      };

      await saveSettings(settings);
      expect(mockInvoke).toHaveBeenCalledWith('save_setting', {
        key: 'app_settings',
        value: JSON.stringify(settings),
      });
    });
  });

  describe('resetSettings', () => {
    it('重置后返回默认设置并调用 saveSettings', async () => {
      mockInvoke.mockResolvedValueOnce(undefined); // saveSettings

      const result = await resetSettings();
      expect(result.hotkey).toBe('Ctrl+Shift+C');
      expect(result.default_backend).toBe('auto');
      expect(result.theme).toBe('system');
      expect(result.monthly_budget_usd).toBe(10);
      expect(mockInvoke).toHaveBeenCalledWith('save_setting', expect.any(Object));
    });
  });
});
