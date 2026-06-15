export interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type OcrBackend = 'pix2text' | 'mathpix' | 'openai' | 'claude' | 'gemini';

export interface OcrRequest {
  image_base64: string;
  backend?: OcrBackend | 'auto';
}

export interface OcrResult {
  latex: string;
  confidence: number;
  backend: OcrBackend;
  timing_ms: number;
  cost_estimate?: CostEstimate;
}

export type OcrResponse = OcrResult;

export interface CostEstimate {
  tokens_used?: number;
  estimated_cost_usd?: number;
}

export interface OcrError {
  code: 'API_KEY_ERROR' | 'RATE_LIMIT_ERROR' | 'NETWORK_ERROR' | 'PARSE_ERROR' | 'UNKNOWN';
  message: string;
  retry_after?: number;
}
