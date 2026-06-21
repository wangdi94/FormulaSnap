import { useState, useEffect, useCallback } from "react";
import { listen, emit } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import RegionSelector from "../components/RegionSelector";
import type { SelectionRect } from "../types/ocr";

export default function SelectionPage() {
  const [screenshot, setScreenshot] = useState<string | null>(null);

  useEffect(() => {
    console.log("[SelectionPage] 等待预截图数据...");

    const unlisten = listen<string>("pre-capture", (event) => {
      console.log("[SelectionPage] 收到预截图数据，长度:", event.payload.length);
      setScreenshot(event.payload);
    });

    return () => {
      unlisten.then((fn) => fn());
    };
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
