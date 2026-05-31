import { useEffect, useRef, useCallback } from "react";
import "mathlive";

interface FormulaPreviewProps {
  latex: string;
  readOnly?: boolean;
  onChange?: (latex: string) => void;
}

export default function FormulaPreview({
  latex,
  readOnly = true,
  onChange,
}: FormulaPreviewProps) {
  const mathFieldRef = useRef<MathfieldElement>(null);

  // 同步外部 latex 到 math-field
  useEffect(() => {
    if (mathFieldRef.current && mathFieldRef.current.value !== latex) {
      mathFieldRef.current.value = latex;
    }
  }, [latex]);

  // 监听 math-field 内部变化
  const handleInput = useCallback(
    (e: Event) => {
      const target = e.target as HTMLElement & { value: string };
      if (target && onChange) {
        onChange(target.value);
      }
    },
    [onChange]
  );

  useEffect(() => {
    const field = mathFieldRef.current;
    if (field) {
      field.addEventListener("input", handleInput);
      return () => field.removeEventListener("input", handleInput);
    }
  }, [handleInput]);

  const handleCopy = useCallback(
    (format: "latex" | "mathml") => {
      if (!mathFieldRef.current) return;

      const text =
        format === "latex"
          ? mathFieldRef.current.value
          : mathFieldRef.current.getValue("mathml");

      navigator.clipboard.writeText(text).catch(console.error);
    },
    []
  );

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800">
      <math-field
        ref={mathFieldRef}
        read-only={readOnly ? "true" : undefined}
        className="w-full min-h-[3rem]"
      />
      <div className="flex gap-2 mt-3">
        <button
          type="button"
          onClick={() => handleCopy("latex")}
          className="px-3 py-1.5 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors"
        >
          复制 LaTeX
        </button>
        <button
          type="button"
          onClick={() => handleCopy("mathml")}
          className="px-3 py-1.5 text-sm bg-gray-500 hover:bg-gray-600 text-white rounded-md transition-colors"
        >
          复制 MathML
        </button>
      </div>
    </div>
  );
}
