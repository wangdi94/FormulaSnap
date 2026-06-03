/**
 * Python Sidecar HTTP 客户端
 *
 * 通过 HTTP 与 Python FastAPI sidecar 通信（端口 8477）。
 * 所有 OCR 请求和状态查询都走这个客户端。
 */

import { invoke } from '@tauri-apps/api/core';
import { t } from './i18n';
import type { OcrBackend } from '../types/ocr';
export type { OcrBackend } from '../types/ocr';

// ---------------------------------------------------------------------------
// 端口初始化（运行时动态获取，支持 Tauri command + 环境变量 + 默认值 fallback）
// ---------------------------------------------------------------------------

let SIDECAR_PORT = '8477';
let SIDECAR_BASE_URL = `http://localhost:${SIDECAR_PORT}`;

/**
 * 初始化 sidecar 端口（在应用启动时调用）
 *
 * 优先级：
 * 1. Tauri command `get_sidecar_port`（桌面环境）
 * 2. 环境变量 `VITE_SIDECAR_PORT`（开发模式）
 * 3. 默认值 `8477`
 */
export async function initSidecarPort(): Promise<void> {
  try {
    const port = await invoke<number>('get_sidecar_port');
    SIDECAR_PORT = String(port);
  } catch {
    SIDECAR_PORT = import.meta.env.VITE_SIDECAR_PORT ?? '8477';
  }
  SIDECAR_BASE_URL = `http://localhost:${SIDECAR_PORT}`;
}

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

/** OCR 请求参数 */
export interface OcrRequest {
  imageBase64: string;
  backend?: OcrBackend | 'auto';
}

/** OCR 响应 */
export interface OcrResponse {
  latex: string;
  confidence: number;
  backend: OcrBackend;
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

/** API Key 状态项 */
export interface KeyStatusItem {
  backend: string;
  configured: boolean;
}

/** API Key 列表响应 */
export interface KeysResponse {
  keys: KeyStatusItem[];
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
      t('sidecar.request_failed', { status: response.status, statusText: response.statusText }),
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
 * 调用 OCR 识别
 *
 * @param imageBase64 - 图片的 base64 编码（不含 data:image/... 前缀）
 * @param backend - OCR 引擎名称，默认 'pix2text'
 * @returns 识别结果，包含 LaTeX、置信度等
 */
export async function callOcr(
  imageBase64: string,
  backend: OcrBackend | 'auto' = 'pix2text',
  options?: { signal?: AbortSignal },
): Promise<OcrResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  const externalSignal = options?.signal;
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener('abort', onExternalAbort);

  try {
    return await request<OcrResponse>('/api/ocr', {
      method: 'POST',
      body: JSON.stringify({
        image_base64: imageBase64,
        backend,
      }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
    externalSignal?.removeEventListener('abort', onExternalAbort);
  }
}

/**
 * 获取 OCR 使用统计（带 5 秒超时）
 *
 * 超时后返回 null，避免前端因 sidecar 无响应而卡住
 */
export async function getStats(): Promise<StatsResponse | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    return await request<StatsResponse>('/api/stats', {
      signal: controller.signal,
    });
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * 保存 API Key 到 sidecar keyring
 */
export async function saveApiKey(
  backend: string,
  key: string,
): Promise<void> {
  await request<{ status: string }>('/api/keys', {
    method: 'POST',
    body: JSON.stringify({ backend, key }),
  });
}

/**
 * 获取所有 API Key 的配置状态（不返回实际值）
 */
export async function getApiKeys(): Promise<KeysResponse> {
  return request<KeysResponse>('/api/keys');
}


