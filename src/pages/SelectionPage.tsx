import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { emit } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import RegionSelector from "../components/RegionSelector";
import type { SelectionRect } from "../types/ocr";

export default function SelectionPage() {
  const [screenshot, setScreenshot] = useState<string | null>(null);

  useEffect(() => {
    console.log("[SelectionPage] 开始截图...");
    Promise.race([
      invoke<string>("capture_screen_for_selection"),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("截图命令超时")), 15000),
      ),
    ]).then((data) => {
      console.log("[SelectionPage] 截图完成，数据长度:", data.length);
      setScreenshot(data);
    })
      .catch((err) => {
        console.error("[SelectionPage] 截图失败:", err);
        getCurrentWindow().close();
      });
  }, []);

  const handleSelected = useCallback(
    async (rect: SelectionRect) => {
      await emit("selection-result", rect);
      await getCurrentWindow().close();
    },
    [],
  );

  const handleCancel = useCallback(async () => {
    await emit("selection-cancelled");
    await getCurrentWindow().close();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleCancel().catch(console.error);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleCancel]);

  if (!screenshot) {
    return (
      <canvas
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          display: "block",
          background: "#000",
        }}
      />
    );
  }

  return (
    <RegionSelector
      screenshotBase64={screenshot}
      onSelected={handleSelected}
      onCancel={handleCancel}
    />
  );
}
