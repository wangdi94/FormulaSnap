import { describe, it, expect } from 'vitest';
import {
  SidecarError,
  getStats,
  callOcr,
  initSidecarPort,
  type StatsResponse,
  type OcrRequest,
  type OcrResponse,
  type HealthResponse,
  type ValidateConfigResponse,
} from '../lib/sidecarClient';

// ---------------------------------------------------------------------------
// SidecarError 类
// ---------------------------------------------------------------------------

describe('SidecarError', () => {
  it('继承 Error', () => {
    const err = new SidecarError('test', 500);
    expect(err).toBeInstanceOf(Error);
  });

  it('name 为 SidecarError', () => {
    const err = new SidecarError('test', 500);
    expect(err.name).toBe('SidecarError');
  });

  it('message 正确传递', () => {
    const err = new SidecarError('请求失败', 404);
    expect(err.message).toBe('请求失败');
  });

  it('status 正确设置', () => {
    const err = new SidecarError('err', 422);
    expect(err.status).toBe(422);
  });

  it('detail 可选，存在时正确设置', () => {
    const detail = { code: 'NOT_FOUND' };
    const err = new SidecarError('err', 404, detail);
    expect(err.detail).toEqual(detail);
  });

  it('detail 缺省为 undefined', () => {
    const err = new SidecarError('err', 500);
    expect(err.detail).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// StatsResponse 接口结构
// ---------------------------------------------------------------------------

describe('StatsResponse 接口', () => {
  it('包含所有必需字段', () => {
    const stats: StatsResponse = {
      total_calls: 100,
      total_tokens: 50000,
      estimated_cost_usd: 1.23,
      calls_today: 10,
      daily_limit: 1000,
      remaining_today: 990,
    };

    expect(stats.total_calls).toBe(100);
    expect(stats.total_tokens).toBe(50000);
    expect(stats.estimated_cost_usd).toBe(1.23);
    expect(stats.calls_today).toBe(10);
    expect(stats.daily_limit).toBe(1000);
    expect(stats.remaining_today).toBe(990);
  });

  it('所有字段为 number 类型', () => {
    const stats: StatsResponse = {
      total_calls: 0,
      total_tokens: 0,
      estimated_cost_usd: 0,
      calls_today: 0,
      daily_limit: 0,
      remaining_today: 0,
    };

    expect(typeof stats.total_calls).toBe('number');
    expect(typeof stats.total_tokens).toBe('number');
    expect(typeof stats.estimated_cost_usd).toBe('number');
    expect(typeof stats.calls_today).toBe('number');
    expect(typeof stats.daily_limit).toBe('number');
    expect(typeof stats.remaining_today).toBe('number');
  });
});

// ---------------------------------------------------------------------------
// OcrRequest 接口结构
// ---------------------------------------------------------------------------

describe('OcrRequest 接口', () => {
  it('imageBase64 为必需 string', () => {
    const req: OcrRequest = { imageBase64: 'abc123' };
    expect(req.imageBase64).toBe('abc123');
  });

  it('backend 为可选 string', () => {
    const req1: OcrRequest = { imageBase64: 'abc' };
    expect(req1.backend).toBeUndefined();

    const req2: OcrRequest = { imageBase64: 'abc', backend: 'pix2text' };
    expect(req2.backend).toBe('pix2text');
  });
});

// ---------------------------------------------------------------------------
// OcrResponse 接口结构
// ---------------------------------------------------------------------------

describe('OcrResponse 接口', () => {
  it('包含所有必需字段', () => {
    const res: OcrResponse = {
      latex: 'x^2',
      confidence: 0.95,
      backend: 'pix2text',
      timing_ms: 120,
    };

    expect(res.latex).toBe('x^2');
    expect(res.confidence).toBe(0.95);
    expect(res.backend).toBe('pix2text');
    expect(res.timing_ms).toBe(120);
  });

  it('cost_estimate 为可选嵌套对象', () => {
    const res1: OcrResponse = {
      latex: '',
      confidence: 0,
      backend: 'pix2text',
      timing_ms: 0,
    };
    expect(res1.cost_estimate).toBeUndefined();

    const res2: OcrResponse = {
      latex: '',
      confidence: 0,
      backend: 'pix2text',
      timing_ms: 0,
      cost_estimate: {
        tokens_used: 1000,
        estimated_cost_usd: 0.02,
      },
    };
    expect(res2.cost_estimate?.tokens_used).toBe(1000);
    expect(res2.cost_estimate?.estimated_cost_usd).toBe(0.02);
  });

  it('cost_estimate 内部字段均可选', () => {
    const res: OcrResponse = {
      latex: '',
      confidence: 0,
      backend: 'pix2text',
      timing_ms: 0,
      cost_estimate: {},
    };
    expect(res.cost_estimate?.tokens_used).toBeUndefined();
    expect(res.cost_estimate?.estimated_cost_usd).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// 公开函数签名验证
// ---------------------------------------------------------------------------

describe('sidecarClient 导出函数', () => {
  it('getStats 是函数，参数数量为 0', () => {
    expect(typeof getStats).toBe('function');
    expect(getStats.length).toBe(0);
  });

  it('callOcr 是函数，参数数量为 2（含默认值）', () => {
    expect(typeof callOcr).toBe('function');
    // callOcr(imageBase64, backend?) — TS 编译后 length=1（仅必需参数）
    expect(callOcr.length).toBe(1);
  });

  it('initSidecarPort 是函数，参数数量为 0', () => {
    expect(typeof initSidecarPort).toBe('function');
    expect(initSidecarPort.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 辅助类型
// ---------------------------------------------------------------------------

describe('HealthResponse / ValidateConfigResponse', () => {
  it('HealthResponse 有 status 字段', () => {
    const h: HealthResponse = { status: 'ok' };
    expect(h.status).toBe('ok');
  });

  it('ValidateConfigResponse 有 valid 和 message', () => {
    const v: ValidateConfigResponse = { valid: true, message: 'OK' };
    expect(v.valid).toBe(true);
    expect(v.message).toBe('OK');
  });
});
