# OpenMathpix 技术债务修复计划

## TL;DR

> **快速摘要**：修复 3 个功能缺口（tray 菜单不执行操作）、6 项技术债务（死代码、异常处理、类型安全、接口不匹配），并为关键模块补充测试。
>
> **交付物**：
> - tray.rs 3 个菜单项功能实现 + 前端导航事件监听
> - lib.rs 死代码清理（greet + tauri-plugin-sql）
> - key_manager.py 异常日志增强
> - MathLive 类型声明（消除 4 处 `as any`）
> - stats.ts 删除 + SettingsPage 迁移到 sidecarClient
> - pyinstaller.spec 删除
> - 前端 lib/ 工具函数测试（clipboard、sidecarClient）
> - Rust 关键模块测试（tray、hotkey）
>
> **预估工作量**：Medium
> **并行执行**：YES — 3 个波次
> **关键路径**：T4（MathLive 类型）→ T6+7（as any 消除）→ T10（clipboard 测试）

---

## 背景

### 原始请求
用户要求对项目功能完成度分析报告中发现的已知问题进行修复。

### 调研摘要
**关键发现**（3 个并行 explore agents 扫描全代码库）：

| 类别 | 数量 | 详情 |
|------|------|------|
| 功能缺口 | 3 | tray.rs 菜单项只显示窗口不执行操作 |
| 技术债务 | 6 | 死代码 2 项 + 异常吞没 2 项 + as any 4 处 + stats 不匹配 1 项 + pyinstaller 占位 1 项 |
| 测试缺口 | 多 | 前端 0 测试、Rust 7 模块无测试 |
| 死代码 | 2 | greet()、tauri-plugin-sql 空壳 |

**用户决策**：
- 测试策略：关键模块加测试（非全面覆盖）
- pyinstaller.spec：删除
- tauri-plugin-sql：删除

### Metis 审查
**发现的遗漏**（已纳入计划）：
- `stats.ts` 不仅是接口不匹配，而是**与 sidecarClient.ts 完全重复**——应删除而非修复
- tray.rs 已有事件通信模式（`CaptureFlow.tsx:83` 监听 `"capture-requested"`），截图 tray 项应复用
- 导航应使用通用 `"navigate"` 事件 + 路径参数模式，前端在 `App.tsx` 中全局监听
- MathLive 类型定义应只覆盖实际使用的方法（`value`、`getValue()`），不做完整 API 覆盖
- greet() 删除需同步清理 `generate_handler![]` 注册列表

---

## 工作目标

### 核心目标
修复 OpenMathpix 项目中 3 个功能缺口和 6 项技术债务，并为关键模块补充自动化测试。

### 具体交付物
- 系统托盘菜单项可执行实际操作（截图触发 + 历史/设置页面导航）
- 代码库中无死代码残留（移除 greet、tauri-plugin-sql、pyinstaller.spec、stats.ts）
- 4 处 `as any` 全部消除，有 MathLive 类型声明
- key_manager.py 异常吞没改为日志记录
- Stats 功能使用 sidecarClient 统一客户端
- 前端 lib/ 工具函数有 vitest 测试覆盖
- Rust tray 和 hotkey 模块有内联测试

### 完成标准
- [x] `cargo build` 通过（Rust 编译无错误）
- [x] `cargo test` 通过（含新增测试）
- [x] `npx tsc --noEmit --skipLibCheck` 通过（TypeScript 无错误）
- [x] `pnpm run test` 通过（vitest 测试）
- [x] `pytest` 通过（Python 测试不受影响）
- [x] grep "as any" src/lib/clipboard.ts src/components/FormulaPreview.tsx 返回 0 结果
- [x] grep "except Exception:\s*$" sidecar/sidecar/ocr_engines/key_manager.py 在 460/465 行不再匹配裸 pass

### 必须包含
- tray 菜单截图项触发实际截图流程
- tray 菜单历史/设置项导航到对应页面
- 所有 `as any` 通过类型声明消除
- stats 功能使用唯一客户端（sidecarClient）

### 必须不包含（护栏）
- 不对 tray 菜单添加新的菜单项
- 不修改 `hotkey.rs` 现有逻辑
- 不做 React 组件测试（scope out）
- 不修改 `manager.py` 的熔断器异常处理（设计意图）
- 不做 CI 配置修改
- 不实现 pyinstaller.spec（删除即可）
- MathLive 类型声明只覆盖 value/getValue，不做完整 API

---

## 验证策略

> **零人工介入** — 所有验证均由代理自动执行。

### 测试决策
- **基础设施存在**：vitest（前端）、pytest（Python）、cargo test（Rust）
- **自动化测试**：Tests-after（实现后补充测试）
- **框架**：vitest + pytest + cargo test

### QA 策略
每个任务包含代理可执行的 QA 场景。证据保存到 `.omo/evidence/`。

- **前端/UI**：Playwright 浏览器验证
- **CLI**：Bash 命令执行验证
- **API**：curl 请求验证
- **Rust**：cargo test 输出验证

---

## 执行策略

### 并行执行波次

```
Wave 1（立即启动 — 基础清理，全部并行）：
├── T1: lib.rs 死代码清理 [quick]
├── T2: pyinstaller.spec 删除 [quick]
├── T3: key_manager.py 异常日志 [quick]
└── T4: MathLive 类型声明创建 [quick]

Wave 2（Wave 1 完成后 — 功能修复 + 类型安全，最大并行）：
├── T5: stats.ts 删除 + SettingsPage 迁移 [quick]
├── T6: clipboard.ts as any 消除 [quick]
├── T7: FormulaPreview.tsx as any 消除 [quick]
├── T8: tray.rs 菜单功能实现 [deep]
└── T9: App.tsx 导航事件监听 [quick]

Wave 3（Wave 2 完成后 — 测试补充，最大并行）：
├── T10: clipboard.test.ts 编写 [quick]
├── T11: sidecarClient stats 测试 [quick]
├── T12: tray.rs 内联测试 [deep]
└── T13: hotkey.rs 内联测试 [deep]

Wave FINAL（所有任务完成后 — 4 个并行审查）：
├── F1: 计划合规审计（oracle）
├── F2: 代码质量审查（unspecified-high）
├── F3: 手工 QA 执行（unspecified-high）
└── F4: 范围保真检查（deep）
→ 呈现结果 → 等待用户明确"okay"
```

**关键路径**：T4 → T6/T7 → T10 → F1-F4
**并行加速**：~60% 比串行执行快
**最大并发**：4（Wave 1）、5（Wave 2）、4（Wave 3）

### 依赖矩阵

| 任务 | 依赖 | 阻塞 | 波次 |
|------|------|------|------|
| T1 | - | - | 1 |
| T2 | - | - | 1 |
| T3 | - | - | 1 |
| T4 | - | T6, T7 | 1 |
| T5 | - | - | 2 |
| T6 | T4 | T10 | 2 |
| T7 | T4 | - | 2 |
| T8 | - | T12 | 2 |
| T9 | - | - | 2 |
| T10 | T6 | - | 3 |
| T11 | - | - | 3 |
| T12 | T8 | - | 3 |
| T13 | - | - | 3 |

### 代理调度摘要

| 波次 | 任务数 | 代理分配 |
|------|--------|----------|
| 1 | 4 | T1-T2 → `quick`、T3 → `quick`、T4 → `quick` |
| 2 | 5 | T5-T7 → `quick`、T8 → `deep`、T9 → `quick` |
| 3 | 4 | T10-T11 → `quick`、T12-T13 → `deep` |
| FINAL | 4 | F1 → `oracle`、F2 → `unspecified-high`、F3 → `unspecified-high`、F4 → `deep` |

---

## TODOs

- [x] 1. lib.rs: 删除 greet() 命令和 tauri-plugin-sql 空壳注册

  **做什么**：
  - 删除 `lib.rs:16-18` 的 `greet()` 函数定义
  - 从 `lib.rs:111` 的 `generate_handler![]` 中移除 `greet,`
  - 删除 `lib.rs:105` 的 `tauri_plugin_sql` 插件注册行
  - 检查是否需同步删除 `Cargo.toml` 中的 `tauri-plugin-sql` 依赖

  **必须不做**：
  - 不删除其他任何插件注册或命令
  - 不修改 `Cargo.toml` 中其他依赖

  **推荐代理配置**：
  - **类别**：`quick`
    - 原因：单一文件删除操作，无复杂逻辑
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES
  - **并行组**：Wave 1（与 T2、T3、T4 并行）
  - **阻塞**：无
  - **被阻塞**：无（可立即启动）

  **参考资料**：
  - `src-tauri/src/lib.rs:16-18` — greet() 函数定义（待删除）
  - `src-tauri/src/lib.rs:105` — tauri_plugin_sql 注册（待删除）
  - `src-tauri/src/lib.rs:111` — generate_handler![] 列表（需移除 greet）
  - `src-tauri/Cargo.toml` — 检查 tauri-plugin-sql 依赖项

  **验收标准**：
  - [ ] `cargo build` 在 src-tauri/ 目录下通过
  - [ ] `grep -r "greet" src-tauri/src/` 无匹配结果
  - [ ] `grep -r "tauri_plugin_sql" src-tauri/src/` 无匹配结果

  **QA 场景**：

  ```
  场景：构建验证 — 删除死代码后编译通过
    工具：Bash（cargo）
    步骤：
      1. cd src-tauri && cargo build 2>&1
      2. 检查输出中无 "error" — grep -c "error" 返回 0
    期望结果：编译成功，无错误
    失败指标：编译报错（greet 引用未清理或依赖缺失）
    证据：.omo/evidence/task-1-build.{txt}

  场景：死代码确认 — greet 和 tauri_plugin_sql 完全移除
    工具：Bash（grep）
    步骤：
      1. grep -r "greet" src-tauri/src/ — 应无输出
      2. grep -r "tauri_plugin_sql" src-tauri/src/ — 应无输出
    期望结果：源码中无残留引用
    证据：.omo/evidence/task-1-grep.{txt}
  ```

  **提交**：YES（独立提交）
  - 消息：`refactor(lib): 移除 greet() 模板残留和 tauri-plugin-sql 空壳注册`
  - 文件：`src-tauri/src/lib.rs`
  - 前置检查：`cargo build`

---

- [x] 2. pyinstaller.spec: 删除占位文件

  **做什么**：
  - 删除 `sidecar/pyinstaller.spec`（2 行注释占位文件）

  **必须不做**：
  - 不创建新的 spec 文件
  - 不修改其他构建配置

  **推荐代理配置**：
  - **类别**：`quick`
    - 原因：单文件删除，无逻辑
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES
  - **并行组**：Wave 1（与 T1、T3、T4 并行）
  - **阻塞**：无
  - **被阻塞**：无（可立即启动）

  **参考资料**：
  - `sidecar/pyinstaller.spec` — 待删除的占位文件

  **验收标准**：
  - [ ] `sidecar/pyinstaller.spec` 文件已不存在
  - [ ] `test -f sidecar/pyinstaller.spec` 返回非零退出码

  **QA 场景**：

  ```
  场景：文件删除确认
    工具：Bash
    步骤：
      1. ls sidecar/pyinstaller.spec 2>&1
      2. 确认 exit code 非零（文件不存在）
    期望结果：文件不存在
    证据：.omo/evidence/task-2-delete.txt
  ```

  **提交**：YES（与 T1 合并为同一 commit 或独立）
  - 消息：`chore: 删除 pyinstaller.spec 占位文件`
  - 文件：`sidecar/pyinstaller.spec`

---

- [x] 3. key_manager.py: 异常吞没改为日志记录

  **做什么**：
  - 在 `sidecar/sidecar/ocr_engines/key_manager.py` 第 460 行 `except Exception:` 块内添加 `logger.warning(...)`
  - 在 `sidecar/sidecar/ocr_engines/key_manager.py` 第 465 行 `except Exception:` 块内添加 `logger.warning(...)`
  - 日志消息应包含被删除 key 的 service 和 key_name（但不暴露完整 key 值）

  **必须不做**：
  - 不修改第 437 行已有的 `except Exception:` 块（已有 logger.warning）
  - 不改变控制流（不重新抛出异常，delete_key 是 best-effort 操作）

  **推荐代理配置**：
  - **类别**：`quick`
    - 原因：两行日志添加，无复杂逻辑
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES
  - **并行组**：Wave 1（与 T1、T2、T4 并行）
  - **阻塞**：无
  - **被阻塞**：无（可立即启动）

  **参考资料**：
  - `sidecar/sidecar/ocr_engines/key_manager.py:455-468` — delete_key 方法中的 except 块
  - `sidecar/sidecar/ocr_engines/key_manager.py:437` — 参考已有的 logger.warning 格式（不修改此行）

  **验收标准**：
- [x] `pytest` 全部通过（176 个测试不受影响）
  - [ ] `grep -A1 "except Exception:" sidecar/sidecar/ocr_engines/key_manager.py | grep "pass"` 无匹配（所有 except 块至少有日志）

  **QA 场景**：

  ```
  场景：Python 测试通过验证
    工具：Bash（pytest）
    步骤：
      1. cd sidecar && python -m pytest -q
      2. 检查 exit code 为 0
    期望结果：所有测试通过（176 passed）
    失败指标：测试失败或 exit code 非零
    证据：.omo/evidence/task-3-pytest.txt

  场景：代码审查 — 无裸 pass
    工具：Bash（grep）
    步骤：
      1. grep -n "except Exception:" sidecar/sidecar/ocr_engines/key_manager.py
      2. 确认第 460-461 行和 465-466 行的 except 块不再是裸 pass
    期望结果：每个 except Exception 块内至少有 logger.warning 调用
    证据：.omo/evidence/task-3-grep.txt
  ```

  **提交**：YES
  - 消息：`fix(key_manager): 异常吞没改为日志记录`
  - 文件：`sidecar/sidecar/ocr_engines/key_manager.py`
  - 前置检查：`cd sidecar && python -m pytest -q`

---

- [x] 4. 扩展 MathLive 类型声明文件

  **做什么**：
  - 扩展已有的 `src/types/mathlive.d.ts` 类型声明文件
  - 声明 `MathfieldElement` 接口，包含：
    - `value: string` 属性
    - `getValue(format: string): string` 方法
  - 声明 `math-field` 自定义元素的 JSX 类型（扩展 `JSX.IntrinsicElements`）

  **必须不做**：
  - 不做完整 MathLive API 类型覆盖（只定义实际使用的 value 和 getValue）
  - 不修改 MathLive 库本身

  **推荐代理配置**：
  - **类别**：`quick`
    - 原因：创建类型声明文件，结构简单
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES
  - **并行组**：Wave 1（与 T1、T2、T3 并行）
  - **阻塞**：T6、T7
  - **被阻塞**：无（可立即启动）

  **参考资料**：
  - `src/components/FormulaPreview.tsx:50` — `getValue("mathml")` 调用点
  - `src/types/mathlive.d.ts` — 已有的 JSX 类型声明（待扩展）

  **验收标准**：
  - [ ] `npx tsc --noEmit --skipLibCheck` 通过
  - [ ] 类型声明文件 `src/types/mathlive.d.ts` 已扩展

  **QA 场景**：

  ```
  场景：TypeScript 编译验证
    工具：Bash（tsc）
    步骤：
      1. npx tsc --noEmit --skipLibCheck 2>&1
      2. 检查 exit code 为 0
    期望结果：无类型错误
    证据：.omo/evidence/task-4-tsc.txt
  ```

  **提交**：YES
  - 消息：`types: 扩展 MathLive MathfieldElement 类型声明`
  - 文件：`src/types/mathlive.d.ts`

---

- [x] 5. stats.ts: 删除重复实现 + SettingsPage 迁移到 sidecarClient

  **做什么**：
  - 删除 `src/lib/stats.ts` 文件（包含 `CostStats` 接口和 `fetchStats()` 函数）
  - 修改 `src/pages/SettingsPage.tsx`：
    - 第 4 行：`import { fetchStats, type CostStats } from '../lib/stats'` → `import { getStats, type StatsResponse } from '../lib/sidecarClient'`
    - 第 65 行：`CostStats` → `StatsResponse`
    - 第 77 行：`fetchStats()` → `getStats()`
    - 第 316 行：`stats.total_cost_usd` → `stats.estimated_cost_usd`
    - 第 318 行：`stats.total_cost_usd > 0` → `stats.estimated_cost_usd > 0`
    - 第 324-340 行：移除 `stats.by_backend` 相关的"按后端分布"UI 区块（`StatsResponse` 无此字段）
    - 第 371 行 + 374-386 行：`stats.total_cost_usd` → `stats.estimated_cost_usd`

  **必须不做**：
  - 不修改 `sidecarClient.ts` 或 API
  - 不创建新的 stats 实现

  **推荐代理配置**：
  - **类别**：`quick` — 原因：文件删除+变量重命名，纯机械操作

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 2（与 T6-T9 并行）| **阻塞**：无 | **被阻塞**：无

  **参考资料**：
  - `src/lib/stats.ts` — 待删除 | `src/lib/sidecarClient.ts:33-40,134-136` — StatsResponse + getStats()
  - `src/pages/SettingsPage.tsx:4,65,77,310-340,371-388` — 所有需修改位置

  **验收标准**：
  - [ ] `src/lib/stats.ts` 已删除
  - [ ] `npx tsc --noEmit --skipLibCheck` 通过
  - [ ] `grep -r "CostStats\|fetchStats" src/` 无匹配

  **QA 场景**：

  ```
  场景：编译+死代码确认
    工具：Bash
    步骤：
      1. test ! -f src/lib/stats.ts && echo "DELETED"
      2. npx tsc --noEmit --skipLibCheck 2>&1; echo "EXIT:$?"
      3. grep -r "fetchStats\|CostStats" src/ || echo "NO_MATCHES"
    期望结果：文件已删除，编译通过，无残留引用
    证据：.omo/evidence/task-5-verify.txt
  ```

  **提交**：YES
  - 消息：`refactor: 删除重复 stats.ts，统一使用 sidecarClient`
  - 文件：`src/lib/stats.ts`（删）、`src/pages/SettingsPage.tsx`
  - 前置检查：`npx tsc --noEmit --skipLibCheck`

---

- [x] 6. clipboard.ts: 消除 2 处 `as any`

  **做什么**：
  - 第 16 行：`as any` → `as unknown as MathfieldElement`
  - 第 32 行：`as any` → `as unknown as MathfieldElement`
  - 添加 `import type { MathfieldElement } from '../types/mathlive'`

  **必须不做**：不添加 @ts-ignore | **被阻塞**：T4

  **推荐代理配置**：
  - **类别**：`quick` — 2 行类型断言替换

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 2 | **阻塞**：T10 | **被阻塞**：T4

  **参考资料**：
  - `src/lib/clipboard.ts:16,32` — as any 位置
  - `src/types/mathlive.d.ts` — T4 扩展的类型声明

  **验收标准**：
  - [ ] `grep -c "as any" src/lib/clipboard.ts` 返回 0
  - [ ] `npx tsc --noEmit --skipLibCheck` 通过

  **QA 场景**：

  ```
  场景：as any 消除确认
    工具：Bash
    步骤：
      1. grep "as any" src/lib/clipboard.ts || echo "CLEAN"
      2. npx tsc --noEmit --skipLibCheck 2>&1; echo "EXIT:$?"
    期望结果：无 as any，编译通过
    证据：.omo/evidence/task-6-verify.txt
  ```

  **提交**：YES
  - 消息：`types(clipboard): 消除 as any，使用 MathfieldElement 类型`
  - 文件：`src/lib/clipboard.ts`
  - 前置检查：`npx tsc --noEmit --skipLibCheck`

---

- [x] 7. FormulaPreview.tsx: 消除 2 处 `as any`

  **做什么**：
  - 第 15 行：`useRef<HTMLElement & { value: string }>` → `useRef<MathfieldElement>`
  - 第 50 行：`(mathFieldRef.current as any).getValue(...)` → `mathFieldRef.current!.getValue(...)`
  - 第 60 行：`ref={mathFieldRef as any}` → `ref={mathFieldRef}`（类型修正后自动生效）

  **必须不做**：不添加 @ts-ignore | **被阻塞**：T4

  **推荐代理配置**：
  - **类别**：`quick` — 3 处类型修正

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 2 | **阻塞**：无 | **被阻塞**：T4

  **参考资料**：
  - `src/components/FormulaPreview.tsx:15,50,60` — 修改位置
  - `src/types/mathlive.d.ts` — T4 扩展的类型

  **验收标准**：
  - [ ] `grep -c "as any" src/components/FormulaPreview.tsx` 返回 0
  - [ ] `npx tsc --noEmit --skipLibCheck` 通过

  **QA 场景**：

  ```
  场景：as any 消除确认
    工具：Bash
    步骤：
      1. grep "as any" src/components/FormulaPreview.tsx || echo "CLEAN"
      2. npx tsc --noEmit --skipLibCheck 2>&1; echo "EXIT:$?"
    期望结果：无 as any，编译通过
    证据：.omo/evidence/task-7-verify.txt
  ```

  **提交**：YES
  - 消息：`types(FormulaPreview): 消除 as any，使用 MathfieldElement ref 类型`
  - 文件：`src/components/FormulaPreview.tsx`
  - 前置检查：`npx tsc --noEmit --skipLibCheck`

---

- [x] 8. tray.rs: 实现 3 个菜单项功能

  **做什么**：
  - **截图**：`show()+focus()` 后 emit `"capture-requested"` 事件（复用 hotkey.rs 的 payload 格式）
  - **历史**：`show()+focus()` 后 emit `"navigate"` 事件，payload=`"/history"`
  - **设置**：`show()+focus()` 后 emit `"navigate"` 事件，payload=`"/settings"`
  - 移除第 35、45、52 行 TODO 注释

  **必须不做**：不修改 hotkey.rs | 不添加新 Tauri command | 不改变 about/quit

  **推荐代理配置**：
  - **类别**：`deep` — 跨层通信（Tauri events + 截图调用）
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 2 | **阻塞**：T12 | **被阻塞**：无

  **参考资料**：
  - `src-tauri/src/tray.rs:29-62` — 菜单 match 块
  - `src-tauri/src/hotkey.rs` — capture-requested emit 模式
  - `src-tauri/src/screenshot.rs` — 截图 API
  - `src/components/CaptureFlow.tsx:83` — 前端事件监听

  **验收标准**：
  - [ ] `cargo build` 通过
  - [ ] `grep "TODO" src-tauri/src/tray.rs` 无匹配
  - [ ] 菜单 match 块中 screenshot/history/settings 分支各含 `emit` 调用

  **QA 场景**：

  ```
  场景：编译+TODO清除+事件代码确认
    工具：Bash
    步骤：
      1. cd src-tauri && cargo build 2>&1; echo "BUILD:$?"
      2. grep -c "TODO" src-tauri/src/tray.rs || echo "NO_TODOS"
      3. grep -c "emit" src-tauri/src/tray.rs
    期望结果：编译成功，TODO清零，emit 代码存在
    证据：.omo/evidence/task-8-verify.txt
  ```

  **提交**：YES
  - 消息：`feat(tray): 实现系统托盘菜单导航和截图功能`
  - 文件：`src-tauri/src/tray.rs`
  - 前置检查：`cd src-tauri && cargo build`

---

- [x] 9. App.tsx: 添加全局导航事件监听

  **做什么**：
  - 在 `App.tsx` 中创建 `NavigationListener` 子组件
  - 使用 `listen("navigate", ...)` 监听 Rust 侧 emitted 的导航事件
  - 使用 `useNavigate()` 跳转到 payload 指定的路径

  **必须不做**：不使用 window.location | 不修改路由配置

  **推荐代理配置**：
  - **类别**：`quick` — ~15 行事件监听代码

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 2 | **阻塞**：无 | **被阻塞**：无

  **参考资料**：
  - `src/App.tsx:24-38` — BrowserRouter + Routes 结构
  - `src/components/CaptureFlow.tsx:83` — 现有 `listen("capture-requested")` 模式
  - Tauri API：`import { listen } from '@tauri-apps/api/event'`

  **验收标准**：
  - [ ] `npx tsc --noEmit --skipLibCheck` 通过
  - [ ] App.tsx 中含 `listen("navigate")` 和 `useNavigate()`

  **QA 场景**：

  ```
  场景：编译+代码确认
    工具：Bash
    步骤：
      1. npx tsc --noEmit --skipLibCheck 2>&1; echo "TSC:$?"
      2. grep -c "navigate" src/App.tsx
    期望结果：编译通过，导航监听代码存在
    证据：.omo/evidence/task-9-verify.txt
  ```

  **提交**：YES
  - 消息：`feat(App): 添加全局导航事件监听，支持托盘菜单页面跳转`
  - 文件：`src/App.tsx`
  - 前置检查：`npx tsc --noEmit --skipLibCheck`

---

- [x] 10. clipboard.test.ts: 编写 clipboard 工具函数测试

  **做什么**：
  - 在 `src/__tests__/` 或 `src/lib/` 下创建 `clipboard.test.ts`
  - 测试覆盖：
    - `getFormatLabel()` 各格式返回正确中文名称
    - `copyToClipboard()` 函数存在且格式参数类型正确（单元测试级别，不实际调用系统剪贴板）
    - 类型导出 `CopyFormat` 值正确

  **必须不做**：
  - 不做实际剪贴板写入的集成测试（需 Tauri 运行时）
  - 不测试 MathLive 渲染

  **推荐代理配置**：
  - **类别**：`quick` — 简单单元测试
  - **技能**：`vitest` 使用 vitest 框架

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 3（与 T11-T13 并行）| **阻塞**：无 | **被阻塞**：T6

  **参考资料**：
  - `src/lib/clipboard.ts` — 被测模块
  - `vitest.config.ts` — vitest 配置（jsdom + globals）

  **验收标准**：
  - [ ] `pnpm run test` 通过（含新增测试）
  - [ ] clipboard 测试覆盖 getFormatLabel 至少 3 个用例

  **QA 场景**：

  ```
  场景：vitest 测试通过
    工具：Bash
    步骤：
      1. pnpm run test -- --reporter=verbose 2>&1
      2. 检查 exit code 为 0
      3. 确认 clipboard 相关测试 PASS
    期望结果：所有 vitest 测试通过
    证据：.omo/evidence/task-10-vitest.txt
  ```

  **提交**：YES
  - 消息：`test(clipboard): 添加 getFormatLabel 和 CopyFormat 类型测试`
  - 文件：`src/__tests__/clipboard.test.ts`
  - 前置检查：`pnpm run test`

---

- [x] 11. sidecarClient stats 测试

  **做什么**：
  - 在 `src/__tests__/` 下创建 `sidecarClient.test.ts`
  - 测试覆盖：
    - `StatsResponse` 接口字段验证（total_calls、total_tokens、estimated_cost_usd、calls_today、daily_limit、remaining_today）
    - `getStats()` 函数签名和返回类型正确
    - `SidecarError` 类构造和属性
    - `OcrRequest`/`OcrResponse` 接口结构

  **必须不做**：
  - 不做实际 HTTP 调用的集成测试
  - 不 mock fetch（纯类型/单元测试）

  **推荐代理配置**：
  - **类别**：`quick` — 类型+接口测试
  - **技能**：`vitest`

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 3 | **阻塞**：无 | **被阻塞**：无

  **参考资料**：
  - `src/lib/sidecarClient.ts:33-40` — StatsResponse
  - `src/lib/sidecarClient.ts:54-63` — SidecarError
  - `src/lib/sidecarClient.ts:14-18` — OcrRequest

  **验收标准**：
  - [ ] `pnpm run test` 通过
  - [ ] 至少 3 个测试用例覆盖上述接口

  **QA 场景**：

  ```
  场景：vitest 测试通过
    工具：Bash
    步骤：
      1. pnpm run test 2>&1; echo "EXIT:$?"
    期望结果：测试全部通过
    证据：.omo/evidence/task-11-vitest.txt
  ```

  **提交**：YES
  - 消息：`test(sidecarClient): 添加 StatsResponse/SidecarError 类型测试`
  - 文件：`src/__tests__/sidecarClient.test.ts`
  - 前置检查：`pnpm run test`

---

- [x] 12. tray.rs 内联测试

  **做什么**：
  - 在 `src-tauri/src/tray.rs` 添加 `#[cfg(test)] mod tests { ... }` 内联测试模块
  - 测试覆盖：
    - `create_tray()` 创建成功（测试 env 中可能有限，聚焦编译验证）
    - 菜单项 ID 正确（screenshot/history/settings/about/quit 均在菜单中）
    - 事件 emit 逻辑可测试（至少验证编译通过 + 函数签名正确）

  **必须不做**：
  - 不做系统级托盘集成测试（需要实际桌面环境）
  - 不 mock Tauri API

  **推荐代理配置**：
  - **类别**：`deep` — Rust 内联测试
  - **技能**：无需特殊技能

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 3 | **阻塞**：无 | **被阻塞**：T8

  **参考资料**：
  - `src-tauri/src/tray.rs` — 被测模块
  - `src-tauri/src/db.rs` / `history.rs` — 已有内联测试模式（`setup_db` helper）

  **验收标准**：
  - [ ] `cd src-tauri && cargo test` 通过（含 tray 测试）
  - [ ] tray 测试至少覆盖菜单创建基础

  **QA 场景**：

  ```
  场景：cargo test 通过
    工具：Bash
    步骤：
      1. cd src-tauri && cargo test 2>&1
      2. 检查 exit code 为 0
      3. 确认 tray 测试在输出中
    期望结果：所有 Rust 测试通过
    证据：.omo/evidence/task-12-cargo-test.txt
  ```

  **提交**：YES
  - 消息：`test(tray): 添加托盘模块内联单元测试`
  - 文件：`src-tauri/src/tray.rs`
  - 前置检查：`cd src-tauri && cargo test`

---

- [x] 13. hotkey.rs 内联测试

  **做什么**：
  - 在 `src-tauri/src/hotkey.rs` 添加 `#[cfg(test)] mod tests { ... }` 内联测试模块
  - 测试覆盖：
    - 快捷键注册函数存在且可编译
    - 平台相关的快捷键组合逻辑（Ctrl/Shift/C vs Cmd/Shift/C）
    - 事件名称正确（`"capture-requested"`）

  **必须不做**：
  - 不做全局快捷键实际的系统注册测试（需桌面环境）
  - 不修改现有快捷键逻辑

  **推荐代理配置**：
  - **类别**：`deep` — Rust 内联测试

  **并行化**：
  - **可并行**：YES | **并行组**：Wave 3 | **阻塞**：无 | **被阻塞**：无

  **参考资料**：
  - `src-tauri/src/hotkey.rs` — 被测模块
  - `src-tauri/src/db.rs` — 已有内联测试模式

  **验收标准**：
  - [ ] `cd src-tauri && cargo test` 通过（含 hotkey 测试）
  - [ ] hotkey 测试至少覆盖事件 emit 逻辑

  **QA 场景**：

  ```
  场景：cargo test 通过
    工具：Bash
    步骤：
      1. cd src-tauri && cargo test 2>&1; echo "EXIT:$?"
    期望结果：所有 Rust 测试通过
    证据：.omo/evidence/task-13-cargo-test.txt
  ```

  **提交**：YES
  - 消息：`test(hotkey): 添加快捷键模块内联单元测试`
  - 文件：`src-tauri/src/hotkey.rs`
  - 前置检查：`cd src-tauri && cargo test`

---

## Final Verification Wave（所有实现任务完成后 — 强制执行）

> 4 个审查 agent 并行执行。全部 APPROVE 后才能呈现结果给用户。用户明确"okay"后才完成。

- [x] F1. **计划合规审计** — `oracle`
  逐条检查计划"必须包含"每一项：验证 tray 菜单 emit 代码存在（读 tray.rs）、as any 消除（grep）、stats.ts 删除（test -f）、key_manager except 修复。逐条检查"必须不包含"：确认无新菜单项、hotkey.rs 未修改、无新 Tauri command、无 CI 修改。
  输出：`Must Have [N/N] | Must NOT Have [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **代码质量审查** — `unspecified-high`
  运行 `cargo build` + `npx tsc --noEmit --skipLibCheck` + `pnpm run test` + `pytest`。审查所有变更文件是否有：`as any`/`@ts-ignore`（误消除不完整）、`console.error` 替代更好的错误处理、重复代码、AI slop 模式（过度注释、过度抽象）。
  输出：`Build [PASS/FAIL] | TSC [PASS/FAIL] | Vitest [N/N] | Pytest [N/N] | Cargo Test [N/N] | VERDICT`

- [x] F3. **手工 QA 执行** — `unspecified-high`
  执行每个任务的 QA 场景步骤，收集证据到 `.omo/evidence/final-qa/`。重点验证跨任务集成：tray emit 事件名与前端 listen 一致；stats 迁移后 SettingsPage 字段名全部正确；MathLive 类型后 clipboard + FormulaPreview 无运行时错误。
  输出：`Scenarios [N/N pass] | Cross-Task [N/N] | VERDICT`

- [x] F4. **范围保真检查** — `deep`
  对照"必须不包含"护栏逐条检查 git diff：无 manager.py 修改、无 CI 修改、无 React 组件测试、无新功能添加。识别跨任务污染（某任务改了其他任务的文件）和未记录的变更。检测残留：`as any` 是否真正清零、`except Exception: pass` 是否真正修复。
  输出：`Tasks [N/N compliant] | Scope Creep [CLEAN/N items] | VERDICT`

---

## 提交策略

| 任务 | 提交消息 | 文件 |
|------|----------|------|
| T1 | `refactor(lib): 移除 greet() 模板残留和 tauri-plugin-sql 空壳注册` | `src-tauri/src/lib.rs` |
| T2 | `chore: 删除 pyinstaller.spec 占位文件` | `sidecar/pyinstaller.spec` |
| T3 | `fix(key_manager): 异常吞没改为日志记录` | `sidecar/sidecar/ocr_engines/key_manager.py` |
| T4 | `types: 扩展 MathLive MathfieldElement 类型声明` | `src/types/mathlive.d.ts` |
| T5 | `refactor: 删除重复 stats.ts，统一使用 sidecarClient` | `src/lib/stats.ts`、`src/pages/SettingsPage.tsx` |
| T6 | `types(clipboard): 消除 as any，使用 MathfieldElement 类型` | `src/lib/clipboard.ts` |
| T7 | `types(FormulaPreview): 消除 as any，使用 MathfieldElement ref 类型` | `src/components/FormulaPreview.tsx` |
| T8 | `feat(tray): 实现系统托盘菜单导航和截图功能` | `src-tauri/src/tray.rs` |
| T9 | `feat(App): 添加全局导航事件监听，支持托盘菜单页面跳转` | `src/App.tsx` |
| T10 | `test(clipboard): 添加 getFormatLabel 和 CopyFormat 类型测试` | `src/__tests__/clipboard.test.ts` |
| T11 | `test(sidecarClient): 添加 StatsResponse/SidecarError 类型测试` | `src/__tests__/sidecarClient.test.ts` |
| T12 | `test(tray): 添加托盘模块内联单元测试` | `src-tauri/src/tray.rs` |
| T13 | `test(hotkey): 添加快捷键模块内联单元测试` | `src-tauri/src/hotkey.rs` |

---

## 成功标准

### 验证命令
```bash
# Rust 编译 + 测试
cd src-tauri && cargo build && cargo test

# TypeScript 类型检查
npx tsc --noEmit --skipLibCheck

# 前端测试
pnpm run test

# Python 测试
cd sidecar && python -m pytest -q

# as any 清零验证
grep -r "as any" src/lib/clipboard.ts src/components/FormulaPreview.tsx || echo "ALL CLEAN"

# stats.ts 删除确认
test ! -f src/lib/stats.ts && echo "STATS_DELETED"

# Tauri-plugin-sql 清除确认
grep -r "tauri_plugin_sql" src-tauri/src/ || echo "SQL_PLUGIN_CLEAN"

# greet 清除确认
grep -r "fn greet" src-tauri/src/ || echo "GREET_CLEAN"
```

### 最终检查清单
- [x] 所有"必须包含"存在
- [x] 所有"必须不包含"不存在
- [x] `cargo build` + `cargo test` 通过
- [x] `npx tsc --noEmit --skipLibCheck` 通过
- [x] `pnpm run test` 通过（含新增前端测试）
- [x] `pytest` 全部通过（176 个测试不受影响）
- [x] 4 处 `as any` 全部消除
- [x] tray.rs 3 个 TODO 全部移除
- [x] stats 功能使用唯一边车客户端

