/**
 * MathLive 缺乏 TypeScript 类型定义。
 * 仅声明项目实际使用的 MathfieldElement 成员。
 * @see https://cortexjs.io/mathlive/
 */
interface MathfieldElement extends HTMLElement {
  /** 获取或设置 math-field 的 LaTeX 值 */
  value: string;
  /** 以指定格式获取内容，如 "latex" | "mathml" | "spoken" */
  getValue(format: string): string;
}

declare namespace React.JSX {
  interface IntrinsicElements {
    "math-field": React.DetailedHTMLProps<
      React.HTMLAttributes<MathfieldElement> & {
        "read-only"?: string;
        value?: string;
      },
      MathfieldElement
    >;
  }
}
