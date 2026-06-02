import { describe, it, expect, vi } from 'vitest';
import { extractSidecarError, mapSidecarError } from '../components/CaptureFlow';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn().mockResolvedValue(vi.fn()) }));
vi.mock('../lib/settings', () => ({ loadSettings: vi.fn().mockResolvedValue({}) }));
vi.mock('../lib/i18n', () => ({ t: (key: string, vars?: Record<string, string>) => vars?.message ?? key }));
vi.mock('../lib/sidecarClient', () => ({
  callOcr: vi.fn(),
  SidecarError: class extends Error {
    status: number;
    detail?: unknown;
    constructor(message: string, status: number, detail?: unknown) {
      super(message);
      this.name = 'SidecarError';
      this.status = status;
      this.detail = detail;
    }
  },
}));

describe('extractSidecarError', () => {
  it('test_sidecar_error_non_standard: detail 不含 error/message 字段时不崩溃', () => {
    const result = extractSidecarError({ foo: 'bar', baz: 123 });
    expect(result.errorType).toBeUndefined();
    expect(result.message).toBe('');
  });

  it('detail 为 null 时返回默认值', () => {
    const result = extractSidecarError(null);
    expect(result.errorType).toBeUndefined();
    expect(result.message).toBe('');
  });

  it('detail 为 string 时返回默认值', () => {
    const result = extractSidecarError('some error');
    expect(result.errorType).toBeUndefined();
    expect(result.message).toBe('');
  });

  it('detail 为数组时返回默认值', () => {
    const result = extractSidecarError([1, 2, 3]);
    expect(result.errorType).toBeUndefined();
    expect(result.message).toBe('');
  });

  it('detail 包含标准 error/message 字段时正确提取', () => {
    const result = extractSidecarError({ error: 'API_KEY_ERROR', message: 'Invalid key' });
    expect(result.errorType).toBe('API_KEY_ERROR');
    expect(result.message).toBe('Invalid key');
  });

  it('detail 仅包含 error 字段时 message 为空', () => {
    const result = extractSidecarError({ error: 'RATE_LIMIT_ERROR' });
    expect(result.errorType).toBe('RATE_LIMIT_ERROR');
    expect(result.message).toBe('');
  });

  it('detail 的 error/message 为非 string 类型时忽略', () => {
    const result = extractSidecarError({ error: 42, message: { nested: true } });
    expect(result.errorType).toBeUndefined();
    expect(result.message).toBe('');
  });
});

describe('mapSidecarError', () => {
  it('test_sidecar_error_non_standard: SidecarError 含非标准 detail 时不崩溃，回退到 err.message', async () => {
    const { SidecarError } = await import('../lib/sidecarClient');
    const err = new SidecarError('HTTP 500', 500, { random: 'data', count: 42 });
    const result = mapSidecarError(err);
    expect(result.message).toBe('HTTP 500');
    expect(result.code).toBeUndefined();
    expect(result.retryable).toBe(true);
  });

  it('SidecarError 含空对象 detail 时回退到 err.message', async () => {
    const { SidecarError } = await import('../lib/sidecarClient');
    const err = new SidecarError('Bad request', 400, {});
    const result = mapSidecarError(err);
    expect(result.message).toBe('Bad request');
    expect(result.code).toBeUndefined();
  });

  it('普通 Error 返回 retryable: true', () => {
    const result = mapSidecarError(new Error('network timeout'));
    expect(result.message).toBe('network timeout');
    expect(result.retryable).toBe(true);
  });

  it('非 Error 类型返回 unknown_error', () => {
    const result = mapSidecarError('string error');
    expect(result.message).toBe('capture.unknown_error');
    expect(result.retryable).toBe(true);
  });
});
