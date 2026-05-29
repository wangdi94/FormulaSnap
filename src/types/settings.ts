export type Theme = 'light' | 'dark' | 'system';

export interface AppSettings {
  hotkey: string;  // e.g., "Ctrl+Shift+C" or "Cmd+Shift+C"
  default_backend: 'auto' | 'pix2text' | 'mathpix' | 'openai' | 'claude' | 'gemini';
  api_keys: {
    openai?: string;
    claude?: string;
    gemini?: string;
    mathpix_app_id?: string;
    mathpix_app_key?: string;
  };
  theme: Theme;
  monthly_budget_usd: number;
  language: 'zh' | 'en';
}
