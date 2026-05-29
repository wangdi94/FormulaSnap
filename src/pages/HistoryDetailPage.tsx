import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import type { HistoryEntry } from "../types/history";
import { copyToClipboard, type CopyFormat } from "../lib/clipboard";
import FormulaPreview from "../components/FormulaPreview";

const BACKEND_LABELS: Record<string, string> = {
  pix2text: "Pix2Text (本地)",
  mathpix: "Mathpix",
  openai: "OpenAI GPT-4o",
  claude: "Claude",
  gemini: "Gemini",
};

type CopyState = null | "copying" | "copied" | "error";

export default function HistoryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [entry, setEntry] = useState<HistoryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [copyState, setCopyState] = useState<Record<CopyFormat, CopyState>>({
    latex: null,
    mathml: null,
    png: null,
  });

  /* ── 加载详情 ── */
  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await invoke<HistoryEntry | null>("get_history_by_id", {
          id: Number(id),
        });
        if (result) {
          setEntry(result);
        } else {
          setError("记录不存在");
        }
      } catch (e) {
        setError(`加载失败: ${e}`);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  /* ── 复制操作 ── */
  const handleCopy = useCallback(
    async (format: CopyFormat) => {
      if (!entry) return;
      setCopyState((prev) => ({ ...prev, [format]: "copying" }));
      try {
        await copyToClipboard(entry.latex, format);
        setCopyState((prev) => ({ ...prev, [format]: "copied" }));
        setTimeout(() => {
          setCopyState((prev) => ({ ...prev, [format]: null }));
        }, 2000);
      } catch (e) {
        console.error("Copy failed:", e);
        setCopyState((prev) => ({ ...prev, [format]: "error" }));
        setTimeout(() => {
          setCopyState((prev) => ({ ...prev, [format]: null }));
        }, 3000);
      }
    },
    [entry],
  );

  /* ── 删除操作 ── */
  const handleDelete = useCallback(async () => {
    if (!entry) return;
    const confirmed = window.confirm("确定要删除这条记录吗？此操作不可撤销。");
    if (!confirmed) return;

    setDeleting(true);
    try {
      await invoke<boolean>("delete_history", { id: entry.id });
      navigate("/history", { replace: true });
    } catch (e) {
      console.error("Delete failed:", e);
      alert(`删除失败: ${e}`);
      setDeleting(false);
    }
  }, [entry, navigate]);

  /* ── 截图 URL ── */
  const screenshotUrl =
    entry?.screenshot_path ? convertFileSrc(entry.screenshot_path) : null;

  /* ── 加载中 ── */
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex items-center gap-3 text-gray-400 dark:text-gray-500">
          <svg
            className="animate-spin h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <title>加载中</title>
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  /* ── 错误 / 未找到 ── */
  if (error || !entry) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <button
          type="button"
          onClick={() => navigate("/history")}
          className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400
                     hover:text-gray-700 dark:hover:text-gray-200 transition-colors mb-6"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          返回列表
        </button>
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="w-16 h-16 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center">
            <ExclamationIcon className="w-8 h-8 text-red-400 dark:text-red-500" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {error ?? "记录不存在"}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              该记录可能已被删除
            </p>
          </div>
        </div>
      </div>
    );
  }

  /* ── 主内容 ── */
  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      {/* 返回按钮 */}
      <button
        type="button"
        onClick={() => navigate("/history")}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400
                   hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
      >
        <ArrowLeftIcon className="w-4 h-4" />
        返回列表
      </button>

      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          识别详情
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          记录 #{entry.id}
        </p>
      </div>

      {/* 公式渲染 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          公式预览
        </h3>
        <FormulaPreview latex={entry.latex} readOnly />
      </section>

      {/* 元信息 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          识别信息
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div className="text-gray-500 dark:text-gray-400">后端</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            {BACKEND_LABELS[entry.backend] ?? entry.backend}
          </div>

          <div className="text-gray-500 dark:text-gray-400">置信度</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            <span
              className={
                entry.confidence >= 0.8
                  ? "text-green-600 dark:text-green-400"
                  : entry.confidence >= 0.5
                    ? "text-yellow-600 dark:text-yellow-400"
                    : "text-red-600 dark:text-red-400"
              }
            >
              {(entry.confidence * 100).toFixed(1)}%
            </span>
          </div>

          <div className="text-gray-500 dark:text-gray-400">创建时间</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            {new Date(entry.created_at).toLocaleString("zh-CN")}
          </div>

          <div className="text-gray-500 dark:text-gray-400">LaTeX</div>
          <div className="text-gray-900 dark:text-gray-100 font-mono text-xs break-all">
            {entry.latex}
          </div>
        </div>
      </section>

      {/* 原始截图 */}
      {screenshotUrl && (
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
            原始截图
          </h3>
          <img
            src={screenshotUrl}
            alt="识别时的原始截图"
            className="max-w-full max-h-64 object-contain rounded-lg border border-gray-200 dark:border-gray-700"
          />
        </section>
      )}

      {/* 操作按钮 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          操作
        </h3>
        <div className="flex flex-wrap gap-3">
          <CopyButton
            label="复制 LaTeX"
            state={copyState.latex}
            onClick={() => handleCopy("latex")}
          />
          <CopyButton
            label="复制 MathML"
            state={copyState.mathml}
            onClick={() => handleCopy("mathml")}
          />
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-colors
                       bg-red-50 text-red-600 hover:bg-red-100
                       dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {deleting ? (
              <span className="flex items-center gap-2">
                <svg
                  className="animate-spin h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <title>删除中</title>
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                删除中...
              </span>
            ) : (
              "删除记录"
            )}
          </button>
        </div>
      </section>
    </div>
  );
}

/* ━━━ 子组件 ━━━ */

function CopyButton({
  label,
  state,
  onClick,
}: {
  label: string;
  state: CopyState;
  onClick: () => void;
}) {
  const isCopying = state === "copying";
  const isCopied = state === "copied";
  const isError = state === "error";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isCopying}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:cursor-not-allowed ${
        isCopied
          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
          : isError
            ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
            : "bg-blue-500 hover:bg-blue-600 disabled:bg-blue-400 text-white"
      }`}
    >
      {isCopying ? (
        <span className="flex items-center gap-2">
          <svg
            className="animate-spin h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <title>复制中</title>
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          复制中...
        </span>
      ) : isCopied ? (
        <span className="flex items-center gap-1">
          <CheckIcon className="w-4 h-4" />
          已复制
        </span>
      ) : isError ? (
        "复制失败"
      ) : (
        label
      )}
    </button>
  );
}

/* ━━━ SVG 图标 ━━━ */

function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10 19l-7-7m0 0l7-7m-7 7h18"
      />
    </svg>
  );
}

function ExclamationIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M5 13l4 4L19 7"
      />
    </svg>
  );
}
