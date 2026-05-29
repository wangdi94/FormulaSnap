/**
 * Python Sidecar HTTP 客户端
 *
 * 通过 HTTP 与 Python FastAPI sidecar 通信（端口 8477）。
 * 所有 OCR 请求和状态查询都走这个客户端。
 */

const SIDECAR_BASE_URL = 'http://localhost:8477';

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

/** OCR 请求参数 */
export interface OcrRequest {
  imageBase64: string;
  backend?: string;
}

/** OCR 响应 */
export interface OcrResponse {
  latex: string;
  confidence: number;
  backend: string;
  timing_ms: number;
  cost_estimate?: {
    tokens_used?: number;
    estimated_cost_usd?: number;
  };
}

/** 使用统计 */
export interface StatsResponse {
  total_calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
  calls_today: number;
  daily_limit: number;
  remaining_today: number;
}

/** 健康检查响应 */
export interface HealthResponse {
  status: string;
}

/** 配置验证响应 */
export interface ValidateConfigResponse {
  valid: boolean;
  message: string;
}

/** Sidecar API 错误 */
export class SidecarError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'SidecarError';
  }
}

// ---------------------------------------------------------------------------
// 内部工具
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${SIDECAR_BASE_URL}${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new SidecarError(
      `Sidecar 请求失败: ${response.status} ${response.statusText}`,
      response.status,
      detail,
    );
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// 公开 API
// ---------------------------------------------------------------------------

/**
 * 健康检查：验证 sidecar 是否就绪
 */
export async function healthCheck(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

/**
 * 调用 OCR 识别
 *
 * @param imageBase64 - 图片的 base64 编码（不含 data:image/... 前缀）
 * @param backend - OCR 引擎名称，默认 'pix2text'
 * @returns 识别结果，包含 LaTeX、置信度等
 */
export async function callOcr(
  imageBase64: string,
  backend: string = 'pix2text',
): Promise<OcrResponse> {
  return request<OcrResponse>('/api/ocr', {
    method: 'POST',
    body: JSON.stringify({
      image_base64: imageBase64,
      backend,
    }),
  });
}

/**
 * 获取 OCR 使用统计
 */
export async function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>('/api/stats');
}

/**
 * 验证指定后端的配置是否有效
 *
 * @param backend - 要验证的 OCR 引擎名称
 */
export async function validateConfig(
  backend: string,
): Promise<ValidateConfigResponse> {
  return request<ValidateConfigResponse>('/api/validate-config', {
    method: 'POST',
    body: JSON.stringify({ backend }),
  });
}

/**
 * 等待 sidecar 就绪（带重试）
 *
 * @param maxRetries - 最大重试次数
 * @param interval - 重试间隔（毫秒）
 * @returns 是否就绪
 */
export async function waitForReady(
  maxRetries: number = 60,
  interval: number = 500,
): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const result = await healthCheck();
      if (result.status === 'ok') {
        return true;
      }
    } catch {
      // sidecar 尚未就绪，继续等待
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  return false;
}
