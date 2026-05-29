import { useCallback, useMemo } from "react";
import type { OcrError } from "../types";

interface OcrErrorDisplayProps {
  error: OcrError;
  onRetry?: () => void;
  onGoSettings?: () => void;
}

const ERROR_CONFIG: Record<
  OcrError["code"],
  { icon: "warning" | "error" | "network"; title: string; color: "amber" | "red" | "blue" }
> = {
  API_KEY_ERROR: {
    icon: "warning",
    title: "API Key 无效，请检查设置",
    color: "amber",
  },
  RATE_LIMIT_ERROR: {
    icon: "warning",
    title: "调用次数超限，请稍后再试",
    color: "amber",
  },
  NETWORK_ERROR: {
    icon: "network",
    title: "网络连接失败，已自动切换到本地 Pix2Text",
    color: "blue",
  },
  PARSE_ERROR: {
    icon: "error",
    title: "识别结果异常，请重试",
    color: "red",
  },
  UNKNOWN: {
    icon: "error",
    title: "出错了",
    color: "red",
  },
};

function ErrorIcon({ type }: { type: "warning" | "error" | "network" }) {
  if (type === "network") {
    return (
      <svg
        className="w-5 h-5 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={1.5}
        stroke="currentColor"
        aria-hidden="true"
      >
        <title>网络错误</title>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z"
        />
      </svg>
    );
  }

  return (
    <svg
      className="w-5 h-5 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
    >
      <title>{type === "warning" ? "警告" : "错误"}</title>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
      />
    </svg>
  );
}

export default function OcrErrorDisplay({
  error,
  onRetry,
  onGoSettings,
}: OcrErrorDisplayProps) {
  const config = ERROR_CONFIG[error.code];

  const colorClasses = useMemo(() => {
    switch (config.color) {
      case "amber":
        return {
          bg: "bg-amber-50 dark:bg-amber-900/30",
          border: "border-amber-200 dark:border-amber-700",
          text: "text-amber-800 dark:text-amber-200",
          icon: "text-amber-500",
          detail: "text-amber-700 dark:text-amber-300",
        };
      case "blue":
        return {
          bg: "bg-blue-50 dark:bg-blue-900/30",
          border: "border-blue-200 dark:border-blue-700",
          text: "text-blue-800 dark:text-blue-200",
          icon: "text-blue-500",
          detail: "text-blue-700 dark:text-blue-300",
        };
      case "red":
        return {
          bg: "bg-red-50 dark:bg-red-900/30",
          border: "border-red-200 dark:border-red-700",
          text: "text-red-800 dark:text-red-200",
          icon: "text-red-500",
          detail: "text-red-700 dark:text-red-300",
        };
    }
  }, [config.color]);

  const handleSettingsClick = useCallback(() => {
    onGoSettings?.();
  }, [onGoSettings]);

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 p-4 rounded-md border ${colorClasses.bg} ${colorClasses.border}`}
    >
      <div className={colorClasses.icon}>
        <ErrorIcon type={config.icon} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium ${colorClasses.text}`}>
          {config.title}
        </p>
        {error.code === "UNKNOWN" && error.message && (
          <p className={`text-sm mt-1 ${colorClasses.detail}`}>
            {error.message}
          </p>
        )}
        {error.code === "RATE_LIMIT_ERROR" && error.retry_after && (
          <p className={`text-sm mt-1 ${colorClasses.detail}`}>
            请等待 {error.retry_after} 秒后重试
          </p>
        )}
        <div className="flex gap-2 mt-3">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${colorClasses.text} bg-white dark:bg-gray-800 border-current hover:opacity-80`}
            >
              重试
            </button>
          )}
          {error.code === "API_KEY_ERROR" && onGoSettings && (
            <button
              type="button"
              onClick={handleSettingsClick}
              className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${colorClasses.text} bg-white dark:bg-gray-800 border-current hover:opacity-80`}
            >
              前往设置
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
