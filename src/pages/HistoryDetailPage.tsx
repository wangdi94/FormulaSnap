import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { invoke, convertFileSrc } from "@tauri-apps/api/core";
import type { HistoryEntry } from "../types/history";
import { copyToClipboard, type CopyFormat } from "../lib/clipboard";
import { getBackendLabel } from "../lib/constants";
import { t } from "../lib/i18n";
import FormulaPreview from "../components/FormulaPreview";

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

  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    };
  }, []);

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
          setError(t('history.record_not_found'));
        }
      } catch (e) {
        setError(t('history.load_failed', { error: String(e) }));
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
        if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
        copyTimeoutRef.current = setTimeout(() => {
          setCopyState((prev) => ({ ...prev, [format]: null }));
        }, 2000);
      } catch (e) {
        console.error("Copy failed:", e);
        setCopyState((prev) => ({ ...prev, [format]: "error" }));
        if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
        copyTimeoutRef.current = setTimeout(() => {
          setCopyState((prev) => ({ ...prev, [format]: null }));
        }, 3000);
      }
    },
    [entry],
  );

  /* ── 删除操作 ── */
  const handleDelete = useCallback(async () => {
    if (!entry) return;
    const confirmed = window.confirm(t('history.delete_confirm'));
    if (!confirmed) return;

    setDeleting(true);
    try {
      await invoke<boolean>("delete_history", { id: entry.id });
      navigate("/history", { replace: true });
    } catch (e) {
      console.error("Delete failed:", e);
      alert(t('history.delete_failed', { error: String(e) }));
      setDeleting(false);
    }
  }, [entry, navigate]);

  /* ── 截图 URL ── */
  const screenshotUrl =
    entry?.screenshot_path ? convertFileSrc(entry.screenshot_path) : null;

  /* ── 加载中 ── */
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full" role="status" aria-live="polite">
        <div className="flex items-center gap-3 text-gray-400 dark:text-gray-500">
          <svg
            className="animate-spin h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <title>{t('common.loading')}</title>
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
          <span>{t('common.loading')}</span>
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
          {t('history.back_to_list')}
        </button>
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="w-16 h-16 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center">
            <ExclamationIcon className="w-8 h-8 text-red-400 dark:text-red-500" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {error ?? t('history.record_not_found')}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {t('history.may_be_deleted')}
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
        {t('history.back_to_list')}
      </button>

      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          {t('history.detail_title')}
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          {t('history.record_number', { id: entry.id })}
        </p>
      </div>

      {/* 公式渲染 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          {t('history.formula_preview')}
        </h3>
        <FormulaPreview latex={entry.latex} readOnly />
      </section>

      {/* 元信息 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          {t('history.recognition_info')}
        </h3>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          <div className="text-gray-500 dark:text-gray-400">{t('history.backend')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            {getBackendLabel(entry.backend)}
          </div>

          <div className="text-gray-500 dark:text-gray-400">{t('history.confidence')}</div>
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

          <div className="text-gray-500 dark:text-gray-400">{t('history.created_at')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-medium">
            {new Date(entry.created_at).toLocaleString("zh-CN")}
          </div>

          <div className="text-gray-500 dark:text-gray-400">{t('history.latex_label')}</div>
          <div className="text-gray-900 dark:text-gray-100 font-mono text-xs break-all">
            {entry.latex}
          </div>
        </div>
      </section>

      {/* 原始截图 */}
      {screenshotUrl && (
        <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
            {t('history.original_screenshot')}
          </h3>
          <img
            src={screenshotUrl}
            alt={t('history.screenshot_alt')}
            className="max-w-full max-h-64 object-contain rounded-lg border border-gray-200 dark:border-gray-700"
          />
        </section>
      )}

      {/* 操作按钮 */}
      <section className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">
          {t('history.actions')}
        </h3>
        <div className="flex flex-wrap gap-3">
          <CopyButton
            label={t('history.copy_latex')}
            state={copyState.latex}
            onClick={() => handleCopy("latex")}
          />
          <CopyButton
            label={t('history.copy_mathml')}
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
                  <title>{t('history.deleting')}</title>
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
                {t('history.deleting')}
              </span>
            ) : (
              t('history.delete_record')
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
            <title>{t('history.copying')}</title>
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
          {t('history.copying')}
        </span>
      ) : isCopied ? (
        <span className="flex items-center gap-1">
          <CheckIcon className="w-4 h-4" />
          {t('history.copied')}
        </span>
      ) : isError ? (
        t('history.copy_failed')
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
