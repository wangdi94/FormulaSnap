import { useRef, useEffect, useCallback } from "react";

interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface RegionSelectorProps {
  screenshotBase64: string;
  onSelected: (rect: SelectionRect) => void;
  onCancel: () => void;
}

const MIN_SELECTION = 10;
const OVERLAY_ALPHA = 0.55;

export default function RegionSelector({
  screenshotBase64,
  onSelected,
  onCancel,
}: RegionSelectorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const isDragging = useRef(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const currentX = useRef(0);
  const currentY = useRef(0);

  const getSelectionBox = useCallback(
    (cw: number, ch: number) => {
      const sx = Math.min(startX.current, currentX.current);
      const sy = Math.min(startY.current, currentY.current);
      const ex = Math.max(startX.current, currentX.current);
      const ey = Math.max(startY.current, currentY.current);
      const w = Math.max(0, Math.min(ex, cw) - Math.max(sx, 0));
      const h = Math.max(0, Math.min(ey, ch) - Math.max(sy, 0));
      return { x: Math.max(sx, 0), y: Math.max(sy, 0), width: w, height: h };
    },
    [],
  );

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const cw = canvas.width;
    const ch = canvas.height;

    ctx.drawImage(img, 0, 0, cw, ch);
    ctx.fillStyle = `rgba(0, 0, 0, ${OVERLAY_ALPHA})`;
    ctx.fillRect(0, 0, cw, ch);

    if (isDragging.current) {
      const box = getSelectionBox(cw, ch);
      if (box.width > 0 && box.height > 0) {
        ctx.clearRect(box.x, box.y, box.width, box.height);
        ctx.drawImage(
          img,
          box.x,
          box.y,
          box.width,
          box.height,
          box.x,
          box.y,
          box.width,
          box.height,
        );
        ctx.strokeStyle = "#3b82f6";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(box.x, box.y, box.width, box.height);
        ctx.setLineDash([]);
      }
    }
  }, [getSelectionBox]);

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      redraw();
    };
    img.src = `data:image/png;base64,${screenshotBase64}`;
  }, [screenshotBase64, redraw]);

  useEffect(() => {
    const onResize = () => redraw();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [redraw]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const handleMouseDown = useCallback(
    (e: MouseEvent) => {
      isDragging.current = true;
      startX.current = e.clientX;
      startY.current = e.clientY;
      currentX.current = e.clientX;
      currentY.current = e.clientY;
      redraw();

      const onMouseMove = (ev: MouseEvent) => {
        if (!isDragging.current) return;
        currentX.current = ev.clientX;
        currentY.current = ev.clientY;
        redraw();
      };

      const onMouseUp = () => {
        if (!isDragging.current) return;
        isDragging.current = false;
        const cw = canvasRef.current?.width ?? window.innerWidth;
        const ch = canvasRef.current?.height ?? window.innerHeight;
        const box = getSelectionBox(cw, ch);
        if (box.width >= MIN_SELECTION && box.height >= MIN_SELECTION) {
          onSelected(box);
        }
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [redraw, getSelectionBox, onSelected],
  );

  useEffect(() => {
    window.addEventListener("mousedown", handleMouseDown);
    return () => window.removeEventListener("mousedown", handleMouseDown);
  }, [handleMouseDown]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        cursor: "crosshair",
        display: "block",
      }}
    />
  );
}
