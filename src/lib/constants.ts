export const BACKEND_LABELS: Record<string, string> = {
  pix2text: "Pix2Text（本地）",
  mathpix: "Mathpix",
  openai: "OpenAI GPT-4o",
  claude: "Claude",
  gemini: "Gemini",
};

export const BACKENDS: Array<{ value: string; label: string }> = [
  { value: 'auto', label: '自动选择' },
  ...Object.entries(BACKEND_LABELS).map(([value, label]) => ({ value, label })),
];
