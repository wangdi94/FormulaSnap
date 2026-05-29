# Learnings - fix-plan

## sidecarClient 测试
- 文件: `src/__tests__/sidecarClient.test.ts`
- vitest 配置: jsdom + globals, setupFiles 引用 `@testing-library/jest-dom`
- 测试内容: SidecarError 类、StatsResponse/OcrRequest/OcrResponse 接口结构、函数签名验证
- 需要 jsdom + @testing-library/jest-dom 依赖才能跑通 vitest

## hotkey.rs 内联测试
- 文件: `src-tauri/src/hotkey.rs`
- 改动: 提取 `CAPTURE_EVENT_NAME` 常量，添加 `#[cfg(test)] mod tests` 块
- 测试内容: 事件名称验证、平台条件编译逻辑（Ctrl/Shift vs Cmd/Shift）、函数签名编译检查
- **环境限制**: WSL 环境缺少 Tauri 系统依赖（libdbus-1-dev, libgtk-3-dev, libwebkit2gtk-4.1-dev 等），且无 sudo 权限安装，`cargo test` 无法在此环境运行
- 测试代码本身是正确的，需要在有完整 Tauri 依赖的环境中验证
