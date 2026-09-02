# 快速开始

这份指南帮助新用户从安装开始，完成一次针对公开 [TodoMVC](https://todomvc.com/examples/react/dist/) 的确定性 Web Run。FSQ v0.1.0 是 Alpha 软件；生产采用前请先阅读[支持与稳定性说明](support-and-stability.md)。

## 前置条件

- Python 3.11 或更新版本。
- 已安装受支持的 Chromium 系浏览器。示例使用稳定版 Chrome。
- 一个可用作本地 FSQ Workspace 的空目录。

AI 探索和 suggestion 分析还需要 GitHub Copilot 或 Azure OpenAI。确定性 Case 重放不需要规划 LLM，除非已编写的 Case 包含 AI assertion。

## 安装

```bash
python -m pip install fsq-agent
fsq --help
```

基础包包含所有支持平台的 Python 依赖。FSQ 不会安装浏览器、应用、ADB、设备、Appium 服务或其他主机前置条件。

## 初始化空 Workspace

```bash
mkdir fsq-web-demo
cd fsq-web-demo
fsq init --platform web --browser-channel chrome
fsq doctor
```

如果当前目录为空，它会成为 Workspace root。如果当前目录非空，`init` 会保留它并创建一个缺失的 `<current-directory>/<workspace-name>` 子目录。其他 Workspace 命令必须在准确注册的 root 中运行；它们不会向父目录搜索。

## 运行公开确定性示例

把当前的 [`examples/web/example-domain.fsq.yaml`](../examples/web/example-domain.fsq.yaml) 下载到 Workspace 的 `cases/web/`，然后运行：

```bash
mkdir -p cases/web
curl --fail --location --output cases/web/example-domain.fsq.yaml \
  https://raw.githubusercontent.com/microsoft/FSQ/main/examples/web/example-domain.fsq.yaml
fsq case test --platform web cases/web/example-domain.fsq.yaml
fsq runs list --platform web
```

这个 Case 会启动已配置的浏览器，打开 TodoMVC，添加两个任务、完成第一个任务、筛选未完成任务、验证预期可见状态，然后关闭浏览器。证据保存在 `.fsq/runs/web/<run-id>/` 下。

## 配置 AI 探索

```bash
fsq providers configure github_copilot
fsq providers status
```

也可以运行 `fsq providers configure azure_openai`。Provider 配置是用户级配置，保存在 `~/.fsq` 下，并与本地 Control Plane 共享。

## 探索与检查

```bash
fsq case create --platform web --goal "Open https://example.com and verify the Example Domain heading is visible."
fsq runs list
fsq runs show RUN_ID
fsq runs logs RUN_ID
fsq runs show RUN_ID --open
```

最后一个命令基于已保存的 Run 事实创建离线报告。它不会操作目标 UI，也不会调用 Provider。

## 分析确定性 Run

```bash
fsq case test --platform web --suggest cases/web/example-domain.fsq.yaml
```

Case 只执行一次。随后 AI 分析只消费源 Case、报告和已保存证据。建议和任何候选 Case 都只保留在对应 Run 内。

## 打开 Control Plane

```bash
fsq ui
```

安装后的前端默认在本地 `127.0.0.1:8879` 提供服务。

## 下一步

- 阅读[平台前置条件](platform-prerequisites.md)。
- 学习 [Case 格式](case-format.md)。
- 查看 [CLI reference](cli-reference.md)。
- 实现级架构与行为契约请查阅根目录及各模块的 `SPEC.md` 文件。
