import { writeText, writeImage } from '@tauri-apps/plugin-clipboard-manager';

export type CopyFormat = 'latex' | 'mathml' | 'png';

/**
 * 复制文本到剪贴板
 */
export async function copyToClipboard(text: string, format: CopyFormat): Promise<void> {
  switch (format) {
    case 'latex':
      await writeText(text);
      break;

    case 'mathml': {
      // 使用 MathLive 将 LaTeX 转换为 MathML
      const mathField = document.createElement('math-field') as unknown as MathfieldElement;
      mathField.value = text;
      const mathml = mathField.getValue('mathml');
      await writeText(mathml);
      break;
    }

    case 'png': {
      // 将 LaTeX 渲染为 PNG
      // 使用 MathLive 创建一个 math-field 元素来渲染
      const container = document.createElement('div');
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      container.style.top = '-9999px';
      document.body.appendChild(container);

      const mathField = document.createElement('math-field') as unknown as MathfieldElement;
      mathField.value = text;
      mathField.style.fontSize = '24px';
      container.appendChild(mathField);

      // 等待渲染完成
      await new Promise(resolve => setTimeout(resolve, 100));

      // 尝试通过 Canvas 导出为 PNG
      try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (ctx) {
          // 使用 SVG 序列化
          const svgData = new XMLSerializer().serializeToString(mathField);
          const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
          const url = URL.createObjectURL(svgBlob);

          const img = new Image();
          await new Promise<void>((resolve, reject) => {
            img.onload = () => {
              canvas.width = img.width;
              canvas.height = img.height;
              ctx.drawImage(img, 0, 0);
              URL.revokeObjectURL(url);
              resolve();
            };
            img.onerror = reject;
            img.src = url;
          });

          // 导出为 PNG 并写入剪贴板
          const blob = await new Promise<Blob | null>(resolve =>
            canvas.toBlob(resolve, 'image/png')
          );
          if (blob) {
            const buffer = await blob.arrayBuffer();
            await writeImage(new Uint8Array(buffer));
            document.body.removeChild(container);
            return;
          }
        }
      } catch {
        // 如果 PNG 导出失败，回退到复制 LaTeX 文本
      }

      document.body.removeChild(container);
      // 回退：复制原始 LaTeX 文本
      await writeText(text);
      break;
    }
  }
}

/**
 * 获取格式的中文名称
 */
export function getFormatLabel(format: CopyFormat): string {
  const labels: Record<CopyFormat, string> = {
    latex: 'LaTeX',
    mathml: 'MathML',
    png: 'PNG 图片',
  };
  return labels[format];
}
