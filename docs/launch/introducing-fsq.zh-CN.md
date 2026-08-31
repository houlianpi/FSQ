# 介绍 FSQ：可检查、可重放的证据优先 AI UI 自动化

AI 可以操作用户界面，但“Agent 说任务完成了”并不足以构成可信的测试。团队需要看见实际发生的过程，检查判断结果所依据的事实，并在不让模型重新探索的情况下重复成功路径。

FSQ 是为这一工作流打造的开源、证据优先 UI 自动化 Agent Harness。

## 从自然语言目标到可检查事实

向 FSQ 提供一个用户可见的目标。执行过程中，FSQ 会把截图、标准化 UI Snapshot、有序事件、元数据和报告保存在同一个本地 Run 中。验证基于已有证据，而不仅仅依赖 Agent 的文字结论。

探索成功后，FSQ 可以根据真实操作生成一份供人工审查的 YAML Case。审查后的 Case 可以通过同一个平台 Harness 确定性重放，并生成新的回归证据。

## 四个平台，共享一套模型

FSQ 使用成熟的平台后端：Web 使用 Playwright，Android 使用 uiautomator2，Windows 使用 pywinauto，macOS 使用 Appium Mac2。FSQ 在其上提供统一的 Case、执行生命周期、证据、验证、Run 历史、就绪诊断和本地 Control Plane。

## 本地优先

Workspace 文件和 Run 证据保存在本地。Provider 配置存储在用户级 FSQ 配置目录，并由 CLI 与 Control Plane 共享。需要模型的操作会使用已配置的 GitHub Copilot 或 Azure OpenAI Provider。

## 体验 Alpha 版本

```bash
python -m pip install fsq-agent
mkdir fsq-web-demo && cd fsq-web-demo
fsq init --platform web --browser-channel chrome
fsq doctor
```

v0.1.0 是 Alpha 版本，适合评估、实验和早期贡献，但不是 1.0 兼容性承诺。

请从[入门指南](../getting-started.md)开始，阅读[架构说明](../architecture.md)，并通过[贡献指南](../../CONTRIBUTING.md)参与项目。
