/**
 * 通用加载旋转指示器组件
 * Reusable loading spinner with Tailwind CSS animation.
 */

interface SpinnerProps {
  /** 尺寸：sm(16px) / md(20px) / lg(32px)，默认 md */
  size?: "sm" | "md" | "lg";
  /** 附加 CSS 类名 */
  className?: string;
  /** SVG <title> 文本，同时用作无障碍标签 */
  title?: string;
}

const sizeClasses: Record<NonNullable<SpinnerProps["size"]>, string> = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-8 w-8",
};

/** 默认无障碍标签 —— 英文回退，调用方可传入 i18n 翻译文本 */
const DEFAULT_TITLE = "Loading...";

export function Spinner({
  size = "md",
  className = "",
  title = DEFAULT_TITLE,
}: SpinnerProps) {
  const sizeClass = sizeClasses[size];

  return (
    <svg
      className={`animate-spin ${sizeClass} ${className}`.trim()}
      viewBox="0 0 24 24"
      fill="none"
      aria-label={title}
      role="img"
    >
      <title>{title}</title>
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
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

export default Spinner;
