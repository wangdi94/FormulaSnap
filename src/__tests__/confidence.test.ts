import { describe, it, expect } from 'vitest';
import { getConfidenceColor } from '../lib/confidence';

describe('getConfidenceColor', () => {
  it('null 返回灰色', () => {
    expect(getConfidenceColor(null)).toBe('text-gray-400');
  });

  it('undefined 返回灰色', () => {
    expect(getConfidenceColor(undefined)).toBe('text-gray-400');
  });

  it('>= 0.9 返回绿色', () => {
    expect(getConfidenceColor(0.9)).toBe('text-green-600');
    expect(getConfidenceColor(0.95)).toBe('text-green-600');
    expect(getConfidenceColor(1.0)).toBe('text-green-600');
  });

  it('>= 0.7 且 < 0.9 返回黄色', () => {
    expect(getConfidenceColor(0.7)).toBe('text-yellow-600');
    expect(getConfidenceColor(0.85)).toBe('text-yellow-600');
  });

  it('>= 0.5 且 < 0.7 返回橙色', () => {
    expect(getConfidenceColor(0.5)).toBe('text-orange-500');
    expect(getConfidenceColor(0.6)).toBe('text-orange-500');
  });

  it('< 0.5 返回灰色', () => {
    expect(getConfidenceColor(0.0)).toBe('text-gray-400');
    expect(getConfidenceColor(0.3)).toBe('text-gray-400');
    expect(getConfidenceColor(0.49)).toBe('text-gray-400');
  });
});
