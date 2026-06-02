import { describe, it, expect, vi, beforeAll, afterAll, beforeEach } from 'vitest';
import type { CopyFormat } from './clipboard';

// Mock Tauri clipboard plugin (unavailable in JSDOM)
vi.mock('@tauri-apps/plugin-clipboard-manager', () => ({
  writeText: vi.fn().mockResolvedValue(undefined),
  writeImage: vi.fn().mockResolvedValue(undefined),
}));

describe('CopyFormat 类型', () => {
  it('包含 latex、mathml、png 三个值', () => {
    const formats: CopyFormat[] = ['latex', 'mathml', 'png'];
    expect(formats).toHaveLength(3);
    expect(formats).toContain('latex');
    expect(formats).toContain('mathml');
    expect(formats).toContain('png');
  });
});

// Override Image constructor so SVG blob URLs settle immediately in JSDOM
const OriginalImage = globalThis.Image;

beforeAll(() => {
  const MockImage = function (
    width?: number,
    height?: number,
  ): HTMLImageElement {
    const img = new OriginalImage(width, height) as HTMLImageElement;
    const origDescriptor = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(img),
      'src',
    );
    if (origDescriptor?.set) {
      const origSet = origDescriptor.set;
      Object.defineProperty(img, 'src', {
        set(value: string) {
          origSet.call(img, value);
          queueMicrotask(() => {
            if (typeof img.naturalWidth === 'undefined' || img.naturalWidth === 0) {
              Object.defineProperties(img, {
                naturalWidth: { value: 200, configurable: true },
                naturalHeight: { value: 50, configurable: true },
              });
            }
            img.dispatchEvent(new Event('load'));
          });
        },
        configurable: true,
      });
    }
    return img;
  };
  MockImage.prototype = OriginalImage.prototype;
  globalThis.Image = MockImage as unknown as typeof Image;
});

afterAll(() => {
  globalThis.Image = OriginalImage;
});

describe('copyToClipboard', () => {
  it('函数存在且接受 (string, CopyFormat) 参数', async () => {
    const { copyToClipboard } = await import('./clipboard');
    expect(typeof copyToClipboard).toBe('function');
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('latex 格式复制原始文本', async () => {
    const { copyToClipboard } = await import('./clipboard');
    const { writeText } = await import('@tauri-apps/plugin-clipboard-manager');
    await copyToClipboard('E=mc^2', 'latex');
    expect(writeText).toHaveBeenCalledWith('E=mc^2');
  });

  it('mathml 格式通过 convertLatexToMathMl 转换后复制', async () => {
    const { copyToClipboard } = await import('./clipboard');
    const { writeText } = await import('@tauri-apps/plugin-clipboard-manager');
    await copyToClipboard('E=mc^2', 'mathml');
    expect(writeText).toHaveBeenCalled();
    const callArg = (writeText as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(typeof callArg).toBe('string');
    // convertLatexToMathMl 返回 MathML 片段（如 <mrow>...</mrow>）
    expect(callArg).toMatch(/<[a-z]+>/);
  });

  it('png 格式不产生损坏输出（回退到 LaTeX 文本或成功导出 PNG）', async () => {
    const { copyToClipboard } = await import('./clipboard');
    const { writeText, writeImage } = await import(
      '@tauri-apps/plugin-clipboard-manager'
    );
    await copyToClipboard('E=mc^2', 'png');

    const textCalls = (writeText as ReturnType<typeof vi.fn>).mock.calls.length;
    const imageCalls = (writeImage as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(textCalls + imageCalls).toBeGreaterThan(0);

    if (textCalls > 0) {
      expect(writeText).toHaveBeenCalledWith('E=mc^2');
    }
    if (imageCalls > 0) {
      const arg = (writeImage as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(arg).toBeInstanceOf(Uint8Array);
      expect(arg.length).toBeGreaterThan(0);
    }
  });
});
