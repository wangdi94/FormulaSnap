import { describe, it, expect, vi } from 'vitest';

vi.mock('../lib/i18n', () => ({
  t: (key: string) => key,
}));

import { TIMEOUT, getBackendLabel, getBackendOptions } from '../lib/constants';

describe('constants', () => {
  describe('TIMEOUT', () => {
    it('截图捕获超时为 15 秒', () => {
      expect(TIMEOUT.SCREENSHOT_CAPTURE).toBe(15_000);
    });

    it('OCR 识别超时为 30 秒', () => {
      expect(TIMEOUT.OCR).toBe(30_000);
    });

    it('Sidecar 统计查询超时为 5 秒', () => {
      expect(TIMEOUT.SIDECAR_STATS).toBe(5_000);
    });

    it('Sidecar 健康检查超时为 3 秒', () => {
      expect(TIMEOUT.SIDECAR_HEALTH).toBe(3_000);
    });
  });

  describe('getBackendLabel', () => {
    it('已知后端返回 i18n key', () => {
      expect(getBackendLabel('pix2text')).toBe('backend.pix2text');
      expect(getBackendLabel('mathpix')).toBe('backend.mathpix');
      expect(getBackendLabel('openai')).toBe('backend.openai');
      expect(getBackendLabel('claude')).toBe('backend.claude');
      expect(getBackendLabel('gemini')).toBe('backend.gemini');
    });

    it('未知后端返回原始字符串', () => {
      expect(getBackendLabel('unknown_backend')).toBe('unknown_backend');
    });
  });

  describe('getBackendOptions', () => {
    it('返回 auto 加上所有后端选项', () => {
      const options = getBackendOptions();
      expect(options).toHaveLength(6);
      expect(options[0]).toEqual({ value: 'auto', label: 'backend.auto' });
    });

    it('每个选项包含 value 和 label', () => {
      const options = getBackendOptions();
      for (const opt of options) {
        expect(opt).toHaveProperty('value');
        expect(opt).toHaveProperty('label');
        expect(typeof opt.value).toBe('string');
        expect(typeof opt.label).toBe('string');
      }
    });

    it('包含 pix2text、mathpix、openai、claude、gemini', () => {
      const values = getBackendOptions().map((o) => o.value);
      expect(values).toContain('pix2text');
      expect(values).toContain('mathpix');
      expect(values).toContain('openai');
      expect(values).toContain('claude');
      expect(values).toContain('gemini');
    });
  });
});
