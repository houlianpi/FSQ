# FSQ 开源战略分析与长期规划

> **目标：将 FSQ 打造为世界顶级的 AI Automation 开源工具，拥有业界领先的 Harness 技术，通过 GitHub 社区协作实现快速增长。**

---

## 一、现状诊断

### 1.1 核心资产盘点

| 维度 | 现状 | 评价 |
|---|---|---|
| **架构质量** | 15 个模块、清晰的分层 DAG、Protocol-driven 接口设计、Spec-Driven Development | ★★★★★ 优秀 |
| **Harness 抽象** | `HarnessInterface` + `DriverInterface` 双层协议，4 平台实现 (Android/Web/Windows/macOS) | ★★★★★ 核心竞争力 |
| **测试覆盖** | 36 个测试文件、600KB+ 测试代码 | ★★★★☆ 扎实 |
| **内部文档** | 15 个 SPEC.md + 39 个设计文档 + README | ★★★★☆ 内部充分 |
| **社区基建** | LICENSE / CONTRIBUTING / CODE_OF_CONDUCT / SECURITY 齐全 | ★★★☆☆ 基本合格 |
| **GitHub 社区** | 9 stars, 0 forks, 0 issues, 0 watchers | ★☆☆☆☆ 刚起步 |
| **CI/CD** | 无 GitHub Actions workflows | ★☆☆☆☆ 缺失 |
| **Issue/PR Templates** | 无 | ★☆☆☆☆ 缺失 |
| **项目定位描述** | "goal-driven automated testing agent" — 过于狭窄 | ★★☆☆☆ 需要重塑 |

### 1.2 核心竞争力分析

FSQ 的真正差异化在于以下三点：

**1. 跨平台统一 Harness 抽象层**

这是市面上少见的技术。Appium 做跨平台但 API 重且不同平台差异大；Playwright 只做 Web；pywinauto 只做 Windows。FSQ 用统一的 `HarnessInterface` Protocol 抽象了 4 个平台，且每个平台有独立的 Driver 实现。这是做 "世界顶级 AI Automation 工具" 的技术基础。

**2. Dual Loop 架构**

严格回放 (StepRunner) + LLM 探索 (Agent) 的双循环设计，让同一套 Harness 既能做确定性回归测试，又能做 AI 驱动的智能探索。这种 "精确性 + 智能性" 的结合在业界独一无二。

**3. FSQ YAML DSL + Capability Registry**

声明式的测试用例描述 (可录制、可回放、可编辑) 加上装饰器驱动的能力发现、验证和元数据管理系统，为扩展性提供了坚实基础。

### 1.3 竞品对比

| 特性 | FSQ | Playwright | Appium | Browser Use | UFO (MS) |
|---|---|---|---|---|---|
| 跨平台统一 API | ✅ 4 平台 | ❌ Web only | ⚠️ API 不统一 | ❌ Web only | ⚠️ Windows only |
| AI Agent 驱动 | ✅ LLM + 规划 | ❌ | ❌ | ✅ | ✅ |
| 确定性回放 | ✅ Strict Mode | ✅ | ✅ | ❌ | ❌ |
| 可扩展 Harness | ✅ Protocol-based | ❌ 固定 | ⚠️ 插件系统 | ❌ | ❌ |
| 自动录制 | ✅ Dynamic Recording | ✅ Codegen | ⚠️ Inspector | ❌ | ❌ |
| 开源社区规模 | 🔴 起步 | 🟢 67k stars | 🟢 19k stars | 🟡 51k stars | 🟡 12k stars |

**结论**：FSQ 在技术完整度上有明显优势，但在社区建设和开发者体验方面需要大幅提升。

### 1.4 关键短板

| 短板 | 影响 | 严重度 |
|---|---|---|
| 品牌定位过窄 — 描述为 "testing agent" | 限制了潜在用户群，Harness 能力远超测试场景 | 🔴 高 |
| 社区参与基础设施缺失 — 无 CI、无模板 | 外部开发者无法有效贡献 | 🔴 高 |
| 可扩展性不够开放 | 添加新平台/Driver 的路径对外部贡献者不透明 | 🔴 高 |
| 缺少 "即开即用" 体验 | 新用户需要配置大量环境变量，上手门槛高 | 🟡 中 |
| LLM Provider 局限 — 只支持 Copilot + Azure OpenAI | 排除了大量潜在用户 | 🟡 中 |
| 缺少 Plugin/Extension 机制 | 社区无法贡献自定义 Harness/Driver/Tool | 🟡 中 |

---

## 二、战略定位重塑

### 2.1 品牌含义

**FSQ = Fully Self Quality**

系统自己完整地证明自己的质量，不依赖外部人工判断。

| 全称拆解 | 含义 | 技术体现 |
|---|---|---|
| **Fully** | 完整无遗漏 | 每一步都有完整 evidence — 截图、UI snapshot、action trace，全链路记录 |
| **Self** | 自主、自驱动 | Agent 自主执行 + Verifier 自主判定，不依赖人工介入 |
| **Quality** | 质量是最终产出 | Evidence-based verification 证明质量，Strict replay 守护质量 |

**核心理念：** 传统 QA 靠人来保证质量；AI Agent 靠自己说"我做完了"；**FSQ 靠 evidence 自证质量** — Fully Self Quality 意味着质量保证是系统内建的、自动的、有据可查的。

### 2.2 从 "Testing Agent" 到 "Agent Harness"

**当前定位 (过窄)：**
> fsq-agent is a goal-driven automated testing agent for FSQ YAML-guided tasks.

**确定的新定位：**
> **FSQ is an evidence-first agent harness for replayable, verifiable AI UI automation.**

14 词，一句话定义品类 + 差异化 + 领域。三个核心属性自然嵌入句子结构：

| 属性 | 在句中的位置 | 含义 | 对应 FSQ 核心能力 |
|---|---|---|---|
| **Evidence-first** | 修饰 agent harness — 设计哲学 | 每一步都有截图、UI snapshot、action trace，evidence 是第一优先级 | `observation` 模块、StepRunner 自动 evidence capture |
| **Replayable** | 修饰 AI UI automation | 动态执行成功后能生成 strict YAML，用于确定性回归 | Dual Loop 架构、dynamic recording → strict replay |
| **Verifiable** | 修饰 AI UI automation | 最终结果通过 verifier / assertion / evidence 判断，而非 agent 自我宣称 | Verifier、AI assertion、evidence-based goal verification |

> **为什么这个定位有效：** 竞品 (Browser Use, UFO, LaVague 等) 的 agent 跑完说 "我成功了"。FSQ 的回答是 "**这是证据，你来验证**"。"Evidence-first" 用设计哲学而非功能清单来定义 FSQ，类似 "API-first"、"mobile-first" — 技术社区立刻理解这意味着什么。

### 2.2 核心叙事的三大支柱

```
┌──────────────────────────────────────────────────────────────┐
│  FSQ: Agent Harness for AI UI Automation                     │
│  Evidence-backed · Replayable · Verifiable                   │
├───────────────────┬─────────────────────┬────────────────────┤
│   Harness SDK     │   Agent Runtime     │  FSQ DSL & Tools   │
│                   │                     │                    │
│   统一跨平台      │   LLM 驱动的        │   YAML 声明式      │
│   自动化抽象层    │   智能执行引擎      │   用例 + Playground │
│                   │                     │                    │
│   社区可扩展      │   多 Provider       │   录制 / 回放      │
│   新平台/驱动     │   支持              │   / 编辑           │
└───────────────────┴─────────────────────┴────────────────────┘
```

### 2.3 目标用户群扩展

| 用户类型 | 使用场景 | 当前覆盖 |
|---|---|---|
| QA 工程师 | 自动化测试、回归测试 | ✅ 已覆盖 |
| 前端开发者 | E2E 测试、UI 验证 | ⚠️ 部分覆盖 |
| AI 研究者 | Agent 基准测试、Benchmark | ❌ 需要开放 |
| RPA 开发者 | 流程自动化、桌面自动化 | ❌ 需要拓展 |
| DevOps 工程师 | CI/CD 中的 UI 验证 | ❌ 需要集成 |
| 开源贡献者 | 新平台 Harness 开发 | ❌ 需要 Plugin 机制 |

---

## 三、可执行方案 (分阶段)

### Phase 1: 社区基础设施建设 (1-2 周)

**目标：让外部开发者能够参与贡献**

#### 1.1 GitHub Actions CI/CD Pipeline

需要创建的 workflows:

| 文件 | 功能 |
|---|---|
| `.github/workflows/ci.yml` | PR / push 自动测试 |
| `.github/workflows/lint.yml` | Ruff lint + type check |
| `.github/workflows/release.yml` | PyPI 发布自动化 |

CI 应包含：
- Ruff lint 检查
- pytest 单元测试 (不含平台集成测试，因为需要设备)
- 构建验证 (`uv build`)
- 前端构建验证 (`npm ci && npm run build`)
- 多 Python 版本矩阵 (3.11, 3.12, 3.13)

#### 1.2 Issue & PR Templates

```
.github/ISSUE_TEMPLATE/
├── bug_report.yml           # Bug 报告模板
├── feature_request.yml      # 功能建议模板
├── new_platform.yml         # 新平台/Driver 提案
└── config.yml               # 模板选择器配置

.github/PULL_REQUEST_TEMPLATE.md  # PR 模板
```

#### 1.3 增强 CONTRIBUTING.md

当前太简单，需要补充：
- 架构概览图 (让贡献者快速理解模块关系)
- "Good First Issues" 路径指引
- 添加新平台 Harness/Driver 的教程
- 添加新 Capability 的教程
- 代码风格和 SPEC 规范的快速指南
- 开发环境 Troubleshooting

#### 1.4 README 重写

**竞品 README 研究结论 (UFO³ / Midscene.js / Browser Use)：**

最有效的开源 README 在 30 秒内回答三个问题：
1. 它是什么？→ 一句 tagline
2. 它能做什么？→ GIF/视频直接看到
3. 我怎么试？→ 3 步 copy-paste 跑通

| 维度 | UFO³ | Midscene.js | Browser Use | FSQ 应该学什么 |
|---|---|---|---|---|
| 首屏信息密度 | 过高，术语先行 | 恰好，一句话+badges | 极简，tagline+GIF | 学 Browser Use 极简首屏 |
| "它能做什么" | 滚很久才看到 | "Why Midscene" 3 bullets | "What can it do?"+动图 | 学 Browser Use 问题式标题+动图 |
| Quick Start | 步骤多，配多个 YAML | 多入口(扩展/SDK/平台) | 3 步 copy-paste 即跑 | 学 Browser Use 的 3 步 |
| 视觉证明 | mermaid 图 | showcases 链接 | GIF/视频嵌 README | 必须有执行过程 GIF |
| 差异化叙事 | 多设备编排 | "vision-first, no selector" | "AI controls browser" | evidence-first 是 FSQ 独有空间 |

**三家共同弱点（FSQ 差异化空间）：**
- 都没强调"结果可信度" — agent 说成功了就真成功了吗？
- 都没有 evidence trace / replayability 概念
- 都没有"AI 探索 → 确定性回归"的完整闭环

**确定的 README 结构：**

```markdown
# FSQ

> An evidence-first agent harness for replayable, verifiable AI UI automation.

[badges: CI | PyPI | Python 3.11+ | License MIT | Docs]

## See it in action
[30 秒 GIF: goal → agent 执行 → evidence 采集 → verification → strict YAML 生成]

## Why FSQ?
- **Other AI agents say "I'm done." FSQ shows you the proof.**
  Every step produces screenshots, UI snapshots, and action traces.
- **Today's AI exploration becomes tomorrow's regression test.**
  Successful runs auto-generate strict YAML — deterministic, no LLM needed.
- **One harness, four platforms.**
  Android · Web · Windows · macOS — same API, same evidence model.

## What can FSQ do?
[Dynamic vs Strict 能力矩阵表]

## Quick Start (≤5 步)
pip install fsq-agent[web]
fsq-agent init --platform web --provider openai
fsq-agent run --platform web --goal "..."
> Output: screenshots + UI snapshots + report + replayable YAML

## How It Works
[Dual Loop 简洁架构图: Dynamic(AI) ↔ Strict(Replay), 共享 Harness + Evidence]

## Platforms
[4 平台 + backend 一行表格]

## Compared to...
[FSQ vs Browser Use vs Midscene vs Playwright 对比表，突出 evidence/replay/verify]

## Documentation
[链接到 docs/]

## Contributing
[3 步上手 + Good First Issues 链接，比竞品更强调社区参与]

## License
```

**关键设计原则：**
1. 首屏 = tagline + GIF + "Why FSQ" 3 bullets — 30 秒内打动人
2. Quick Start ≤ 5 步能看到结果 — 当前环境配置必须简化
3. 竞品对比表放首页 — evidence/replay/verify 差异在对比中最突出
4. Dual Loop 是故事线 — "AI 探索 → evidence → replay YAML → 回归" 这个闭环无竞品能讲
5. 视觉证明 > 文字描述 — 一个 GIF 胜过十段说明

#### 1.5 Changelog & Release 流程

- 创建 `CHANGELOG.md`
- 设置 Semantic Versioning 规范
- 配置 GitHub Releases 自动化

---

### Phase 2: Harness SDK 可扩展化 (2-4 周)

**目标：让社区能贡献新平台 Harness — 这是 FSQ 最核心的技术壁垒**

#### 2.1 Harness Plugin 架构

```python
# 设想的 Plugin 注册机制:
# fsq_agent/core/harness/_plugin.py

class HarnessPlugin(Protocol):
    """Third-party harness plugin contract."""
    platform_id: str
    backend_id: str

    def create_driver(self, config: dict) -> DriverObservationInterface: ...
    def create_harness(self, driver, ...) -> HarnessInterface: ...
    def get_capabilities(self) -> list[CapabilityDefinition]: ...
    def get_skill_markdown(self) -> str: ...
```

通过 Python entry_points 注册第三方 Harness:
```toml
# 第三方 package 的 pyproject.toml:
[project.entry-points."fsq_agent.harness"]
linux = "fsq_linux:LinuxHarnessPlugin"
ios = "fsq_ios:IOSHarnessPlugin"
```

#### 2.2 优先级最高的新平台

| 平台 | 驱动后端 | 社区需求 | 难度 | 建议 |
|---|---|---|---|---|
| **iOS** | XCUITest / Appium | 非常高 | 中 | 社区合作开发 |
| **Linux Desktop** | AT-SPI2 / ldtpd | 中 | 中 | Good First Platform |
| **Electron Apps** | Playwright + CDP | 高 | 低 | 快速赢面 |
| **Flutter** | flutter_driver / integration_test | 中 | 中 | 中期目标 |
| **React Native** | Detox / Appium | 中 | 中 | 中期目标 |

#### 2.3 Harness 开发者文档

创建 `docs/harness-development-guide.md`，内容包含：
- HarnessInterface Protocol 完整详解
- DriverInterface Protocol 完整详解
- Capability 装饰器使用指南
- 从零添加一个新平台的 Step-by-Step 教程
- 测试 Harness 的最佳实践
- 参考实现走读 (以 Web Harness 为例)

---

### Phase 3: 多 LLM Provider 支持 (2-3 周)

**目标：降低使用门槛，不限制用户的 LLM 选择**

```
当前: GitHub Copilot, Azure OpenAI
目标: + OpenAI Direct + Anthropic Claude + 本地 LLM (Ollama/vLLM) + OpenRouter
```

#### 3.1 扩展计划

| Provider | 优先级 | 说明 |
|---|---|---|
| OpenAI Direct API | P0 | 直接 API key，最简单的上手方式 |
| Anthropic Claude | P0 | Claude 4.x 系列，强推理能力 |
| Ollama / Local LLM | P1 | 零成本本地体验，降低试用门槛 |
| OpenRouter | P1 | 统一接口，一个 key 访问所有模型 |
| AWS Bedrock | P2 | 企业用户需求 |
| Google Vertex AI | P2 | 企业用户需求 |

#### 3.2 Provider 抽象增强

Provider 抽象已存在于 `providers` 模块，需要：
- 标准化 Provider Protocol (不依赖 OpenAI SDK 特定结构)
- 添加 Provider Plugin 机制 (类似 Harness Plugin)
- 配置层支持 `FSQ_LLM_PROVIDER=anthropic|openai|ollama|openrouter`

---

### Phase 4: 开发者体验优化 (2-4 周)

**目标：5 分钟从安装到第一次自动化**

#### 4.1 Docker 化开箱即用

```dockerfile
# 提供预配置的 Docker image:
# fsq-web:  内置 Playwright browsers, 即开即用
# fsq-android: 内置 ADB + Android emulator
```

```bash
# 用户只需:
docker run -it ghcr.io/microsoft/fsq-web \
  fsq-agent run --platform web --goal "Open bing.com and search for FSQ"
```

#### 4.2 Cloud IDE 即时体验

- GitHub Codespaces devcontainer 配置
- GitPod 配置
- 用户点击按钮即可在浏览器中体验 FSQ

#### 4.3 CLI 增强

```bash
# 新命令建议:
fsq-agent doctor                    # 诊断环境配置，显示哪些平台就绪
fsq-agent scaffold --platform ios   # 生成新 Harness 骨架代码
fsq-agent record --platform web     # 交互式录制模式
fsq-agent convert --from appium     # 从其他框架迁移
```

#### 4.4 Playground 增强

- Harness 能力可视化面板
- 实时录制 + 编辑 FSQ YAML
- 运行历史对比
- 分享运行结果链接

---

### Phase 5: 生态扩展 (中长期, 1-2 季度)

#### 5.1 FSQ Case Registry / Marketplace

- 社区贡献的 FSQ YAML 用例集合
- 按应用/平台/场景分类
- 可分享的 Harness Skills
- 预制的 Application Knowledge 包

#### 5.2 CI/CD 原生集成

```yaml
# GitHub Actions 官方 Action:
- uses: microsoft/fsq-action@v1
  with:
    platform: web
    case-dir: ./tests/fsq-cases/
    strict: true
    report: true
```

同时支持: Azure DevOps, GitLab CI, Jenkins

#### 5.3 IDE 集成

| IDE | 功能 |
|---|---|
| VS Code Extension | FSQ YAML 编辑、语法高亮、Playground 嵌入、运行管理 |
| IntelliJ Plugin | FSQ 用例编辑和运行 |

#### 5.4 SDK / API 模式

```python
# 让 FSQ 不仅是 CLI 工具，也是可嵌入的 SDK:
from fsq_agent import FSQ

async with FSQ(platform="web") as fsq:
    await fsq.run(goal="Navigate to bing.com and search for FSQ")
    report = await fsq.get_report()
```

---

### Phase 6: 技术前沿突破 (长期, 2-4 季度)

| 方向 | 描述 | 价值 |
|---|---|---|
| **Multi-Agent 协作** | 多 Agent 协同完成复杂工作流 | 复杂场景自动化 |
| **视觉 Grounding** | 无需 Accessibility Tree，直接从截图操作 | 覆盖无障碍标记缺失的应用 |
| **自愈 Harness** | AI 自动修复失效的 Locator / 元素定位 | 降低维护成本 |
| **Cloud Harness** | 远程设备 Farm 连接 (Sauce Labs, BrowserStack) | 企业级规模化 |
| **Agent Benchmark** | 标准化的 UI Agent 能力评测 | 成为 AI Agent 社区的基准 |
| **Workflow DSL** | 超越单任务，支持多步骤工作流编排 | RPA 级别的复杂流程 |

---

## 四、长期路线图 (Timeline)

```
2026 Q3 (立即开始)      Phase 1: 社区基础设施 ──────────────┐
  │  CI/CD Pipeline                                        │
  │  Issue/PR Templates                                    │
  │  README 重写 + 品牌定位                                │
  │  CONTRIBUTING 增强                                     │
  └────────────────────────────────────────────────────────┘

2026 Q3-Q4              Phase 2: Harness SDK 开放 ─────────┐
  │  Harness Plugin 架构设计与实现                          │
  │  Harness 开发者指南文档                                │
  │  iOS Harness (社区合作)                                │
  │  Linux Desktop Harness                                 │
  └────────────────────────────────────────────────────────┘

2026 Q4                 Phase 3: 多 Provider 支持 ─────────┐
  │  OpenAI Direct Provider                                │
  │  Anthropic Claude Provider                             │
  │  Ollama/Local LLM Provider                             │
  │  OpenRouter 统一接口                                   │
  └────────────────────────────────────────────────────────┘

2027 Q1                 Phase 4: 开发者体验 ───────────────┐
  │  Docker 镜像发布                                       │
  │  GitHub Codespaces / GitPod 配置                       │
  │  fsq-agent doctor / scaffold 命令                      │
  │  交互式录制增强                                        │
  └────────────────────────────────────────────────────────┘

2027 Q1-Q2              Phase 5: 生态建设 ─────────────────┐
  │  GitHub Action 发布                                    │
  │  VS Code Extension                                     │
  │  FSQ Case Registry                                     │
  │  PyPI 正式版 1.0 发布                                  │
  │  SDK / API 模式                                        │
  └────────────────────────────────────────────────────────┘

2027 H2                 Phase 6: 技术前沿 ─────────────────┐
  │  Multi-Agent 协作自动化                                │
  │  视觉 Grounding (无 accessibility tree)                │
  │  自愈 Harness (AI 自动修复 locator)                    │
  │  Cloud Harness (远程设备 Farm)                         │
  │  Agent Benchmark 标准化                                │
  └────────────────────────────────────────────────────────┘
```

---

## 五、社区增长策略

### 5.1 "Good First Issue" 策略

在 Phase 1 完成后，立即创建 20+ 标记为 `good first issue` 的 Issues:

| 类型 | 示例 Issue |
|---|---|
| 文档 | "Improve macOS platform setup documentation" |
| 文档 | "Add architecture diagram to README" |
| 文档 | "Translate CLI help messages to Chinese" |
| 测试 | "Add edge case tests for config validation" |
| 测试 | "Add integration test examples for Web platform" |
| 小功能 | "Add `--version` flag to CLI" |
| 小功能 | "Add `--verbose` logging option" |
| 小功能 | "Support custom output directory via CLI flag" |
| 新 Driver | "Add Firefox browser support for Web platform" |
| 新 Driver | "Add Safari WebDriver support" |
| 体验优化 | "Better error message when ADB device not connected" |
| 体验优化 | "Add progress indicator during long-running tasks" |

### 5.2 内容营销

| 渠道 | 内容 | 目标 |
|---|---|---|
| 博客 / Dev.to | "Building a Cross-Platform AI Automation Framework" 系列 | 技术影响力 |
| 博客 / Medium | "How FSQ's Harness Architecture Works" 深潜文章 | 吸引架构师 |
| YouTube | "5 Minutes to Automate Any App with FSQ" 教程 | 新用户转化 |
| B 站 | 中文教程系列 | 中国开发者社区 |
| Twitter/X | 功能演示 GIF/视频 | 日常曝光 |
| Hacker News | Show HN: FSQ — Cross-platform AI Automation Framework | 初始爆发 |
| Reddit | r/Python, r/MachineLearning, r/QualityAssurance | 垂直社区 |

### 5.3 与现有社区合作

| 社区 | 合作方式 |
|---|---|
| **Playwright** | FSQ Web Harness 基于 Playwright，交叉推广 |
| **Appium** | macOS Harness 使用 Appium Mac2，合作开发 iOS Harness |
| **OpenAI Agents SDK** | FSQ 是 Agents SDK 优秀应用案例，申请官方 showcase |
| **LangChain / LlamaIndex** | Agent 工具集成 |
| **awesome-* 列表** | 申请收录到 awesome-testing, awesome-python, awesome-ai-agents |

### 5.4 里程碑式 Star 增长目标

| 时间点 | Star 目标 | 关键驱动 |
|---|---|---|
| 2026 年底 | 500+ | Phase 1-2 完成 + HN 发布 |
| 2027 Q1 | 2,000+ | 多 Provider + Docker + 内容营销 |
| 2027 Q2 | 5,000+ | 生态建设 + VS Code Extension |
| 2027 年底 | 10,000+ | 技术前沿突破 + 行业 Conference 演讲 |

---

## 六、Team 分工建议

### 核心角色

| 角色 | 职责 | 人数 |
|---|---|---|
| **Tech Lead** | 架构决策、Plugin 系统设计、Code Review | 1 |
| **Harness Engineer** | Harness/Driver 开发、新平台支持 | 2-3 |
| **Agent Engineer** | LLM Agent 优化、多 Provider、Pre-plan | 1-2 |
| **DX Engineer** | CLI/Playground/文档/Docker/IDE 插件 | 1-2 |
| **Community Manager** | Issue Triage、PR Review、内容营销、社区互动 | 1 |

### 社区贡献者吸引路径

```
新来者 → Good First Issue (文档/小Bug)
      → Regular Contributor (新功能/测试)
      → Harness Author (贡献新平台 Driver)
      → Core Maintainer (架构决策权)
```

---

## 七、立即行动清单 (Top 10)

| # | Action | Owner | 时间 | 优先级 |
|---|---|---|---|---|
| 1 | 创建 GitHub Actions CI workflow (lint + test + build) | DevOps | 2 天 | 🔴 P0 |
| 2 | 创建 Issue/PR Templates | Community | 1 天 | 🔴 P0 |
| 3 | 重写 README.md — 定位为 "AI Automation Framework" | DX | 2 天 | 🔴 P0 |
| 4 | 增强 CONTRIBUTING.md + 添加架构图 | DX | 2 天 | 🔴 P0 |
| 5 | 设计 Harness Plugin Protocol (RFC) | Tech Lead | 1 周 | 🟡 P1 |
| 6 | 编写 Harness 开发者指南文档 | Harness Eng | 1 周 | 🟡 P1 |
| 7 | 创建 20 个 Good First Issues | Community | 2 天 | 🟡 P1 |
| 8 | 添加 OpenAI Direct Provider | Agent Eng | 3 天 | 🟡 P1 |
| 9 | 准备 Hacker News / Reddit 发布文案 | Community | 3 天 | 🟡 P1 |
| 10 | 设计 `fsq-agent doctor` 命令 | DX | 3 天 | 🟢 P2 |

---

## 八、成功指标 (KPIs)

| 指标 | 当前值 | 6 个月目标 | 12 个月目标 |
|---|---|---|---|
| GitHub Stars | 9 | 2,000 | 10,000 |
| GitHub Forks | 0 | 200 | 1,000 |
| Monthly Contributors | 0 (内部) | 10+ | 50+ |
| Supported Platforms | 4 | 6+ | 8+ |
| LLM Providers | 2 | 5+ | 8+ |
| PyPI Monthly Downloads | 0 | 5,000 | 50,000 |
| Community Harness Plugins | 0 | 2+ | 5+ |
| Documentation Pages | ~10 | 30+ | 60+ |

---

## 附录: 技术架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FSQ Framework                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐   ┌──────────────┐   ┌──────────────┐                 │
│  │   CLI   │   │  Playground  │   │  SDK (future)│                 │
│  └────┬────┘   └──────┬───────┘   └──────┬───────┘                 │
│       │                │                   │                        │
│  ┌────▼────────────────▼───────────────────▼───────┐                │
│  │              Agent Runtime                       │                │
│  │  ┌─────────────┐  ┌───────────┐  ┌──────────┐  │                │
│  │  │  Pre-Plan   │  │  Executor │  │ Verifier │  │                │
│  │  └─────────────┘  └─────┬─────┘  └──────────┘  │                │
│  └──────────────────────────┼──────────────────────┘                │
│                             │                                       │
│  ┌──────────────────────────▼──────────────────────┐                │
│  │            Execution Core (StepRunner)           │                │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────┐  │                │
│  │  │ Capabilities │  │  Evidence  │  │ Report │  │                │
│  │  └──────────────┘  └────────────┘  └────────┘  │                │
│  └──────────────────────────┬──────────────────────┘                │
│                             │                                       │
│  ┌──────────────────────────▼──────────────────────┐                │
│  │          Harness Abstraction Layer               │                │
│  │                                                  │                │
│  │  ┌─────────────────────────────────────────────┐ │                │
│  │  │          HarnessInterface (Protocol)        │ │                │
│  │  └──────┬──────────┬───────────┬───────────┬───┘ │                │
│  │         │          │           │           │     │                │
│  │  ┌──────▼───┐ ┌────▼────┐ ┌───▼────┐ ┌────▼──┐  │                │
│  │  │ Android  │ │   Web   │ │Windows │ │ macOS │  │                │
│  │  │ Harness  │ │ Harness │ │Harness │ │Harness│  │                │
│  │  └──────┬───┘ └────┬────┘ └───┬────┘ └────┬──┘  │                │
│  │         │          │           │           │     │                │
│  │  ┌──────▼───┐ ┌────▼─────┐ ┌──▼──────┐ ┌──▼───┐ │                │
│  │  │UiAuto-  │ │Playwright│ │Pywinauto│ │Appium│ │                │
│  │  │mator2   │ │  Driver  │ │ Driver  │ │Mac2  │ │                │
│  │  └─────────┘ └──────────┘ └─────────┘ └──────┘ │                │
│  │                                                  │                │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐          │  ← Future     │
│  │  │  iOS    │  │  Linux  │  │Electron │  ...     │    Plugins    │
│  │  │ Plugin  │  │  Plugin │  │ Plugin  │          │                │
│  │  └─────────┘  └─────────┘  └─────────┘          │                │
│  └──────────────────────────────────────────────────┘                │
│                                                                     │
│  ┌──────────────────────────────────────────────────┐                │
│  │           LLM Provider Layer                     │                │
│  │  ┌────────┐ ┌───────┐ ┌────────┐ ┌──────┐       │                │
│  │  │Copilot │ │Azure  │ │OpenAI  │ │Claude│ ...   │                │
│  │  └────────┘ └───────┘ └────────┘ └──────┘       │                │
│  └──────────────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

---

*本文档由 FSQ 团队于 2026-07-30 编写，作为开源战略规划的内部讨论材料。*


核心优势

  1. Harness 执行协议已经成型
     fsq_agent/core/SPEC.md:1 定义了 prepare -> invoke -> finalize 的统一执行模型，StepRunner 负责 evidence、delay、secret resolution、event、result normalization。这是
     harness 库的核心资产。

  2. Capability metadata 驱动设计很强
     当前能力不是简单硬编码命令表，而是 decorator + catalog + registry + replay policy。这个设计可以演化成插件生态。

  3. Strict replay 和 dynamic recording 是差异化能力
     动态 agent 执行后能从真实成功能力事件生成 strict FSQ YAML，这一点很适合社区贡献测试资产。

  4. 多平台方向已经打开
     Android、Web、Windows、macOS 都有平台块和 backend 实现路径。虽然成熟度不均，但架构没有被单一平台绑死。

  5. Playground 有产品雏形
     fsq_agent/playground/SPEC.md:1 已经覆盖运行、进度、回放、报告、YAML 展示、step artifact 预览。这是未来社区 demo、debug、case authoring 的入口。

  主要差距

  1. 贡献者首次体验不合格
     npm ci、uv run pytest 目前都不能直接成功。这必须作为 P0。

  2. 没有 GitHub Actions workflow
     .github/workflows 为空。开源后没有 CI，社区 PR 无法形成可信反馈闭环。

  3. Harness 扩展还不是公开 SDK
     现在新增平台/后端需要改 core 私有 dispatch 表、models 参数模型、platform catalog、config preset 等多个内部位置。对内部开发可接受，对社区插件生态不够友好。

  4. README 是开发说明，不是产品入口
     当前 README.md:1 偏环境配置。缺少“FSQ 是什么、为什么比 Playwright/Appium/Midscene 更值得用、5 分钟 strict run、5 分钟 AI run、如何贡献一个 harness”的叙事。

  5. 文档资产不少，但没有信息架构
     docs/ 里有架构文档和历史设计，但缺少稳定的 public docs：DSL reference、capability reference、harness authoring guide、evidence manifest spec、plugin guide、roadmap。

  6. SPEC 与代码存在小的同步风险
     例如 fsq_agent/core/SPEC.md:42 提到 fsq_agent.core.registry 子包导出，但实际没有 fsq_agent/core/registry.py 或 core/registry/。这类问题对 SDD 项目尤其要严肃处理。

  0-2 周可执行计划：先把开源地基打稳

  1. 修复本地 bootstrap
      - 同步 package-lock.json，确保 npm ci && npm run build 在 Node 20.19 和 22.12 上通过。
      - 解决 Python 测试依赖前端生成目录的问题：要么让 editable/test 不依赖 static，要么提交可保留的 static 目录占位并调整 .gitignore。
      - README 增加一条明确验证路径：uv sync --extra dev、npm ci、npm run build、uv run python -m pytest。

  2. 建立 CI
      - python.yml: uv sync --extra dev、pytest、ruff、SPEC/code sync smoke。
      - frontend.yml: Node 20/22 matrix，npm ci、npm run build。
      - package.yml: build wheel，验证 wheel 内含 Playground 静态资产。
      - 平台 extras 分开做 optional smoke，避免普通 PR 被 Android/Appium/Windows 环境阻塞。

  3. 整理 GitHub 社区入口
      - issue templates：bug、feature、new harness/backend、docs、good first issue。
      - PR template：SPEC impact、tests run、platform touched、screenshots/artifacts。
      - CODEOWNERS：core/models/capabilities/cli/playground/platform backend 分 owner。
      - label 体系：area:harness, area:dsl, area:playground, good first issue, needs-design, platform:web 等。

  4. 重写 README 第一屏
      - 一句话定位：FSQ 是 “AI-assisted automation + deterministic replay + evidence-first harness framework”。
      - 两条 quickstart：strict YAML 无 LLM；dynamic goal 有 LLM。
      - 明确社区贡献路径：写 case、补平台能力、加 harness backend、改 Playground、改 docs。

  30-60 天：把 FSQ 变成可扩展 Harness SDK

  1. 设计公开 SDK 边界
      - 新增或规划 fsq_agent.sdk / fsq_agent.harness 公共包。
      - 公开稳定类型：HarnessPlugin, PlatformDefinition, CapabilityDefinition, ArtifactStore, HarnessInterface, DriverObservationInterface。
      - 支持 Python entry points，例如第三方包可注册 fsq_agent.platforms。
      - 内置平台仍保留，但走同一插件注册路径。

  2. 拆分“内置平台”和“扩展平台”
      - 内置 Android/Web/Windows/macOS 作为 first-party plugins。
      - 新平台不再必须改 core 私有表。
      - 平台参数模型和 replay alias 用插件 metadata 注册。

  3. 发布 Harness Authoring Guide
      - “写一个最小平台 backend”。
      - “写 capability 参数模型”。
      - “写 evidence capture”。
      - “如何支持 strict replay”。
      - “如何写 fake driver 测试，不依赖真实设备”。

  4. 建立公开 DSL Reference
      - .codex.yaml schema。
      - lifecycle hooks。
      - runtime secrets。
      - platform capability reference。
      - strict vs dynamic 行为差异。

  5. 做 benchmark 和 showcase
      - Web: 一个公开 demo app。
      - Android: 一个稳定 sample app。
      - Desktop: Calculator/Edge/简单 Electron app。
      - 指标：首次成功率、strict replay 成功率、flake rate、平均 step evidence 完整率、动态录制可 replay 率。

  60-90 天：形成社区增长飞轮

  1. Case Hub
      - examples/ 升级为 curated cases。
      - 每个 case 有平台、预期、运行命令、报告样例。
      - 允许社区提交真实产品的 anonymized/open cases。

  2. Harness Compatibility Matrix
      - 平台 x backend x OS x Python x capability。
      - 自动从 tests/CI/report 生成状态页。

  3. Playground 变成贡献入口
      - 支持从 UI 运行 strict case、查看 evidence、导出 minimized repro。
      - 支持“录制动态运行 -> 生成 strict YAML -> 本地编辑 -> PR”。

  4. 治理机制
      - 每周 triage。
      - 月度 roadmap issue。
      - good first issue 保持 10-20 个。
      - “new platform proposal” 模板，强制先写 design/spec。

  长期路线图

  1. Harness Core 成为独立价值
      - 即使不用 LLM，也能作为 evidence-first automation runner 使用。
      - 类似 pytest 的执行协议，但面向 UI automation：phase report、artifact、teardown、failure category。

  2. AI Automation 层建立在可信 replay 上
      - 动态 agent 负责探索、修复、生成候选 case。
      - strict runner 负责回归、CI、审计。
      - 所有 AI 结果必须落到 evidence 和 replayable steps。

  3. 跨平台统一 observation model
      - Android XML、Web accessibility snapshot、Windows UIA、macOS Appium source 统一到 normalized ui_snapshot。
      - 后续可以做 locator memory、diff、failure clustering、self-healing 建议。

  4. 开放插件生态
      - iOS、Electron、Selenium Grid、BrowserStack、Sauce Labs、WinAppDriver、custom enterprise apps 都应能作为第三方 package 接入。
      - FSQ 主仓库只维护协议、内置参考实现和兼容性测试。

  5. 可信 AI Assertion
      - assertWithAI 保持显式能力，不偷偷替代 deterministic assertion。
      - 报告里保留 prompt、截图、verdict、模型、置信度、反证 evidence。
      - 长期目标是“AI 判断可审计”，不是“AI 说过就算过”。

  建议第一批 SDD 主题

  1. open-source-contributor-bootstrap-design：修复构建/测试/CI/README 首次体验。
  2. public-harness-plugin-sdk-design：把当前内部 harness 扩展机制变成公开 SDK。
  3. dsl-reference-and-capability-docs-design：生成稳定 public docs。
  4. benchmark-and-compatibility-matrix-design：定义世界级工具必须公开的质量指标。
  5. playground-contributor-workflow-design：让 Playground 支持录制、调试、导出、贡献。

  我建议第一轮先做 open-source-contributor-bootstrap，因为现在外部贡献者最先遇到的不是架构问题，而是跑不起来。确认后就应该按仓库 SDD 流程走 requirements-to-design，生成设
  计文档，再进入 spec-driven 实施。



### 关键短板（阻碍"世界顶级开源"的地方）

 A. 社区协作基础设施缺失（最紧急）
 - ❌ 没有任何 CI/CD（.github/workflows 为空）—— 社区 PR 无法自动验证，这是致命伤
 - ❌ 没有 Issue 模板、PR 模板、CODEOWNERS
 - ❌ 没有发布到 PyPI（version = 0.1.0，用户只能源码安装）
 - ❌ 没有 ROADMAP.md、GOVERNANCE.md、贡献者成长路径

 B. "Harness 库"定位没有被产品化
 - Harness 是最大卖点，但目前深埋在 core 内部，无法被外部作为独立库/插件使用
 - 没有"如何新增一个平台后端"的插件机制文档 —— 社区想贡献新 harness（如 iOS、Linux、Flutter）门槛极高
 - capabilities 装饰器体系很好，但对外没有 SDK 式的 API 文档

 C. 上手门槛与叙事
 - README 密度极高、术语先行（CommonTool/PlatformTool/ReplayPolicy…），新用户 30 秒内看不懂它能干什么
 - 没有演示 GIF/视频、没有 badges、没有"5 分钟 quickstart"
 - 文档是"架构说明书"而非"用户旅程"

 D. 质量可见性
 - 仅 35 个测试文件，覆盖率不可见（无 coverage 报告）
 - 无 lint/type-check 强制（ruff 已配但未 CI 化，无 mypy）

 ────────────────────────────────────────────────────────────────────────────────

 二、可执行方案（分 3 阶段，约 12 周）

 ### 🔴 阶段一：开源"可信任基线"（第 1–3 周，最高优先级）

 目标：让社区 PR 能被自动验证、让项目看起来"活着且专业"。

 1. 建立 CI 流水线 .github/workflows/
     - ci.yml：矩阵测试（Python 3.11/3.12 × macOS/Ubuntu/Windows）+ ruff check + pytest
     - frontend.yml：npm ci && npm run build 验证
     - 加 mypy（渐进式，先 models/capabilities 严格模式）
 2. 社区模板：Issue 模板（bug/feature/new-platform）、PR 模板、CODEOWNERS、ROADMAP.md
 3. README 重写：顶部一句话价值主张 + 演示 GIF + badges + 5 分钟 quickstart，把架构细节移到 docs/
 4. 发布 PyPI：release.yml（tag 触发，build wheel 含 frontend 资产 → publish），让用户 pip install fsq-agent
 5. 测试覆盖率可见：pytest-cov + Codecov badge

 我可以直接生成阶段一的所有文件。

 ### 🟡 阶段二：让 Harness 成为"可被贡献"的库（第 4–8 周）

 这是把 FSQ 从"工具"升级为"Harness 开源库"的关键。

 1. 抽出 Harness 插件契约：基于现有 HarnessInterface/Driver/capabilities 装饰器，定义外部平台插件的 entry-point 注册机制（Python entry_points），让第三方包能注册新平台而
    不改 core
 2. 写《Building a New Harness》权威指南：用一个最小示例（如 Linux xdotool 或 iOS）走通全流程 —— 这是社区最想要的贡献入口
 3. Capability SDK 文档：把 @capability 装饰器、ReplayPolicy、参数 schema 做成对外 API reference（可用 mkdocs-material 生成文档站）
 4. 示例库 examples/：每个平台一个端到端可跑 demo + 对应 FSQ YAML

 ### 🟢 阶段三：增长与生态（第 9–12 周）

 1. 文档站上线（mkdocs-material + GitHub Pages）：Getting Started / Concepts / Harness SDK / API Reference
 2. good first issue / help wanted 标签体系 + 每个都写清验收标准
 3. Playground 一键体验（Docker / Codespaces devcontainer）
 4. Benchmark：建立 automation 成功率评测集，公开 leaderboard —— 这是"世界顶级"的技术信誉来源

 ────────────────────────────────────────────────────────────────────────────────

 三、长期规划（6–18 个月）

 ### 技术护城河

 - Harness 生态：目标让 iOS、Linux、Flutter、React Native、Terminal/TUI 等由社区贡献 harness 插件，FSQ 成为"跨平台 automation 的 harness 标准层"
 - 录制→回放闭环产品化：dynamic 录制生成 strict YAML 已有基础，做成"AI 探索 + 确定性回归"的 CI 测试方案（对企业最有价值）
 - 模型无关：抽象 provider 层（现已支持 Copilot/Azure），扩展到 Anthropic/local(ollama/vLLM)，降低使用门槛
 - 可靠性：self-healing locator、失败重规划、evidence-based 验证的准确率评测

 ### 社区与治理

 - 从 Microsoft 单一维护 → 开放治理（maintainer 提名机制、RFC 流程复用现有 SDD 的 design-doc 文化，这是天然优势）
 - 建立 Discord/Discussions、月度 roadmap 更新、release 节奏（每 2–4 周）

 ### 商业/影响力

 - 对标定位：**"Playwright + AI Agent + 跨平台"**的开源标准
 - Benchmark leaderboard + 学术/技术博客建立技术信誉

 ────────────────────────────────────────────────────────────────────────────────

 建议的第一步

 阶段一投入产出比最高，且能立刻让社区参与成为可能。我可以现在就为你生成阶段一的全部落地文件：

 - .github/workflows/ci.yml + release.yml + frontend.yml
 - Issue/PR 模板、CODEOWNERS、ROADMAP.md
 - 重写后的 README（含 quickstart 骨架）
 - pytest-cov 配置
