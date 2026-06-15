import { writeText, writeImage } from '@tauri-apps/plugin-clipboard-manager';
import { convertLatexToMarkup } from 'mathlive';
import { convertLatexToMathMl } from 'mathlive/ssr';
import mathliveCss from 'mathlive/static.css?inline';

export type CopyFormat = 'latex' | 'mathml' | 'png';

// 将 @font-face url(fonts/...) 替换为 CDN 绝对路径，使 SVG foreignObject 作为 Image 加载时字体可访问
function prepareMathliveCssForSvg(css: string): string {
  return css.replace(
    /url\(fonts\//g,
    'url(https://cdn.jsdelivr.net/npm/mathlive/fonts/'
  );
}

export async function copyToClipboard(text: string, format: CopyFormat): Promise<void> {
  switch (format) {
    case 'latex':
      await writeText(text);
      break;

    case 'mathml': {
      // 使用 MathLive SSR 将 LaTeX 转换为 MathML，无需 DOM 元素
      const mathml = convertLatexToMathMl(text);
      await writeText(mathml);
      break;
    }

    case 'png': {
      // 方案：使用 MathLive SSR 将 LaTeX 转换为 HTML，嵌入 SVG foreignObject 后渲染到 Canvas
      // 避免直接序列化 math-field 自定义元素（其 Shadow DOM 无法用 XMLSerializer 捕获）
      const markup = convertLatexToMarkup(text, { defaultMode: 'math' });
      const cssWithFonts = prepareMathliveCssForSvg(mathliveCss);

      const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100%" height="100%">
  <defs>
    <style>${cssWithFonts}</style>
  </defs>
  <foreignObject x="0" y="0" width="100%" height="100%">
    <div xmlns="http://www.w3.org/1999/xhtml">${markup}</div>
  </foreignObject>
</svg>`;

      const svgBlob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      let objectUrl: string | undefined = url;
      try {
        const img = new Image();
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('Canvas 2D context unavailable');

        await new Promise<void>((resolve, reject) => {
          img.onload = () => {
            canvas.width = img.naturalWidth || 200;
            canvas.height = img.naturalHeight || 50;
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(url);
            objectUrl = undefined;
            resolve();
          };
          img.onerror = () => reject(new Error('SVG image failed to load'));
          img.src = url;
        });

        const blob = await new Promise<Blob | null>(resolve =>
          canvas.toBlob(resolve, 'image/png')
        );

        if (blob) {
          const buffer = await blob.arrayBuffer();
          await writeImage(new Uint8Array(buffer));
          return;
        }
      } catch {
        // PNG 转换失败时 fallback 到纯文本复制
      } finally {
        if (objectUrl) {
          URL.revokeObjectURL(objectUrl);
        }
      }

      await writeText(text);
      break;
    }
  }
}


