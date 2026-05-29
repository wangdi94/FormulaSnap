import { useMemo } from "react";
import type { OcrBackend } from "../types";

interface BackendIndicatorProps {
  backend: OcrBackend;
  fallback?: boolean;
}

const BACKEND_LABELS: Record<OcrBackend, string> = {
  pix2text: "Pix2Text (本地)",
  mathpix: "Mathpix",
  openai: "OpenAI",
  claude: "Claude",
  gemini: "Gemini",
};

const BACKEND_COLORS: Record<OcrBackend, string> = {
  pix2text: "bg-green-500",
  mathpix: "bg-blue-500",
  openai: "bg-emerald-500",
  claude: "bg-orange-500",
  gemini: "bg-purple-500",
};

export default function BackendIndicator({
  backend,
  fallback = false,
}: BackendIndicatorProps) {
  const label = BACKEND_LABELS[backend];
  const dotColor = BACKEND_COLORS[backend];

  const tooltipText = useMemo(() => {
    if (fallback) {
      return `已降级到 ${label}`;
    }
    return `当前后端: ${label}`;
  }, [fallback, label]);

  return (
    <div
      className="flex items-center gap-2 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded-md"
      title={tooltipText}
    >
      <span className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span>{label}</span>
      {fallback && (
        <span className="text-amber-600 dark:text-amber-400 text-[10px] font-medium">
          降级
        </span>
      )}
    </div>
  );
}
