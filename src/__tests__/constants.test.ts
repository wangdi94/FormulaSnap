import { describe, it, expect } from 'vitest';
import { BACKEND_LABELS, BACKENDS } from '../lib/constants';

describe('BACKEND_LABELS', () => {
  it('包含全部 5 个后端', () => {
    expect(Object.keys(BACKEND_LABELS)).toHaveLength(5);
    expect(BACKEND_LABELS).toHaveProperty('pix2text');
    expect(BACKEND_LABELS).toHaveProperty('mathpix');
    expect(BACKEND_LABELS).toHaveProperty('openai');
    expect(BACKEND_LABELS).toHaveProperty('claude');
    expect(BACKEND_LABELS).toHaveProperty('gemini');
  });

  it('pix2text 标签为中文以标明本地', () => {
    expect(BACKEND_LABELS.pix2text).toBe('Pix2Text（本地）');
  });

  it('所有标签均为合法字符串', () => {
    for (const label of Object.values(BACKEND_LABELS)) {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

describe('BACKENDS', () => {
  it('包含 6 个选项（auto + 5 后端）', () => {
    expect(BACKENDS).toHaveLength(6);
  });

  it('第一项为 auto 自动选择', () => {
    expect(BACKENDS[0]).toEqual({ value: 'auto', label: '自动选择' });
  });

  it('后续项与 BACKEND_LABELS 对应', () => {
    for (const [value, label] of Object.entries(BACKEND_LABELS)) {
      expect(BACKENDS).toContainEqual({ value, label });
    }
  });

  it('每项均有 value 和 label', () => {
    for (const item of BACKENDS) {
      expect(item).toHaveProperty('value');
      expect(item).toHaveProperty('label');
      expect(typeof item.value).toBe('string');
      expect(typeof item.label).toBe('string');
    }
  });
});
