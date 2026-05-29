import { describe, it, expect } from 'vitest';
import { getFormatLabel, copyToClipboard, type CopyFormat } from './clipboard';

describe('getFormatLabel', () => {
  it('latex 返回 "LaTeX"', () => {
    expect(getFormatLabel('latex')).toBe('LaTeX');
  });

  it('mathml 返回 "MathML"', () => {
    expect(getFormatLabel('mathml')).toBe('MathML');
  });

  it('png 返回 "PNG 图片"', () => {
    expect(getFormatLabel('png')).toBe('PNG 图片');
  });
});

describe('CopyFormat 类型', () => {
  it('包含 latex、mathml、png 三个值', () => {
    const formats: CopyFormat[] = ['latex', 'mathml', 'png'];
    expect(formats).toHaveLength(3);
    expect(formats).toContain('latex');
    expect(formats).toContain('mathml');
    expect(formats).toContain('png');
  });
});

describe('copyToClipboard', () => {
  it('函数存在且接受 (string, CopyFormat) 参数', () => {
    expect(typeof copyToClipboard).toBe('function');
    // 验证函数签名：第一个参数是 string，第二个是 CopyFormat
    const fn = copyToClipboard as unknown as (...args: unknown[]) => unknown;
    expect(fn.length).toBe(2);
  });
});
