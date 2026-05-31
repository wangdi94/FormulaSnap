import type { OcrBackend } from './ocr';

export interface HistoryEntry {
  id: number;
  created_at: string;  // ISO 8601
  latex: string;
  backend: OcrBackend;
  confidence: number;
  screenshot_path: string | null;
  mathml?: string | null;
}

export interface HistoryListParams {
  limit: number;
  offset: number;
  backend_filter?: string;
}
