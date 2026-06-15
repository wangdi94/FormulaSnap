import { describe, it, expect, beforeEach } from 'vitest';
import { t, setLang, __resetLangCache, loadLang } from '../lib/i18n';

describe('i18n', () => {
  beforeEach(async () => {
    localStorage.clear();
    __resetLangCache();
    Object.defineProperty(navigator, 'language', {
      value: 'zh-CN',
      configurable: true,
      writable: true,
    });
    await loadLang('zh');
    await loadLang('en');
  });

  describe('t()', () => {
    it('返回中文翻译（当系统语言为中文时）', () => {
      expect(t('app.title')).toBe('FormulaSnap');
      expect(t('nav.home')).toBe('首页');
      expect(t('nav.history')).toBe('历史记录');
      expect(t('nav.settings')).toBe('设置');
    });

    it('返回英文翻译（当系统语言为英文时）', () => {
      Object.defineProperty(navigator, 'language', {
        value: 'en-US',
        configurable: true,
        writable: true,
      });
      __resetLangCache();
      expect(t('app.title')).toBe('FormulaSnap');
      expect(t('nav.home')).toBe('Home');
      expect(t('nav.history')).toBe('History');
      expect(t('nav.settings')).toBe('Settings');
    });

    it('localStorage language 优先于系统语言', () => {
      localStorage.setItem('language', 'en');
      __resetLangCache();
      // navigator.language is 'zh-CN' but localStorage overrides
      expect(t('nav.home')).toBe('Home');
    });

    it('对于不存在的 key 返回 key 本身', () => {
      // Using a type assertion to simulate an unknown key
      const unknownKey = 'nonexistent.key' as Parameters<typeof t>[0];
      expect(t(unknownKey)).toBe('nonexistent.key');
    });

    it('支持参数插值', () => {
      expect(t('history.time.minutes_ago', { n: 5 })).toBe('5 分钟前');
      expect(t('history.time.hours_ago', { n: 2 })).toBe('2 小时前');
    });

    it('英文模式下参数插值也正常', () => {
      Object.defineProperty(navigator, 'language', {
        value: 'en-US',
        configurable: true,
        writable: true,
      });
      __resetLangCache();
      expect(t('history.time.minutes_ago', { n: 5 })).toBe('5 minutes ago');
    });
  });

  describe('setLang()', () => {
    it('保存语言到 localStorage', () => {
      setLang('en');
      expect(localStorage.getItem('language')).toBe('en');
    });

    it('允许设置为中文', () => {
      setLang('zh');
      expect(localStorage.getItem('language')).toBe('zh');
    });
  });
});
