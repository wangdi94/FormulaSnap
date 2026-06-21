import { t, type TranslationKey } from './i18n';

// ---------------------------------------------------------------------------
// 超时配置（毫秒）
// ---------------------------------------------------------------------------

export const TIMEOUT = {
  /** 截图捕获超时（Rust 端 10s + 前端缓冲 5s） */
  SCREENSHOT_CAPTURE: 15_000,
  /** 区域选择超时（等待用户框选） */
  SELECTION: 15_000,
  /** OCR 识别超时 */
  OCR: 30_000,
  /** Sidecar 统计查询超时 */
  SIDECAR_STATS: 5_000,
  /** Sidecar 健康检查超时 */
  SIDECAR_HEALTH: 3_000,
} as const;

const BACKEND_I18N_KEYS: Record<string, TranslationKey> = {
  pix2text: 'backend.pix2text',
  mathpix: 'backend.mathpix',
  openai: 'backend.openai',
  claude: 'backend.claude',
  gemini: 'backend.gemini',
};

export function getBackendLabel(backend: string): string {
  const key = BACKEND_I18N_KEYS[backend];
  return key ? t(key) : backend;
}

export function getBackendOptions(): Array<{ value: string; label: string }> {
  return [
    { value: 'auto', label: t('backend.auto') },
    ...Object.entries(BACKEND_I18N_KEYS).map(([value, key]) => ({
      value,
      label: t(key),
    })),
  ];
}
