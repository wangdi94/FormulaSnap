/** 根据置信度返回对应的 Tailwind 文本颜色类名 */
export function getConfidenceColor(
  confidence: number | null | undefined,
): string {
  if (confidence == null) return "text-gray-400";
  if (confidence >= 0.9) return "text-green-600";
  if (confidence >= 0.7) return "text-yellow-600";
  if (confidence >= 0.5) return "text-orange-500";
  return "text-gray-400";
}
