import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const rootEl = document.getElementById("root");
if (rootEl) {
  // React 挂载时会自然替换 #root 的全部子元素（包括 loading fallback）。
  // 如果 React 渲染失败，fallback 保留不动，用户仍能看到加载状态和错误信息。
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
