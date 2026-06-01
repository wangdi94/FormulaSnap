import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { emit } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import RegionSelector from "../components/RegionSelector";

interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export default function SelectionPage() {
  const [screenshot, setScreenshot] = useState<string | null>(null);

  useEffect(() => {
    invoke<string>("capture_screen_for_selection")
      .then(setScreenshot)
      .catch((err) => {
        console.error("Failed to capture screen for selection:", err);
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
        handleCancel();
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
          background: "transparent",
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
