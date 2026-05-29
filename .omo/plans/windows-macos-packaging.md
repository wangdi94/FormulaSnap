# OpenMathpix Windows + macOS 打包方案

## TL;DR

> **Quick Summary**: 将 OpenMathpix 桌面应用打包成 Windows NSIS 安装包和 macOS DMG，包含 Python sidecar 的 PyInstaller 打包、自动更新功能配置，以及基于 Git tag 的自动化发布工作流。
> 
> **Deliverables**:
> - Windows NSIS 安装包（.exe）
> - macOS DMG 安装包（.dmg）
> - Python sidecar 单文件可执行程序
> - 自动更新功能（Tauri updater）
> - GitHub Actions 自动化发布工作流
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 4 → Task 6/7 → Task 9 → F1-F4

---

## Context

### Original Request
用户希望将 OpenMathpix 应用打包成 Windows 安装包，经讨论后扩展为同时支持 Windows + macOS。

### Interview Summary
**Key Discussions**:
- **Windows 格式**: NSIS 安装包（现代安装向导，用户体验好）
- **macOS 格式**: DMG（标准 macOS 安装方式）
- **Python sidecar**: 使用 PyInstaller 打包成单个可执行文件
- **平台支持**: Windows + macOS
- **代码签名**: 暂不需要（成本考虑）
- **自动更新**: 需要（使用 Tauri 内置更新器）
- **版本号**: 基于 Git tag 自动生成

**Research Findings**:
- 项目使用 Tauri v2 + React + TypeScript
- Python sidecar 使用 FastAPI + pix2text OCR
- `tauri.conf.json` 已配置 `externalBin: ["binaries/openmathpix-sidecar"]`
- `src-tauri/binaries/` 目录为空，需要构建 sidecar
- 现有 CI 工作流只运行测试，不包含打包

---

## Work Objectives

### Core Objective
完成 OpenMathpix 应用的完整打包流程，支持 Windows 和 macOS 平台，并实现自动化发布。

### Concrete Deliverables
- PyInstaller 配置文件和构建脚本
- 更新后的 `tauri.conf.json` 配置
- Tauri updater 插件集成
- GitHub Actions release 工作流
- 打包文档

### Definition of Done
- [ ] `pnpm tauri build` 成功生成 Windows NSIS 安装包
- [ ] `pnpm tauri build` 成功生成 macOS DMG 安装包
- [ ] Python sidecar 被打包成单个可执行文件
- [ ] 应用启动时自动检查更新
- [ ] 推送 Git tag 时自动触发 GitHub Actions 构建和发布

### Must Have
- Windows NSIS 安装包
- macOS DMG 安装包
- PyInstaller 打包 Python sidecar
- Tauri updater 自动更新功能
- GitHub Actions 自动化发布工作流

### Must NOT Have (Guardrails)
- 不要修改现有业务逻辑代码
- 不要添加代码签名（暂不需要）
- 不要创建新的数据库或存储结构
- 不要修改前端 UI 组件
- 不要添加新的 Python 依赖（除非打包必需）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES（现有 CI 运行 pytest 和 vitest）
- **Automated tests**: Tests-after（打包配置完成后验证）
- **Framework**: pytest + vitest
- **验证重点**: 打包产物是否正确生成，自动更新是否配置正确

### QA Policy
每个任务必须包含 agent-executed QA scenarios。
Evidence 保存到 `.omo/evidence/task-{N}-{scenario-slug}.{ext}`。

- **打包产物验证**: 使用 Bash 检查文件是否存在、大小是否合理
- **配置验证**: 使用 Bash 运行 JSON 语法检查
- **构建验证**: 使用 Bash 运行 `pnpm tauri build` 并检查输出

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - 基础配置):
├── Task 1: PyInstaller 配置文件 [quick]
├── Task 2: 更新 package.json 版本号脚本 [quick]
├── Task 3: 配置 Tauri updater 插件 [unspecified-high]
└── Task 4: 生成签名密钥对 [quick]

Wave 2 (After Wave 1 - 核心打包):
├── Task 5: 创建 PyInstaller 构建脚本 [unspecified-high]
├── Task 6: 更新 tauri.conf.json 打包配置 [quick]
├── Task 7: 集成 updater 到前端代码 [unspecified-high]
└── Task 8: 更新 Tauri 权限配置 [quick]

Wave 3 (After Wave 2 - 自动化发布):
├── Task 9: 创建 GitHub Actions release 工作流 [unspecified-high]
└── Task 10: 创建打包文档 [writing]

Wave FINAL (After ALL tasks — 4 parallel reviews, then user okay):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 4 → Task 6/7 → Task 9 → F1-F4 → user okay
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 4 (Waves 1 & 2)
Wave 3: 2 tasks — T9 first, then T10 (sequential, T10 blocked on T9)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|------------|--------|
| 1 | - | 5 |
| 2 | - | 9 |
| 3 | - | 7 |
| 4 | - | 9 |
| 5 | 1 | 9 |
| 6 | 4 | 9 |
| 7 | 3 | 9 |
| 8 | - | 9 |
| 9 | 2, 4, 5, 6, 7, 8 | F1-F4 |
| 10 | 5, 9 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks - T1 → `quick`, T2 → `quick`, T3 → `unspecified-high`, T4 → `quick`
- **Wave 2**: 4 tasks - T5 → `unspecified-high`, T6 → `quick`, T7 → `unspecified-high`, T8 → `quick`
- **Wave 3**: 2 tasks - T9 → `unspecified-high`, T10 → `writing`
- **FINAL**: 4 tasks - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. 创建 PyInstaller 配置文件

  **What to do**:
  - 在 `sidecar/` 目录创建 `pyinstaller.spec` 文件
  - 配置入口点为 `sidecar.main:main`
  - 添加所有必要的 hidden imports（pix2text, onnxruntime, fastapi 等）
  - 配置数据文件包含（模型文件等）
  - 设置单文件模式（--onefile）
  - 配置控制台窗口（--console）

  **Must NOT do**:
  - 不要修改现有的 Python 代码
  - 不要添加新的 Python 依赖
  - 不要修改 pyproject.toml

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: PyInstaller 配置是标准操作，不需要深度研究
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 5
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `sidecar/pyproject.toml` - 查看项目依赖，确定 hidden imports
  - `sidecar/sidecar/main.py` - 入口点文件，确认 main() 函数

  **API/Type References**:
  - PyInstaller 官方文档：https://pyinstaller.org/en/stable/spec-files.html

  **WHY Each Reference Matters**:
  - `pyproject.toml`: 列出了所有运行时依赖，需要添加到 hidden imports
  - `main.py`: 确认入口点函数名和导入路径

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: PyInstaller spec 文件语法验证
    Tool: Bash
    Preconditions: sidecar/pyinstaller.spec 文件存在
    Steps:
      1. 运行 `cd sidecar && pyinstaller --version` 确认 PyInstaller 已安装
      2. 运行 `pyinstaller pyinstaller.spec --help` 检查 spec 文件语法
    Expected Result: 命令成功执行，无语法错误
    Failure Indicators: 出现 "Error" 或 "Invalid" 错误信息
    Evidence: .omo/evidence/task-1-pyinstaller-spec-validation.txt

  Scenario: Spec 文件内容完整性检查
    Tool: Bash
    Preconditions: sidecar/pyinstaller.spec 文件存在
    Steps:
      1. 读取 spec 文件内容
      2. 验证包含 `Analysis` 部分
      3. 验证包含 `PYZ` 部分
      4. 验证包含 `EXE` 部分
      5. 验证入口点配置正确
    Expected Result: spec 文件包含所有必要部分，入口点为 sidecar.main:main
    Failure Indicators: 缺少必要部分或入口点配置错误
    Evidence: .omo/evidence/task-1-spec-content-check.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 添加 PyInstaller 配置文件`
  - Files: `sidecar/pyinstaller.spec`
  - Pre-commit: `cd sidecar && pyinstaller pyinstaller.spec --help`

- [x] 2. 更新 package.json 添加版本号管理脚本

  **What to do**:
  - 在 `package.json` 的 `scripts` 中添加版本号管理脚本
  - 添加 `version` 脚本用于从 Git tag 同步版本号
  - 添加 `prebuild` 脚本在构建前自动同步版本号
  - 配置 `standard-version` 或类似工具用于版本号管理

  **Must NOT do**:
  - 不要修改现有的 scripts
  - 不要添加新的依赖（除非版本管理必需）
  - 不要修改项目结构

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: package.json 脚本配置是标准操作
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Task 9
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `package.json` - 现有脚本配置，了解项目结构
  - `src-tauri/Cargo.toml` - Rust 项目版本号，需要同步
  - `src-tauri/tauri.conf.json` - Tauri 配置版本号，需要同步

  **WHY Each Reference Matters**:
  - `package.json`: 了解现有脚本格式和项目结构
  - `Cargo.toml` 和 `tauri.conf.json`: 版本号需要在三个地方保持同步

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 版本号脚本功能验证
    Tool: Bash
    Preconditions: package.json 已更新
    Steps:
      1. 运行 `pnpm version --no-git-tag-version 1.2.3` 测试版本号更新
      2. 检查 package.json 版本号是否更新为 1.2.3
      3. 检查 src-tauri/Cargo.toml 版本号是否同步更新
      4. 检查 src-tauri/tauri.conf.json 版本号是否同步更新
      5. 还原版本号为 0.1.0
    Expected Result: 三个文件的版本号都更新为 1.2.3
    Failure Indicators: 任一文件版本号未更新或不一致
    Evidence: .omo/evidence/task-2-version-sync.txt

  Scenario: Git tag 版本号同步验证
    Tool: Bash
    Preconditions: 版本号管理脚本已配置
    Steps:
      1. 创建测试 Git tag: `git tag v1.2.3`
      2. 运行版本号同步脚本
      3. 检查 package.json 版本号是否更新为 1.2.3
      4. 删除测试 tag: `git tag -d v1.2.3`
    Expected Result: 版本号从 Git tag 正确同步
    Failure Indicators: 版本号未更新或格式错误
    Evidence: .omo/evidence/task-2-git-tag-sync.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 添加版本号管理脚本`
  - Files: `package.json`
  - Pre-commit: `pnpm version --no-git-tag-version 0.1.0`

- [x] 3. 配置 Tauri updater 插件依赖

  **What to do**:
  - 在 `src-tauri/Cargo.toml` 中添加 `tauri-plugin-updater` 依赖
  - 配置平台条件编译（仅 macOS 和 Windows）
  - 添加 `tauri-plugin-process` 依赖用于 relaunch
  - 更新 `src-tauri/src/lib.rs` 初始化 updater 插件

  **Must NOT do**:
  - 不要修改现有的 Tauri 配置
  - 不要添加不需要的插件
  - 不要修改前端代码

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解 Tauri 插件系统和条件编译
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 7
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src-tauri/Cargo.toml` - 现有依赖配置，了解格式
  - `src-tauri/src/lib.rs` - 现有插件初始化代码
  - `src-tauri/capabilities/default.json` - 权限配置

  **External References**:
  - Tauri updater 文档：https://tauri.app/plugin/updater/
  - Tauri v2 插件系统：https://tauri.app/develop/plugins/

  **WHY Each Reference Matters**:
  - `Cargo.toml`: 了解现有依赖格式和版本约束
  - `lib.rs`: 了解插件初始化模式
  - `capabilities/default.json`: 了解权限配置方式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Cargo.toml 依赖验证
    Tool: Bash
    Preconditions: src-tauri/Cargo.toml 已更新
    Steps:
      1. 运行 `cd src-tauri && cargo check` 检查依赖是否正确
      2. 验证 tauri-plugin-updater 依赖存在
      3. 验证平台条件编译配置正确
    Expected Result: cargo check 成功，无编译错误
    Failure Indicators: 出现依赖解析错误或编译错误
    Evidence: .omo/evidence/task-3-cargo-check.txt

  Scenario: lib.rs 插件初始化验证
    Tool: Bash
    Preconditions: src-tauri/src/lib.rs 已更新
    Steps:
      1. 运行 `cd src-tauri && cargo check` 检查代码
      2. 验证 updater 插件初始化代码存在
      3. 验证条件编译配置正确
    Expected Result: 代码编译通过，无错误
    Failure Indicators: 出现编译错误或警告
    Evidence: .omo/evidence/task-3-lib-rs-check.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 添加 Tauri updater 插件依赖`
  - Files: `src-tauri/Cargo.toml`, `src-tauri/src/lib.rs`
  - Pre-commit: `cd src-tauri && cargo check`

- [x] 4. 生成 Tauri 签名密钥对

  **What to do**:
  - 使用 `tauri signer generate` 生成签名密钥对
  - 将私钥保存到安全位置（~/.tauri/openmathpix.key）
  - 提取公钥内容用于 tauri.conf.json 配置
  - 创建说明文档记录密钥管理流程

  **Must NOT do**:
  - 不要将私钥提交到版本控制
  - 不要在代码中硬编码密钥
  - 不要修改现有配置

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 密钥生成是标准命令行操作
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Task 9
  - **Blocked By**: None (can start immediately)

  **References**:

  **External References**:
  - Tauri 签名文档：https://tauri.app/distribute/sign/

  **WHY Each Reference Matters**:
  - 签名文档：了解密钥生成命令和最佳实践

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 密钥对生成验证
    Tool: Bash
    Preconditions: Tauri CLI 已安装
    Steps:
      1. 运行 `pnpm tauri signer generate -w ~/.tauri/openmathpix.key` 生成密钥对
      2. 检查私钥文件是否存在：`ls -la ~/.tauri/openmathpix.key`
      3. 提取公钥内容：`cat ~/.tauri/openmathpix.key.pub`
    Expected Result: 密钥对成功生成，私钥文件存在
    Failure Indicators: 命令执行失败或文件不存在
    Evidence: .omo/evidence/task-4-key-generation.txt

  Scenario: 公钥内容格式验证
    Tool: Bash
    Preconditions: 密钥对已生成
    Steps:
      1. 读取公钥文件内容
      2. 验证内容以 "age" 开头（age 加密格式）
      3. 验证内容长度合理（约 60-70 字符）
    Expected Result: 公钥内容格式正确
    Failure Indicators: 格式错误或内容异常
    Evidence: .omo/evidence/task-4-pubkey-format.txt
  ```

  **Commit**: NO（密钥文件不应提交到版本控制）

- [x] 5. 创建 PyInstaller 构建脚本

  **What to do**:
  - 创建 `sidecar/build.sh` 和 `sidecar/build.bat` 构建脚本
  - 脚本应自动检测平台并调用 PyInstaller
  - 配置输出目录为 `src-tauri/binaries/`
  - 添加构建前清理逻辑
  - 配置平台特定的可执行文件命名（Windows: .exe, macOS: 无后缀）

  **Must NOT do**:
  - 不要修改现有的构建流程
  - 不要添加复杂的构建逻辑
  - 不要修改 PyInstaller spec 文件

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要处理跨平台构建逻辑
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `sidecar/pyinstaller.spec` - PyInstaller 配置文件（Task 1 创建）
  - `src-tauri/binaries/` - 目标输出目录
  - `src-tauri/tauri.conf.json` - externalBin 配置，了解命名要求

  **WHY Each Reference Matters**:
  - `pyinstaller.spec`: 构建脚本需要调用此配置文件
  - `binaries/`: 了解目标目录结构和命名要求
  - `tauri.conf.json`: 了解 sidecar 命名约定

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 构建脚本语法验证
    Tool: Bash
    Preconditions: 构建脚本已创建
    Steps:
      1. 检查 `sidecar/build.sh` 文件权限：`ls -la sidecar/build.sh`
      2. 验证脚本可执行：`chmod +x sidecar/build.sh && ./sidecar/build.sh --help`（如果有帮助选项）
      3. 检查 `sidecar/build.bat` 文件存在
    Expected Result: 脚本文件存在且有执行权限
    Failure Indicators: 文件不存在或无执行权限
    Evidence: .omo/evidence/task-5-build-script-check.txt

  Scenario: 构建脚本输出目录验证
    Tool: Bash
    Preconditions: 构建脚本已创建
    Steps:
      1. 读取构建脚本内容
      2. 验证输出目录配置为 `src-tauri/binaries/`
      3. 验证可执行文件命名约定正确
    Expected Result: 输出目录和命名配置正确
    Failure Indicators: 输出目录错误或命名约定不正确
    Evidence: .omo/evidence/task-5-output-dir-check.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 添加 PyInstaller 构建脚本`
  - Files: `sidecar/build.sh`, `sidecar/build.bat`
  - Pre-commit: `chmod +x sidecar/build.sh`

- [x] 6. 更新 tauri.conf.json 打包配置

  **What to do**:
  - 更新 `src-tauri/tauri.conf.json` 添加 updater 配置
  - 配置 `createUpdaterArtifacts: true`
  - 添加 updater endpoints（GitHub Releases）
  - 配置 pubkey（从 Task 4 获取）
  - 设置 Windows installMode 为 "passive"

  **Must NOT do**:
  - 不要修改现有的 app 配置
  - 不要修改 bundle 的其他配置
  - 不要添加不需要的配置项

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: JSON 配置更新是标准操作
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7, 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 4

  **References**:

  **Pattern References**:
  - `src-tauri/tauri.conf.json` - 现有配置，了解结构
  - Task 4 生成的公钥内容

  **External References**:
  - Tauri updater 配置文档：https://tauri.app/plugin/updater/

  **WHY Each Reference Matters**:
  - `tauri.conf.json`: 了解现有配置结构和格式
  - 公钥内容: 用于配置 pubkey 字段

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: tauri.conf.json 语法验证
    Tool: Bash
    Preconditions: tauri.conf.json 已更新
    Steps:
      1. 运行 `pnpm tauri info` 检查配置是否正确加载
      2. 验证 JSON 语法正确：`python -m json.tool src-tauri/tauri.conf.json`
    Expected Result: 配置加载成功，JSON 语法正确
    Failure Indicators: 配置加载失败或 JSON 语法错误
    Evidence: .omo/evidence/task-6-config-validation.txt

  Scenario: Updater 配置完整性检查
    Tool: Bash
    Preconditions: tauri.conf.json 已更新
    Steps:
      1. 读取 tauri.conf.json 内容
      2. 验证 `bundle.createUpdaterArtifacts` 为 true
      3. 验证 `plugins.updater` 配置存在
      4. 验证 `plugins.updater.pubkey` 不为空
      5. 验证 `plugins.updater.endpoints` 数组存在
    Expected Result: updater 配置完整且正确
    Failure Indicators: 配置缺失或格式错误
    Evidence: .omo/evidence/task-6-updater-config-check.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 配置 Tauri updater`
  - Files: `src-tauri/tauri.conf.json`
  - Pre-commit: `pnpm tauri info`

- [x] 7. 集成 updater 到前端代码

  **What to do**:
  - 创建 `src/lib/updater.ts` 更新检查模块
  - 实现 `checkForUpdates()` 函数
  - 实现 `downloadAndInstall()` 函数
  - 添加更新进度回调
  - 在应用启动时自动检查更新（可选）

  **Must NOT do**:
  - 不要修改现有的 UI 组件
  - 不要添加复杂的更新 UI
  - 不要强制用户更新

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解 Tauri API 和异步编程
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 8)
  - **Blocks**: Task 9
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `src/lib/` - 现有工具库结构
  - `src/App.tsx` - 应用入口，了解启动流程
  - `src-tauri/capabilities/default.json` - 权限配置

  **External References**:
  - Tauri updater JavaScript API：https://tauri.app/plugin/updater/#javascript

  **WHY Each Reference Matters**:
  - `src/lib/`: 了解现有工具库组织方式
  - `App.tsx`: 了解应用启动流程，确定更新检查时机
  - `capabilities/default.json`: 了解权限配置

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: updater 模块导入验证
    Tool: Bash
    Preconditions: src/lib/updater.ts 已创建
    Steps:
      1. 运行 `pnpm run build` 检查 TypeScript 编译
      2. 验证无导入错误
    Expected Result: 编译成功，无错误
    Failure Indicators: 出现导入或类型错误
    Evidence: .omo/evidence/task-7-updater-import.txt

  Scenario: updater 函数功能验证
    Tool: Bash
    Preconditions: src/lib/updater.ts 已创建
    Steps:
      1. 读取 updater.ts 内容
      2. 验证 `checkForUpdates` 函数存在
      3. 验证 `downloadAndInstall` 函数存在
      4. 验证使用了 `@tauri-apps/plugin-updater` 导入
    Expected Result: 函数存在且使用正确的 API
    Failure Indicators: 函数缺失或 API 使用错误
    Evidence: .omo/evidence/task-7-updater-functions.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 集成 Tauri updater 前端模块`
  - Files: `src/lib/updater.ts`
  - Pre-commit: `pnpm run build`

- [x] 8. 更新 Tauri 权限配置

  **What to do**:
  - 更新 `src-tauri/capabilities/default.json` 添加 updater 权限
  - 添加 `"updater:default"` 权限
  - 验证权限配置正确

  **Must NOT do**:
  - 不要修改现有权限
  - 不要添加不需要的权限
  - 不要修改其他配置文件

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: JSON 配置更新是标准操作
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 6, 7)
  - **Blocks**: Task 9
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `src-tauri/capabilities/default.json` - 现有权限配置

  **External References**:
  - Tauri 权限系统：https://tauri.app/develop/plugins/

  **WHY Each Reference Matters**:
  - `default.json`: 了解现有权限配置格式

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 权限配置验证
    Tool: Bash
    Preconditions: capabilities/default.json 已更新
    Steps:
      1. 运行 `pnpm tauri info` 检查配置
      2. 读取 default.json 内容
      3. 验证 `"updater:default"` 权限存在
    Expected Result: 权限配置正确
    Failure Indicators: 权限缺失或格式错误
    Evidence: .omo/evidence/task-8-permissions-check.txt

  Scenario: JSON 语法验证
    Tool: Bash
    Preconditions: capabilities/default.json 已更新
    Steps:
      1. 运行 `python -m json.tool src-tauri/capabilities/default.json`
    Expected Result: JSON 语法正确
    Failure Indicators: JSON 语法错误
    Evidence: .omo/evidence/task-8-json-validation.txt
  ```

  **Commit**: YES
  - Message: `feat(packaging): 添加 updater 权限配置`
  - Files: `src-tauri/capabilities/default.json`
  - Pre-commit: `python -m json.tool src-tauri/capabilities/default.json`

- [x] 9. 创建 GitHub Actions release 工作流

  **What to do**:
  - 创建 `.github/workflows/release.yml` 工作流
  - 配置触发条件：推送 `v*` tag
  - 配置矩阵构建：macOS (Intel + Apple Silicon) + Windows
  - 添加 PyInstaller 构建步骤
  - 配置 Tauri 构建和发布
  - 添加签名密钥环境变量
  - 配置 GitHub Release 创建

  **Must NOT do**:
  - 不要修改现有的 CI 工作流
  - 不要添加 Linux 构建（暂不需要）
  - 不要添加代码签名步骤（暂不需要）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 需要理解 GitHub Actions 和跨平台构建
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 10)
  - **Blocks**: F1-F4
  - **Blocked By**: Tasks 2, 4, 5, 6, 7, 8

  **References**:

  **Pattern References**:
  - `.github/workflows/ci.yml` - 现有 CI 工作流，了解格式
  - `sidecar/build.sh` - PyInstaller 构建脚本（Task 5 创建）
  - `src-tauri/tauri.conf.json` - Tauri 配置

  **External References**:
  - Tauri GitHub Actions 文档：https://tauri.app/distribute/github-actions/
  - GitHub Actions 矩阵构建：https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs

  **WHY Each Reference Matters**:
  - `ci.yml`: 了解现有工作流格式和最佳实践
  - `build.sh`: 了解 PyInstaller 构建命令
  - `tauri.conf.json`: 了解 Tauri 构建配置

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 工作流语法验证
    Tool: Bash
    Preconditions: release.yml 已创建
    Steps:
      1. 运行 `act -n` 检查工作流语法（如果 act 已安装）
      2. 或者使用在线 YAML 验证器检查语法
    Expected Result: YAML 语法正确
    Failure Indicators: YAML 语法错误
    Evidence: .omo/evidence/task-9-workflow-syntax.txt

  Scenario: 矩阵构建配置验证
    Tool: Bash
    Preconditions: release.yml 已创建
    Steps:
      1. 读取 release.yml 内容
      2. 验证包含 macOS (Intel + Apple Silicon) 配置
      3. 验证包含 Windows 配置
      4. 验证触发条件为 `v*` tag
    Expected Result: 矩阵配置正确
    Failure Indicators: 平台缺失或触发条件错误
    Evidence: .omo/evidence/task-9-matrix-config.txt

  Scenario: PyInstaller 构建步骤验证
    Tool: Bash
    Preconditions: release.yml 已创建
    Steps:
      1. 读取 release.yml 内容
      2. 验证包含 PyInstaller 构建步骤
      3. 验证构建步骤调用正确的脚本
    Expected Result: PyInstaller 构建步骤存在且正确
    Failure Indicators: 步骤缺失或脚本路径错误
    Evidence: .omo/evidence/task-9-pyinstaller-step.txt
  ```

  **Commit**: YES
  - Message: `ci(packaging): 添加 GitHub Actions release 工作流`
  - Files: `.github/workflows/release.yml`
  - Pre-commit: `act -n`（如果 act 已安装）

- [x] 10. 创建打包文档

  **What to do**:
  - 创建 `docs/BUILDING.md` 打包文档
  - 记录 Windows 打包流程
  - 记录 macOS 打包流程
  - 记录 PyInstaller 构建步骤
  - 记录 GitHub Actions 发布流程
  - 记录密钥管理流程
  - 记录故障排除指南

  **Must NOT do**:
  - 不要修改现有文档
  - 不要添加过于技术性的内容
  - 不要记录未实现的功能

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: 文档编写任务
  - **Skills**: []
    - 无特殊技能需求

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 9)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 5, Task 9

  **References**:

  **Pattern References**:
  - `README.md` - 现有文档，了解格式
  - `.github/workflows/release.yml` - 发布工作流（Task 9 创建）
  - `sidecar/build.sh` - 构建脚本（Task 5 创建）

  **WHY Each Reference Matters**:
  - `README.md`: 了解现有文档风格和格式
  - `release.yml`: 了解发布流程细节
  - `build.sh`: 了解构建步骤

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 文档完整性检查
    Tool: Bash
    Preconditions: docs/BUILDING.md 已创建
    Steps:
      1. 读取 BUILDING.md 内容
      2. 验证包含 Windows 打包章节
      3. 验证包含 macOS 打包章节
      4. 验证包含 PyInstaller 构建章节
      5. 验证包含 GitHub Actions 发布章节
    Expected Result: 文档包含所有必要章节
    Failure Indicators: 章节缺失或内容不完整
    Evidence: .omo/evidence/task-10-doc-completeness.txt

  Scenario: 文档格式验证
    Tool: Bash
    Preconditions: docs/BUILDING.md 已创建
    Steps:
      1. 检查 Markdown 语法
      2. 验证代码块格式正确
      3. 验证链接格式正确
    Expected Result: Markdown 格式正确
    Failure Indicators: 语法错误或格式问题
    Evidence: .omo/evidence/task-10-doc-format.txt
  ```

  **Commit**: YES
  - Message: `docs(packaging): 添加打包文档`
  - Files: `docs/BUILDING.md`
  - Pre-commit: 无

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `npx tsc --noEmit --skipLibCheck` + `pnpm run test`. Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp).
  Output: `Build [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (features working together, not isolation). Test edge cases: empty state, invalid input, rapid actions. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(packaging): 添加 PyInstaller 配置、版本管理和签名密钥` - sidecar/pyinstaller.spec, package.json, src-tauri/Cargo.toml, src-tauri/src/lib.rs
- **Wave 2**: `feat(packaging): 集成 Tauri updater 和构建脚本` - sidecar/build.sh, sidecar/build.bat, src-tauri/tauri.conf.json, src/lib/updater.ts, src-tauri/capabilities/default.json
- **Wave 3**: `ci(packaging): 添加 GitHub Actions release 工作流和文档` - .github/workflows/release.yml, docs/BUILDING.md
- **Final**: 验证和审查，无新提交

---

## Success Criteria

### Verification Commands
```bash
# 检查 PyInstaller 配置
cd sidecar && pyinstaller --version  # Expected: PyInstaller 6.x

# 检查 Tauri 配置
pnpm tauri info  # Expected: 显示正确的平台和依赖信息

# 检查签名密钥
ls -la ~/.tauri/openmathpix.key  # Expected: 文件存在

# 运行构建（验证配置）
pnpm tauri build  # Expected: 成功生成安装包

# 检查产物
ls -la src-tauri/target/release/bundle/  # Expected: 包含 NSIS 和 DMG 文件
```

### Final Checklist
- [ ] Windows NSIS 安装包生成成功
- [ ] macOS DMG 安装包生成成功
- [ ] Python sidecar 被正确打包
- [ ] 自动更新功能配置完成
- [ ] GitHub Actions 工作流创建完成
- [ ] 所有测试通过
- [ ] 文档完整
