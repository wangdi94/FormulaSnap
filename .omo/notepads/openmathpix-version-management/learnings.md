
## 版本同步脚本设计 (Task 2)

### 文件位置
- `scripts/sync-version.js` - ESM 格式版本同步脚本
- `package.json` 添加了 `version:sync`、`postversion`、`prebuild` 三个脚本

### 关键决策
1. **使用独立脚本文件而非内联** - package.json 设置了 `"type": "module"`，内联 `node -e` 的 `require()` 不兼容，且内联脚本太长难以维护
2. **使用 postversion 钩子** - `pnpm version` 更新 package.json 后自动触发同步
3. **prebuild 确保构建前同步** - 防止手动修改版本后忘记同步

### 流程
- `pnpm version --no-git-tag-version x.y.z` → 更新 package.json → postversion 触发 sync-version.js → 同步到 Cargo.toml + tauri.conf.json
- `pnpm build` → prebuild 先运行 sync-version.js → 确保版本一致 → 再执行构建

### 验证结果
- 三个文件版本号成功同步
- LSP 诊断无错误
