import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getTheme, setTheme, applyTheme } from '../lib/theme';

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    // Default: light mode for prefers-color-scheme
    Object.defineProperty(window, 'matchMedia', {
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
      writable: true,
      configurable: true,
    });
  });

  describe('getTheme()', () => {
    it('返回默认值 system', () => {
      expect(getTheme()).toBe('system');
    });

    it('返回 localStorage 中保存的值', () => {
      localStorage.setItem('theme', 'dark');
      expect(getTheme()).toBe('dark');
    });

    it('返回 light 当已设置', () => {
      localStorage.setItem('theme', 'light');
      expect(getTheme()).toBe('light');
    });
  });

  describe('applyTheme()', () => {
    it('light 主题不添加 dark class', () => {
      applyTheme('light');
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    it('dark 主题添加 dark class', () => {
      applyTheme('dark');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    it('system 主题跟随 prefers-color-scheme（深色时添加 dark class）', () => {
      Object.defineProperty(window, 'matchMedia', {
        value: vi.fn().mockImplementation((query: string) => ({
          matches: true, // dark mode
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
        writable: true,
        configurable: true,
      });
      applyTheme('system');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    it('system 主题跟随 prefers-color-scheme（浅色时不添加 dark class）', () => {
      // matchMedia already returns matches: false from beforeEach
      applyTheme('system');
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
  });

  describe('setTheme()', () => {
    it('保存主题到 localStorage 并应用', () => {
      setTheme('dark');
      expect(localStorage.getItem('theme')).toBe('dark');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    it('切换到 light 移除 dark class', () => {
      setTheme('dark');
      expect(document.documentElement.classList.contains('dark')).toBe(true);
      setTheme('light');
      expect(localStorage.getItem('theme')).toBe('light');
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
  });
});
