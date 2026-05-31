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
    (rect: SelectionRect) => {
      emit("selection-result", rect);
      setTimeout(() => getCurrentWindow().close(), 50);
    },
    [],
  );

  const handleCancel = useCallback(() => {
    getCurrentWindow().close();
  }, []);

  if (!screenshot) return null;

  return (
    <RegionSelector
      screenshotBase64={screenshot}
      onSelected={handleSelected}
      onCancel={handleCancel}
    />
  );
}
