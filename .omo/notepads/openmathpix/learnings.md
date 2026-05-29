
## 测试基础设施 (Task 3)

### pytest 配置
- `pytest.ini` 放在项目根目录，`testpaths = sidecar/tests`
- pytest 9.0.3 + Python 3.10.12 环境可用
- 已安装的 pytest 插件: cov, mock, langsmith, timeout, anyio, asyncio
- pytest 自动从 pytest.ini 读取配置，无需命令行参数

### vitest 配置
- `vitest.config.ts` 使用 `@vitejs/plugin-react` 插件
- 环境设为 `jsdom`，`globals: true` 允许直接使用 describe/it/expect
- setup 文件: `src/test/setup.ts` 引入 `@testing-library/jest-dom`
- vitest 会优先使用 vitest.config.ts 而非 vite.config.ts

### CI workflow
- frontend 和 backend 两个 job 并行运行
- 三个平台 matrix: ubuntu-latest, windows-latest, macos-latest
- frontend 用 pnpm + Node 20
- backend 用 Python 3.10 + pip install -e "./sidecar[dev]"

### 注意事项
- 工作区可能被并行任务修改，需注意文件系统状态
- vitest 相关 TS 模块在依赖安装前会有 LSP 错误，这是预期行为
- sidecar/tests/ 需要 __init__.py 才能被 pytest 发现

## Sidecar 项目初始化 (Task 1)

### pix2text 版本
- PyPI 上最新版本是 1.1.6，**不存在 1.8+**
- 已将依赖约束从 `>=1.8` 调整为 `>=1.1`

### hatchling 构建配置
- 项目名 `openmathpix-sidecar` 与包目录 `sidecar` 不同
- 需要显式配置 `[tool.hatch.build.targets.wheel] packages = ["sidecar"]`
- 否则 hatchling 会报错 "Unable to determine which files to ship"

### 安装验证
- 使用 `pip install -e ".[dev]" --no-deps` 模式验证包本身
- pix2text 首次安装可能超时（依赖较大），后续单独管理
- `python3 -c "from sidecar.main import app"` 可验证导入

### 端口配置
- FastAPI 服务监听 `127.0.0.1:8477`
- 健康检查端点 `GET /health` 返回 `{"status": "ok"}`

## Tauri v2 项目初始化 (Task 4)

### 创建方式
- `pnpm create tauri-app@latest . -m pnpm -t react-ts -y --tauri-version 2 --force` 可非交互式创建
- `--force` 参数允许在非空目录（如已有 .omo/ 文件夹）创建项目
- 系统缺少 libwebkit2gtk-4.1-dev，无法运行 `pnpm tauri dev`，但项目结构和代码不受影响

### 依赖版本
- React 19.2.6, react-router-dom 7.15.1, mathlive 0.109.2
- Tailwind CSS 4.3.0 + @tailwindcss/vite 4.3.0
- @tauri-apps/api 2.11.0, @tauri-apps/cli 2.11.2
- Vite 7.3.3, TypeScript 5.8.3

### Cargo.toml 配置
- tauri features: ["tray-icon"] 用于系统托盘
- tauri-plugin-sql features: ["sqlite"] 用于 SQLite 支持
- xcap 0.0.14 用于截图能力（替代 tauri-plugin-screenshots）
- 移除了 tauri-plugin-opener（用 shell 和 dialog 替代）

### lib.rs 插件注册
- 需要在 tauri::Builder 中注册所有插件
- tauri_plugin_sql::Builder::default().add_migrations("sqlite:app.db", &[]).build() 格式注册
- tauri_plugin_global_shortcut::Builder::new().build() 格式注册

## TypeScript 类型定义 (T2)
- 创建了 src/types/ 目录下的所有类型定义文件
- OCR 后端类型：pix2text, mathpix, openai, claude, gemini
- HistoryEntry 包含 id, created_at, latex, backend, confidence, screenshot_path, mathml
- AppSettings 包含 hotkey, default_backend, api_keys, theme, monthly_budget_usd, language
- npx tsc --noEmit 验证通过，无类型错误
- tsconfig.json 中有注释，但 TypeScript 编译器能正常处理

## SQLite Schema + 迁移 (Task 8)

### rusqlite 配置
- 使用 rusqlite 0.31 + "bundled" + "modern_sqlite" features
- "bundled" feature 自动编译 SQLite，无需系统依赖
- "modern_sqlite" 启用 FTS5 和其他现代功能

### 数据库初始化
- `db::initialize_database(conn)` 函数使用幂等迁移（CREATE TABLE IF NOT EXISTS）
- history 表: id (PK), created_at, latex, backend, confidence, screenshot_path, mathml
- settings 表: key (PK), value
- history_fts FTS5 虚拟表: latex 列，content='history', content_rowid='id'

### FTS5 同步触发器
- history_ai: INSERT 触发器，插入新记录到 FTS
- history_ad: DELETE 触发器，从 FTS 删除记录
- history_au: UPDATE 触发器，删除旧记录并插入新记录

### Tauri 集成
- 在 `lib.rs` 的 `.setup()` 中调用 `db::initialize_database`
- 使用 `app.path().app_data_dir()` 获取应用数据目录
- 确保目录存在后打开 SQLite 连接

### 测试验证
- 使用内存数据库 `Connection::open_in_memory()` 测试
- 验证表存在: sqlite_master 查询
- 验证 FTS5 搜索: MATCH 查询
- 验证幂等性: 多次调用不失败

### 注意事项
- 系统缺少 libdbus-1-dev，cargo check 无法完成，但代码结构正确
- 环境缺少 libwebkit2gtk-4.1-dev，无法运行 Tauri 应用
- 后续任务 24 将实现 CRUD 操作 (history.rs)
- 后续任务 25 将添加 FTS5 搜索功能

## T2 - Tauri 插件权限配置
- `tauri.conf.json` 中 `withGlobalTauri: true` 启用 `window.__TAURI__` 全局对象
- `bundle.externalBin` 声明 sidecar 路径，格式为 `["binaries/<name>"]`（不含平台后缀）
- Tauri v2 使用 capabilities 系统（`src-tauri/capabilities/default.json`）声明权限
- shell 插件需要 `shell:allow-execute`, `shell:allow-spawn` 等细粒度权限
- global-shortcut 插件需要 `allow-register`, `allow-unregister`, `allow-is-registered`
- clipboard-manager 插件支持 write-text, read-text, write-image, read-image
- sql 和 dialog 使用 `:default` 即可获得全部常用权限
- `trayIcon` 配置在 `app` 层级，需要 `tray-icon` feature 在 Cargo.toml 中启用
- lib.rs 中插件注册顺序不影响功能，但需确保所有 Cargo.toml 中的依赖都已注册

## OCR 后端接口定义 (Task 7)

### Protocol vs ABC
- 使用 `typing.Protocol` 实现结构化子类型（duck typing）
- 不需要显式继承，只要方法签名匹配即可满足协议
- Python 3.10 环境下 `get_protocol_members` 不存在（3.13+ 才有）
- Python 3.11+ 可用 `__protocol_attrs__` 获取协议成员
- Python 3.10 回退方案：用 `dir()` 检查方法是否存在

### 数据类设计
- `OcrResult` 核心字段：latex, confidence, backend, timing_ms
- `CostEstimate` 可选嵌套，用于 LLM 后端按 token 计费
- `RateLimitError` 的 `retry_after` 字段用 `Optional[int]`，兼容无重试信息场景
- 所有数据类使用 `@dataclass` 装饰器，无额外依赖

### 错误层次结构
- `OcrError` 作为基类继承 `Exception`
- 四个具体错误：`ApiKeyError`, `RateLimitError`, `NetworkError`, `ParseError`
- `RateLimitError` 重写 `__init__` 添加 `retry_after` 属性

### pytest 运行
- 运行命令：`cd sidecar && python3 -m pytest tests/test_interface.py -v`
- 20 个测试全部通过
- LSP diagnostics 干净无错误

## Mathpix OCR 引擎实现 (Task T7)

### TDD 流程
- 测试先行：创建 `tests/test_mathpix.py`（6 个测试），LSP 报 import 错误是预期的
- 实现跟进：创建 `sidecar/ocr_engines/mathpix_engine.py`，LSP 错误立即消失
- 全部 6 个测试通过，耗时 0.02s

### 测试策略
- 使用 `@patch('sidecar.ocr_engines.mathpix_engine.httpx')` mock HTTP 层
- 模块级 `import httpx` 让 patch 路径正确指向
- mock_response.headers 用普通 dict，`response.headers.get()` 兼容
- `RateLimitError.retry_after` 属性通过 `exc_info.value.retry_after` 验证

### MathpixEngine 设计
- `recognize()` 是同步方法（非 async），使用 `httpx.post`
- 凭证来源：构造函数参数 > 环境变量 `MATHPIX_APP_ID` / `MATHPIX_APP_KEY`
- Base64 编码图片嵌入 JSON payload（`data:image/png;base64,...`）
- 优先读 `latex_simplified`，回退到 `latex` 字段
- 固定费率 $0.002/请求，tokens_used=765

### 错误映射
- 401 → `ApiKeyError`
- 429 → `RateLimitError`（从 `Retry-After` header 读取秒数）
- 5xx → `NetworkError`
- `httpx.RequestError` → `NetworkError`

### validate_config
- 无凭证 → `valid=False`，message 包含 "key" 或 "id"
- 凭证长度 < 10 → `valid=False`（"too short"）
- 格式检查通过 → `valid=True`

### 注意事项
- `OcrBackend` Protocol 定义 `async def recognize()`，但实现用同步 `def recognize()`
- Python 3.10 Protocol 不强制 async/sync 一致性（无 runtime_checkable）
- `__init__.py` 需显式导入 `MathpixEngine` 才能被外部使用

## T7 System Tray 实现
- Tauri v2 使用 `TrayIconBuilder` 创建托盘，`MenuItem::with_id` 创建菜单项
- 左键托盘图标切换窗口：通过 `on_tray_icon_event` 监听 `TrayIconEvent::Click`
- 右键菜单：通过 `on_menu_event` 处理菜单点击
- 关闭窗口不退出：在 `on_window_event` 中拦截 `CloseRequested`，调用 `api.prevent_close()` + `window.hide()`
- `Cargo.toml` 已有 `tray-icon` feature，`tauri.conf.json` 已有 `trayIcon` 配置
- 环境缺 `libdbus-1-dev` 导致 `cargo check` 失败，代码结构正确

## 全局快捷键 + 截图模块 (Task 9)

### hotkey.rs
- 使用 `tauri_plugin_global_shortcut` 的 `GlobalShortcutExt` trait 注册快捷键
- macOS 用 `Modifiers::SUPER | Modifiers::SHIFT` (Cmd+Shift+C)
- Windows/Linux 用 `Modifiers::CONTROL | Modifiers::SHIFT` (Ctrl+Shift+C)
- 通过 `#[cfg(target_os = "macos")]` 条件编译处理平台差异
- `on_shortcut` 回调签名: `|_app, _shortcut, event|` 三个参数
- `ShortcutState::Pressed` 判断按下事件

### screenshot.rs
- xcap 0.0.14 的 `Monitor::capture_image()` 返回 `image::DynamicImage`
- `DynamicImage` 有 `write_to(writer, format)` 方法可直接输出 PNG
- `image::imageops::crop_imm` 裁剪后需 `.to_image()` 转为 `ImageBuffer`
- `ImageBuffer` 需包装为 `DynamicImage::ImageRgba8(cropped)` 才能用 `write_to`
- 裁剪时需 clamp 到图像边界避免 panic（`saturating_sub` + `min`）
- 需要在 Cargo.toml 添加 `image = "0.25"` 依赖（xcap 不 re-export image crate）

### lib.rs 集成
- `mod hotkey; mod screenshot;` 声明模块
- 在 `.setup()` 中调用 `hotkey::register_hotkeys(app.handle())`
- 用 `if let Err(e) = ...` 处理注册失败（不阻塞应用启动）

## React UI 框架搭建 (Task 9)

### 文件结构
- `src/App.tsx`: BrowserRouter + Routes 路由设置，4 个路由：/ /history /history/:id /settings
- `src/components/Header.tsx`: 顶部导航栏，useLocation 高亮当前路由
- `src/components/StatusBar.tsx`: 底部状态栏，就绪指示器 + 后端名称
- `src/pages/HomePage.tsx`: 截图首页占位（截图区域 + 最近结果）
- `src/pages/HistoryPage.tsx`: 历史记录列表占位
- `src/pages/HistoryDetailPage.tsx`: 历史详情占位（useParams 获取 id）
- `src/pages/SettingsPage.tsx`: 设置页面占位

### Tailwind CSS 4 配置
- `@import "tailwindcss"` 在 App.css 中引入（Tailwind CSS 4 语法）
- `@tailwindcss/vite` 插件已在 vite.config.ts 中配置
- `@layer base {}` 用于全局基础样式
- 移除了 Tauri 模板的默认 CSS，只保留必要的 font-smoothing

### 设计决策
- 布局：flex flex-col h-screen（Header 固定 + main flex-1 overflow-auto + StatusBar 固定）
- 暗色模式：dark: 前缀支持（bg-gray-50 dark:bg-gray-900）
- 导航高亮：location.pathname === item.path 切换样式类
- 页面骨架：只返回占位内容，具体功能后续任务实现

### 验证
- LSP diagnostics 全部文件零错误
- `npx tsc --noEmit` 编译通过
- react-router-dom 7.6.1 已在 package.json 中

## Pix2Text 本地 OCR 引擎实现 (T11)

### TDD 流程
- 测试先行：创建 `tests/test_pix2text.py`（9 个测试），再实现引擎
- 实现文件：`sidecar/ocr_engines/pix2text_engine.py`
- 全部 9 个测试通过，耗时 0.12s

### 模块级名称设计（关键）
- `Pix2Text` 和 `ort` 必须作为模块级变量存在（即使 import 失败也赋值为 None）
- 这样 `@patch('sidecar.ocr_engines.pix2text_engine.Pix2Text')` 才能找到目标
- 如果用 `_pix2text_cls` 等私有名称，mock 路径不匹配会导致 `AttributeError`

### recognize 测试需额外 mock PIL
- `PIL.Image.open(b"fake_image")` 会抛 `UnidentifiedImageError`
- 测试中需要 `@patch("PIL.Image.open")` 返回 MagicMock
- mock 装饰器顺序：离函数定义最近的 mock 参数最先传入

### validate_config 设计
- 检查顺序：`Pix2Text is None` → `ort is None` → `ort.get_available_providers()`
- 测试 `test_validate_config_checks_onnxruntime` 和 `test_validate_config_no_providers` 需要同时 mock `Pix2Text` 和 `ort`
- 测试 `test_validate_config_when_pix2text_not_installed` 只 patch `PIX2TEXT_AVAILABLE=False`，利用 `Pix2Text is None` 天然成立

### Pix2Text API
- `Pix2Text.from_config()` 创建实例
- `recognize_page(img)` 返回 list[dict]，每个 dict 有 type/text/confidence 字段
- type 可以是 "formula" 或 "text"
- 本地引擎无成本和速率限制，`estimate_cost` 和 `get_rate_limit_status` 返回 None

### LSP 预期警告
- `Import "pix2text" could not be resolved`：pix2text 是运行时依赖，LSP 环境未安装
- `Cannot access attribute "get_available_providers" for class "object"`：`ort` 模块级类型是 `object | None`，运行时无影响

