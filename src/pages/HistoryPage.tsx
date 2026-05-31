import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { invoke } from "@tauri-apps/api/core";
import type { HistoryEntry } from "../types/history";
import { BACKEND_LABELS } from "../lib/constants";

const PAGE_SIZE = 20;

const BACKEND_COLORS: Record<string, string> = {
  pix2text: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  mathpix: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  openai: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  claude: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  gemini: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
};

/** 截断 LaTeX 显示，过长时加省略号 */
function truncateLatex(latex: string, maxLen = 80): string {
  if (latex.length <= maxLen) return latex;
  return latex.slice(0, maxLen) + "…";
}

/** 格式化时间：显示为本地化短格式 */
function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return "刚刚";
    if (diffMin < 60) return `${diffMin} 分钟前`;
    if (diffHr < 24) return `${diffHr} 小时前`;
    if (diffDay < 7) return `${diffDay} 天前`;

    return d.toLocaleDateString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** 置信度颜色 */
function confidenceColor(c: number): string {
  if (c >= 0.8) return "text-green-600 dark:text-green-400";
  if (c >= 0.5) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(0);
  const [isLastPage, setIsLastPage] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isCancelledRef = useRef(false);

  /* ── debounce 搜索词 ── */
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(0); // 搜索时重置到第一页
    }, 300);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [searchQuery]);

  /* ── 加载数据 ── */
  const loadEntries = useCallback(async () => {
    setLoading(true);
    isCancelledRef.current = false;
    try {
      let results: HistoryEntry[];
      if (debouncedQuery) {
        results = await invoke<HistoryEntry[]>("search_history", {
          query: debouncedQuery,
        });
        if (isCancelledRef.current) return;
        setIsLastPage(true); // 搜索结果不分页
      } else {
        results = await invoke<HistoryEntry[]>("get_history", {
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        });
        if (isCancelledRef.current) return;
        setIsLastPage(results.length < PAGE_SIZE);
      }
      setEntries(results);
    } catch (e) {
      if (isCancelledRef.current) return;
      console.error("Failed to load history:", e);
      setEntries([]);
    } finally {
      if (!isCancelledRef.current) {
        setLoading(false);
      }
    }
  }, [debouncedQuery, page]);

  useEffect(() => {
    loadEntries();
    return () => {
      isCancelledRef.current = true;
    };
  }, [loadEntries]);

  /* ── 渲染 ── */
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
          历史记录
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          查看过往的公式识别记录
        </p>
      </div>

      {/* 搜索栏 */}
      <div className="relative">
        <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索 LaTeX 公式..."
          className="w-full pl-9 pr-9 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg
                     bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                     placeholder-gray-400 dark:placeholder-gray-500
                     focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                     dark:focus:ring-blue-400 dark:focus:border-blue-400
                     transition-colors text-sm"
          aria-label="搜索历史记录"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 text-gray-400 hover:text-gray-600
                       dark:hover:text-gray-300 transition-colors"
            aria-label="清除搜索"
          >
            <XIcon className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 搜索状态提示 */}
      {debouncedQuery && !loading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          搜索 "{debouncedQuery}" 找到 {entries.length} 条记录
        </p>
      )}

      {/* 列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20" role="status" aria-live="polite">
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
      ) : entries.length === 0 ? (
        /* 空状态 */
        <div className="flex flex-col items-center justify-center py-20 space-y-4">
          <div className="w-16 h-16 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
            <DocumentIcon className="w-8 h-8 text-gray-300 dark:text-gray-600" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
              {debouncedQuery ? "未找到匹配的记录" : "暂无历史记录"}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              {debouncedQuery
                ? "尝试其他关键词搜索"
                : "使用截图识别功能后，记录会自动保存在这里"}
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <button
              type="button"
              key={entry.id}
              onClick={() => navigate(`/history/${entry.id}`)}
              className="w-full text-left bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
                         rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600
                         hover:shadow-sm transition-all group cursor-pointer"
            >
              {/* LaTeX 预览 */}
              <p className="text-sm font-mono text-gray-800 dark:text-gray-200 truncate leading-relaxed">
                {truncateLatex(entry.latex)}
              </p>

              {/* 元信息行 */}
              <div className="mt-2.5 flex items-center gap-3 text-xs">
                {/* 后端标签 */}
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full font-medium ${
                    BACKEND_COLORS[entry.backend] ??
                    "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                  }`}
                >
                  {BACKEND_LABELS[entry.backend] ?? entry.backend}
                </span>

                {/* 置信度 */}
                <span className={`font-mono ${confidenceColor(entry.confidence)}`}>
                  {(entry.confidence * 100).toFixed(0)}%
                </span>

                {/* 时间 */}
                <span className="text-gray-400 dark:text-gray-500 ml-auto">
                  {formatTime(entry.created_at)}
                </span>

                {/* 箭头 */}
                <ChevronRightIcon className="w-4 h-4 text-gray-300 dark:text-gray-600 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors" />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* 分页控件 */}
      {!loading && !debouncedQuery && entries.length > 0 && (
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-colors
                       bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600
                       text-gray-700 dark:text-gray-300
                       hover:bg-gray-50 dark:hover:bg-gray-700
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-gray-800"
          >
            上一页
          </button>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            第 {page + 1} 页
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => p + 1)}
            disabled={isLastPage}
            className="px-4 py-2 text-sm font-medium rounded-lg transition-colors
                       bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600
                       text-gray-700 dark:text-gray-300
                       hover:bg-gray-50 dark:hover:bg-gray-700
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white dark:disabled:hover:bg-gray-800"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

/* ━━━ 内联 SVG 图标 ━━━ */

function SearchIcon({ className }: { className?: string }) {
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
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
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
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}

function DocumentIcon({ className }: { className?: string }) {
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
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
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
        d="M9 5l7 7-7 7"
      />
    </svg>
  );
}
