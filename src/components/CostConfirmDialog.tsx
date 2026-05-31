import { useCallback } from "react";

interface CostConfirmDialogProps {
  backend: string;
  estimatedTokens: number;
  estimatedCostUsd: number;
  budgetWarning?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onNeverShow?: () => void;
}

export default function CostConfirmDialog({
  backend,
  estimatedTokens,
  estimatedCostUsd,
  budgetWarning = false,
  onConfirm,
  onCancel,
  onNeverShow,
}: CostConfirmDialogProps) {
  const handleOverlayClick = useCallback(() => {
    onCancel();
  }, [onCancel]);

  const handleOverlayKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    },
    [onCancel]
  );

  const handleContentClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
    },
    []
  );

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: 模态遮罩层需要点击/键盘事件
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 cursor-default"
      onClick={handleOverlayClick}
      onKeyDown={handleOverlayKeyDown}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="确认 LLM 调用"
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden"
        onClick={handleContentClick}
        onKeyDown={handleOverlayKeyDown}
      >
        {/* 头部 */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            确认 LLM 调用
          </h2>
        </div>

        {/* 内容 */}
        <div className="px-6 py-4 space-y-4">
          {/* 预算警告 */}
          {budgetWarning && (
            <div className="flex items-start gap-3 p-3 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 rounded-md">
              <svg
                className="w-5 h-5 text-amber-500 mt-0.5 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                aria-hidden="true"
              >
                <title>警告</title>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
                />
              </svg>
              <div>
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  月度预算警告
                </p>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                  当前月度 LLM 支出已超过预算的 80%，请注意控制使用量。
                </p>
              </div>
            </div>
          )}

          {/* 成本信息 */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                后端
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {backend}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                预估 Tokens
              </span>
              <span className="text-sm font-medium text-gray-900 dark:text-white font-mono">
                {estimatedTokens.toLocaleString()}
              </span>
            </div>
            <div className="h-px bg-gray-200 dark:bg-gray-700" />
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                预估成本
              </span>
              <span className="text-base font-semibold text-gray-900 dark:text-white font-mono">
                ${estimatedCostUsd.toFixed(4)}
              </span>
            </div>
          </div>
        </div>

        {/* 按钮 */}
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 flex items-center justify-between gap-3">
          {onNeverShow && (
            <button
              type="button"
              onClick={onNeverShow}
              className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
            >
              不再提示
            </button>
          )}
          <div className="flex items-center gap-3 ml-auto">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
            >
              确认调用
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
