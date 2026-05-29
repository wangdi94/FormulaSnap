# FormulaSnap

[![CI](https://github.com/wangdi94/FormulaSnap/actions/workflows/ci.yml/badge.svg)](https://github.com/wangdi94/FormulaSnap/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tauri v2](https://img.shields.io/badge/Tauri-v2-ffc131.svg)](https://tauri.app)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab.svg)](https://python.org)

> Screenshot → LaTeX math formula. 截图转 LaTeX 数学公式的桌面应用。

Tauri v2 外壳，React 前端，Python sidecar 提供 5 种 OCR 引擎。系统托盘常驻，快捷键一键截图识别数学公式。

## 功能

- 截图 OCR → LaTeX 公式（支持区域截图）
- 5 种 OCR 引擎：Pix2Text / Mathpix / OpenAI / Claude / Gemini
- 引擎管理器：熔断器 + 成本感知路由，自动选择最优引擎
- 系统托盘常驻，快捷键 `Ctrl+Shift+C`（macOS: `Cmd+Shift+C`）触发截图
- 历史记录管理，支持全文搜索（FTS5）
- 自动更新支持（macOS / Windows）
- 深色/浅色主题切换
- 中英文界面

## 开发环境

### 前置要求

- Node.js 22+
- pnpm
- Python 3.10+
- Rust 工具链

### 安装依赖

```bash
# 前端依赖
pnpm install

# Python sidecar 依赖
cd sidecar
pip install -e .
```

### 启动开发

```bash
# 方式一：完整桌面应用（推荐）
pnpm tauri dev

# 方式二：仅前端
pnpm dev

# 方式三：仅 sidecar
cd sidecar && python -m sidecar.main
```

## 构建

### 打包 Python Sidecar

```bash
cd sidecar

# Linux/macOS
./build.sh

# Windows
build.bat
```

输出：`src-tauri/binaries/formulasnap-sidecar-<平台三元组>`

### 构建桌面应用

```bash
pnpm tauri build
```

输出位于 `src-tauri/target/release/bundle/`：
- Windows: `.msi` / `.exe`
- macOS: `.dmg`
- Linux: `.deb` / `.AppImage`

## 测试

```bash
# Python 测试（176 个）
cd sidecar && pytest

# 前端测试（24 个）
pnpm test

# TypeScript 类型检查
npx tsc --noEmit --skipLibCheck
```

## 项目结构

```
FormulaSnap/
├── src/                    # React 前端 (TypeScript)
│   ├── pages/              # 4 个路由页面
│   ├── components/         # 9 个 UI 组件
│   ├── lib/                # 工具模块 (sidecarClient, settings, i18n...)
│   └── i18n/               # zh.json, en.json
├── src-tauri/              # Rust 后端 (Tauri v2)
│   └── src/                # 9 个模块 (db, screenshot, hotkey, tray, sidecar...)
├── sidecar/                # Python OCR 服务
│   └── sidecar/            # FastAPI 服务 + 5 个 OCR 引擎实现
└── .github/workflows/      # CI (测试) + Release (打包发布)
```

## 技术栈

| 层 | 技术 |
|---|------|
| 桌面外壳 | [Tauri v2](https://tauri.app) (Rust) |
| 前端 | React 18 + TypeScript + Tailwind CSS |
| OCR 服务 | Python 3.10+ / FastAPI |
| 数据库 | SQLite (rusqlite, bundled) |
| OCR 引擎 | Pix2Text / Mathpix / OpenAI GPT-4o / Claude Sonnet / Gemini 2.5 Pro |

## 架构

```
┌─────────────────────────────────────────────┐
│                  Tauri v2                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ React UI │──│ Rust 后端 │──│ SQLite DB │  │
│  └────┬─────┘  └──────────┘  └───────────┘  │
│       │ HTTP (port 8477)                     │
│  ┌────▼─────────────────────────────────┐   │
│  │        Python Sidecar (FastAPI)       │   │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐  │   │
│  │  │Pix2Text │ │Mathpix │ │ OpenAI  │  │   │
│  │  └─────────┘ └────────┘ └─────────┘  │   │
│  │  ┌─────────┐ ┌────────┐              │   │
│  │  │ Claude  │ │ Gemini │              │   │
│  │  └─────────┘ └────────┘              │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

- **前端 → Sidecar 直连**：React 通过 HTTP 直接调用 Python sidecar（端口 8477），不经过 Rust 层
- **引擎管理器**：熔断器 + 成本感知路由，自动选择最优 OCR 引擎
- **设置存储**：Rust DB（应用设置）、localStorage（主题/语言）、Python keyring（API 密钥）

## 发布

```bash
# 打标签触发 CI 构建
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions 会自动构建三平台安装包并创建 Release（draft 模式）。

## 许可证

[MIT License](LICENSE)
