# FSQ 下一代 CLI：团队内部讨论稿

**用途：** 团队讨论与决策同步
**日期：** 2026-08-13
**状态：** 内部 Review

> 本文不是 SPEC、实现依据或最终 API 承诺。完整技术设计见 [FSQ Next-Generation CLI Design](./2026-08-13-next-generation-cli-design.md)。团队 Review 后，最终确认的 Design Doc 才可进入后续 Spec-Driven 流程。

## 1. 为什么要重新设计 CLI

当前 `fsq-agent run` 同时承载 AI 测试、严格回放、单文件与目录执行、录制、流式输出和 Tart 环境管理。用户需要先理解 FSQ 的内部执行模式，才能组合出合法参数；Coding Agent 还需要自行解析日志、识别错误类型和寻找产物。

本次调整希望解决四个问题：

1. 让用户一眼区分“AI 参与的测试”和“确定性回放”。
2. 让 CLI 同时成为人类、CI 和 Coding Agent 的稳定入口。
3. 把 Tart 从 CLI 特例提升为可扩展的 Environment Provider 模型。
4. 让 CLI 与 Control Plane 使用同一套执行服务和 Run 数据，不再分别维护执行语义。

## 2. 第一阶段命令树

```text
fsq
├── init
├── doctor
├── test
├── replay
├── ui
├── providers
│   ├── list
│   ├── configure NAME
│   └── status [NAME]
├── runs
│   ├── list
│   ├── show RUN_ID
│   └── logs RUN_ID
└── environments
    ├── list
    └── doctor NAME
```

暂不公开：

- Extension 安装与管理
- Actions/Capabilities 查询
- Environment 创建、删除和清理
- Run 取消和删除
- 后台任务、并发、分片和测试矩阵

新的主程序名为 `fsq`。`fsq-agent` 在迁移期指向同一套新命令，但旧命令语法不做自动转发。

## 3. 最关键的边界：Test 与 Replay

### Test：AI 参与

```bash
fsq test --platform web --goal "验证用户可以搜索商品"

fsq test \
  --platform web \
  --intent tests/search.intent.yaml
```

Test 的含义是：

- AI 理解测试目标；
- AI 可以规划操作；
- AI 可以处理定位变化和执行恢复；
- AI 根据 Evidence 验证结果；
- 成功后默认尝试生成可严格回放的候选 Workflow。

AI 不会修改输入的 Goal 文件或 Intent 文件。候选 Workflow 只生成在本次 Run 的输出目录中，由用户或 Coding Agent Review 后再纳入正式测试资产。

### Replay：严格模式

```bash
fsq replay --platform web tests/search.fsq.yaml
```

Replay 的含义是：

- 按 Workflow 确定性执行；
- AI 不参与规划、定位修复或失败恢复；
- 不修改源 Workflow；
- 只有 Workflow 明确写入 AI Assertion 时，才允许模型执行该断言。

因此不再需要：

```text
run --strict
```

`replay` 本身就是严格模式。

## 4. 两类测试文件

### `*.intent.yaml`：描述“测试什么”

```yaml
schemaVersion: fsq.test-intent/v1
name: Search products
platform: web
goal: >
  搜索指定商品，并验证结果列表包含相关商品。
tags:
  - smoke
context:
  startUrl: https://example.com
```

Intent 面向 AI，不包含必须逐条执行的严格命令。

### `*.fsq.yaml`：描述“具体怎么执行”

它是 Replay 使用的确定性 Workflow。AI Test 成功后，可以根据实际成功执行的可重放操作生成：

```text
candidate.fsq.yaml
```

旧的 `*.codex.yaml` 暂时兼容一个弃用周期；新生成的文件统一使用 `*.fsq.yaml`。系统不会自动重命名旧文件。

## 5. Runs 是什么

每次 Test 或 Replay 都产生一个持久化 Run。Run 是本次测试的完整记录，而不只是最终报告。

```text
Run
├── 状态与时间
├── 输入 Goal、Intent 或 Workflow 摘要
├── 平台与 Environment
├── 执行事件和日志
├── 验证结果与失败分类
├── Report
├── Screenshots 和 UI snapshots
└── Candidate Workflow
```

查询方式：

```bash
fsq runs list
fsq runs show RUN_ID
fsq runs logs RUN_ID
```

目录批量执行时，每个文件产生独立子 Run，外层再产生一个 Batch Run 汇总结果。第一阶段默认递归发现、稳定排序并串行执行，避免多个测试共享设备状态。

## 6. Coding Agent 如何使用

CLI 对人和 Coding Agent 使用同一命令树，通过全局输出模式区分消费方式：

```bash
fsq --output human test ...
fsq --output json test ...
fsq --output jsonl test ...
```

- `human`：面向终端用户。
- `json`：只输出一个最终结果对象。
- `jsonl`：输出实时事件，最后一行一定是终态。
- `--non-interactive`：禁止提示、确认和交互认证。

结构化结果会稳定提供：

- Run ID
- 测试状态
- Report 路径
- Evidence manifest 路径
- Candidate Workflow 路径
- 稳定错误码和安全的下一步建议

退出码用于区分顶层结果：

| Code | 含义 |
|---:|---|
| `0` | 命令成功，测试通过 |
| `1` | 测试失败或无法可靠判定 |
| `2` | 命令用法、输入或 Schema 错误 |
| `3` | 配置、认证、Provider 或 Environment 未就绪 |
| `4` | Driver、设备、网络、VM 或远程基础设施错误 |
| `5` | FSQ 内部错误 |
| `130` | 用户中断 |

这样 Coding Agent 可以区分“产品测试失败”和“测试工具根本没有正常运行”。

## 7. Environment Provider：从 Tart 特例走向通用设备模型

命令只选择 Environment Profile：

```bash
fsq replay \
  --platform macos \
  --environment macos-tart \
  tests/settings.fsq.yaml
```

Tart 的模板、UI 模式、超时和保留策略不再作为 CLI 参数，而是写入 `config.macos.yaml`：

```yaml
environments:
  local:
    provider: local

  macos-tart:
    provider: tart
    template: fsq-macos-base
    display: headless
    retention:
      onSuccess: delete
      onFailure: keep
```

Environment Provider 负责：

```text
检查 → 获取设备/VM → 准备服务 → 提供连接 → 收集诊断 → 释放或保留
```

Driver 只负责操作已经准备好的目标。

第一阶段实现 Local 和 Tart，但接口为未来以下场景保留空间：

- Appium Grid
- BrowserStack / Sauce Labs
- AWS Device Farm
- Windows/macOS 云 VM
- 企业内部真机实验室

未指定 `--environment` 时始终使用 `local`，避免意外创建远程或收费资源。

## 8. Init、Doctor、Providers 和 UI

### Init

```bash
fsq init
```

只初始化当前目录的 `.fsq-agent-workspace`，不再选择平台或配置模型。

### Doctor

```bash
fsq doctor --platform web
fsq doctor --platform macos --environment macos-tart
```

综合检查 Workspace、Provider、Driver、平台依赖和 Environment，但默认不会创建 VM、申请云设备或发送模型请求。

### Providers

```bash
fsq providers list
fsq providers configure github-copilot
fsq providers status azure-openai
```

第一阶段继续使用当前目录 `.env` 保存 Provider 配置。Secret 不得出现在日志、报告或机器输出中。`test` 不提供临时 `--provider` 或 `--model` 参数。

### UI

```bash
fsq ui
```

`fsq ui` 启动正式 Control Plane。旧 Playground 不再作为公开入口。CLI 和 UI 共享 Test、Replay、Runs 和 Environment 服务，避免出现两套行为。

## 9. 对现有用户的主要影响

这是一次 Breaking Change：

| 旧方式 | 新方式 |
|---|---|
| `fsq-agent run --goal ...` | `fsq test --goal ...` |
| `fsq-agent run --case-yaml ...` | 创建 Intent，使用 `fsq test --intent ...` |
| `fsq-agent run --strict --case-yaml ...` | `fsq replay ...` |
| `fsq-agent report --run-id ...` | `fsq runs show ...` |
| `fsq-agent control-plane` | `fsq ui` |
| `fsq-agent playground` | 不再公开 |

旧命令不会静默转发，避免系统猜错用户意图。调用旧命令会得到迁移提示。

保留的兼容项：

- `.fsq-agent-workspace` 和现有输出根目录继续使用；
- `fsq-agent` 程序名在迁移期继续存在；
- `*.codex.yaml` 在一个弃用周期内仍可 Replay。

## 10. 建议的实施顺序

1. **统一应用服务与结果模型**：让 CLI 和 Control Plane 共享 Test、Replay、Run、Environment 和 Provider 编排。
2. **切换新命令树**：加入 `fsq`，统一 Human/JSON/JSONL 和退出码。
3. **分离 Intent 与 Workflow**：引入 `*.intent.yaml`、`*.fsq.yaml` 和候选 Workflow。
4. **重构 Environment**：统一 Local/Tart 生命周期，把 Tart 配置迁入 Profile。
5. **稳定 Runs 与 UI**：建立 `run.json`、Batch Run 和查询命令，Control Plane 使用相同数据。
6. **文档与迁移收尾**：更新 README、CI/Coding Agent 示例，并公布弃用时间表。

第一阶段不引入 Daemon、数据库、消息队列或异步任务系统。

## 11. 请团队重点 Review

### 产品与用户体验

1. `test` 与 `replay` 的命名和边界是否足够直观？
2. 是否接受旧动态 Case 不自动转换为 Intent？
3. 成功的 Test 默认生成 Candidate Workflow 是否符合预期？
4. 第一阶段公开命令是否仍然过多或过少？

### 测试资产

5. `*.intent.yaml` 的最小字段和 `context` 应包含哪些内容？
6. `*.fsq.yaml` 与旧 `*.codex.yaml` 的兼容期应该到哪个版本或日期？
7. 如何判断目录中一对新旧文件是同一个 Workflow，避免重复运行？

### 架构与扩展

8. 共享应用服务应该放在哪个 Python 模块？
9. Local 和 Tart 的封闭 Profile Schema 是否足以支撑第一阶段？
10. 为云设备预留的 Environment Lease/connection 信息是否完整？
11. Control Plane 是否可以同步改用 Test/Replay 术语？

### 发布与迁移

12. 这次 Breaking Change 采用哪个版本发布？
13. `fsq-agent` 程序名保留到哪个版本？
14. 历史 Run 的只读兼容支持保留多久？
15. 是否需要在正式发布前提供预览版本或迁移验证期？

## 12. 本轮希望达成的团队结论

团队 Review 最少需要确认：

- 命令树和 Test/Replay 边界；
- Intent/Workflow 文件模型；
- Run 和机器协议方向；
- Environment Provider 与 Tart 迁移方向；
- Breaking Change 的发布与兼容策略；
- 第一阶段范围，以及明确延后的能力。

具体参数、Schema 和模块落点会在正式 Spec-Driven 阶段进一步收敛。
