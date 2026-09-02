核心内容： 

Planner output / FSQ step
    -> StepBuilder / TaskBuilder
    -> ExecutableStep / ExecutionTask
    -> StepRunner / TaskRunner
    -> Harness Interface
    -> Evidence Bundle

这条链路建议在 FSQ-Agent 里统一改成 FSQ 命名，不要继续保留 / TaskBuilder、/ ExecutionTask、/ TaskRunner，否则团队分工时会混
  乱。

  推荐写法：

  Planner output / FSQ step
    -> StepBuilder
    -> ExecutableStep
    -> StepRunner
    -> HarnessInterface
    -> EvidenceBundle

  对应 Midscene 对照可以单独说明：

   FSQ-Agent           Midscene 对照                      作用
  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   StepBuilder         TaskBuilder                        把语义步骤编译成可执行步骤
  ──────────────────  ─────────────────────────────────  ────────────────────────────
   ExecutableStep      ExecutionTask                      内部可执行单元
  ──────────────────  ─────────────────────────────────  ────────────────────────────
   StepRunner          TaskRunner                         状态机执行器
  ──────────────────  ─────────────────────────────────  ────────────────────────────
   HarnessInterface    AbstractInterface + actionSpace    平台能力合同
  ──────────────────  ─────────────────────────────────  ────────────────────────────
   EvidenceBundle      ExecutionDump / report dump        执行事实与调试证据

  所以更准确的团队沟通版本是：

  FSQ:
  Planner output / FSQ step
    -> StepBuilder
    -> ExecutableStep
    -> StepRunner
    -> HarnessInterface
    -> EvidenceBundle

这个部分已经实现： 
 Owner 1: Step Contract & Builder
    Planner output / FSQ step
    -> StepBuilder
    -> ExecutableStep

每层边界

  StepBuilder / TaskBuilder owner：

  输入:
    Planner output
    FSQ step

  输出:
    ExecutableStep[]

  负责:
    schema normalization
    action lookup
    target resolution planning
    evidence policy attachment
    retry policy attachment

  禁止:
    不调用 harness
    不写 evidence 文件
    不决定 case pass/fail

  ExecutableStep / ExecutionTask contract owner：

  这是 Builder 和 Runner 的接口。
  必须由资深工程师把关。

  它定义:
    step_id
    source_ref
    kind
    action_name
    params
    target_ref
    retry_policy
    evidence_policy
    timeout



剩下的部分，建议参考pytest，并且遵循 FSQ-Agent 代码仓库契约。

可以明确说：pytest 对 FSQ 的参考价值非常高，但应该参考它的架构协议，不要照搬代码。

  pytest 的核心启发

  pytest 的执行核心不是“直接跑 test function”。它有清晰分层：

  Session
    -> runtestloop
    -> runtest_protocol(item)
    -> setup phase
    -> call phase
    -> teardown phase
    -> TestReport
    -> logreport hooks

  对应到 FSQ：

  ExecutionSession
    -> StepRunner
    -> run_step_protocol(executable_step)
    -> prepare phase
    -> invoke phase
    -> finalize phase
    -> StepReport / StepResult
    -> EvidenceRecorder hooks

  这是最值得借鉴的点：每个可执行单元都走统一协议，而不是直接调用 action。

  建议的三模块定位

  你现在关注的是：

  StepRunner / TaskRunner
    -> Harness Interface
    -> Evidence Bundle

  我建议把它们定义成：

  StepRunner = 执行协议和状态机
  HarnessInterface = 平台能力与上下文提供者
  EvidenceBundle = 事实记录格式

  更准确一点：

  StepRunner owns control.
  Harness owns capability.
  Evidence owns history.

  1. StepRunner 参考 pytest runner

  pytest 的 runtestprotocol() 做了三段：

  setup
  call
  teardown

  FSQ 可以采用类似协议，但命名更贴近 UI 自动化：

  prepare
  invoke
  finalize

  或者：

  observe_before
  call
  observe_after

  推荐：

  prepare
  invoke
  finalize

  含义：

  prepare:
    获取 ExecutionContext
    调用 harness.before_action
    捕获 before evidence
    检查 step 是否可执行

  invoke:
    调用 harness.invoke_action
    捕获 action result / exception

  finalize:
    调用 harness.after_action
    捕获 after evidence
    生成 StepResult
    广播 runner events

  pytest 每个 phase 都会生成 CallInfo，再转成 TestReport。FSQ 也应该类似：

  StepCallInfo
    -> StepPhaseReport
    -> StepResult
    -> EvidenceBundle

  核心思想是：异常不要直接散落抛出，先被包装成结构化 call info。

  FSQ 的 runner 不应该只输出一个最终结果，而应该记录每个 phase 的事实：

  prepare passed / failed
  invoke passed / failed
  finalize passed / failed
  duration
  exception
  failure_category
  evidence_refs

  这对 UI 测试很重要，因为：

  prepare 失败 = 可能设备不可用、上下文获取失败
  invoke 失败 = 可能动作失败、目标不存在、超时
  finalize 失败 = 可能证据捕获失败、页面稳定等待失败

  这三类错误不应该混在一起。

  2. HarnessInterface 参考 pytest fixture

  pytest 的 fixture 系统给 test item 提供上下文和依赖。FSQ 的 Harness 也类似 fixture，但更重：

  pytest fixture:
    db
    tmp_path
    browser

  FSQ harness:
    device
    screen context
    action space
    screenshot
    UI tree
    platform lifecycle

  所以 HarnessInterface 的定位可以是：

  一个平台 fixture + driver + observation provider

  它不应该控制 runner，也不应该写 report。

  它应该回答三个问题：

  当前平台能做什么？
  当前平台现在是什么状态？
  请执行这个动作，结果是什么？

  所以接口大方向是：

  get_context()
  action_space()
  invoke_action()
  capture_artifact()
  before_action()
  after_action()
  classify_error()

  其中 get_context() 类似 pytest fixture resolution：

  Runner 需要 context
  Harness 提供 context
  Runner 把 context 传给 step invocation

  注意一个边界：Harness plugin 可以不同，但 HarnessInterface contract 必须稳定。

  AndroidHarness
  WebHarness
  IOSHarness
  FakeHarness

  这些都应该只是实现同一个 contract。

  3. EvidenceBundle 参考 pytest reports + junitxml

  pytest 的 report 不是 runner 状态本身。runner 执行后通过：

  pytest_runtest_makereport
  pytest_runtest_logreport

  把执行事实交给报告系统、terminal、junitxml、插件。

  FSQ 也应该这样设计：

  StepRunner emits RunnerEvent / StepPhaseReport
  EvidenceRecorder consumes them
  EvidenceBundleWriter writes manifest/artifacts
  ReportGenerator reads EvidenceBundle
  Verifier reads EvidenceBundle

  所以 EvidenceBundle 不应该嵌在 Runner 内部变成一堆字段。

  推荐大方向：

  Runner 内部有 operational state
  EvidenceBundle 保存 historical facts

  区别是：

  Runner state:
    当前跑到第几步
    当前 step 是 running 还是 failed
    是否需要 cancel remaining steps
    是否 retry

  Evidence facts:
    step X started
    prepare phase captured screenshot A
    invoke called tap with params P
    harness returned result R
    finalize captured UI tree B
    step X failed with category element_not_found

  这就是 pytest 给我们的启发：执行状态和报告事实分离。

  推荐架构

  ExecutionSession
    owns run-level metadata

  StepRunner
    owns execution protocol and state machine
    emits RunnerEvent
    calls HarnessInterface
    sends phase reports to EvidenceRecorder

  HarnessInterface
    platform plugin contract
    provides context, actions, artifacts, errors

  EvidenceRecorder
    event sink
    writes EvidenceBundle manifest
    stores artifact refs

  EvidenceBundle
    stable historical record
    consumed by Verifier / Report / Debug

  FSQ Step Protocol

  参考 pytest setup/call/teardown，FSQ 的每个 ExecutableStep 可以走：

  step_start
    -> prepare
        get_context
        before_action
        capture_before_evidence
    -> invoke
        harness.invoke_action
        capture action result / error
    -> finalize
        after_action
        capture_after_evidence
        classify final outcome
    -> step_report
    -> step_finish

  图上是：

  ExecutableStep
    -> prepare phase
    -> invoke phase
    -> finalize phase
    -> StepResult
    -> EvidenceBundle

  这三个模块的清晰边界

  StepRunner
    should know:
      ExecutableStep
      HarnessInterface
      EvidenceRecorder
      RetryPolicy
      FailureCategory

    should not know:
      Android implementation
      Playwright implementation
      report markdown format
      verifier prompt

  HarnessInterface
    should know:
      platform API
      platform artifacts
      platform error mapping
      action execution

    should not know:
      runner scheduling
      case pass/fail
      report layout
      planner repair policy

  EvidenceRecorder / EvidenceBundle
    should know:
      runner events
      phase reports
      artifact refs
      manifest schema

    should not know:
      how to execute action
      how to retry
      how to choose next step

  插件机制参考 pytest hooks

  pytest 最大的设计优点之一是 hooks。FSQ 不需要完整 pluggy 复杂度，但应该保留 hook 思想。

  建议第一版定义有限 hooks：

  on_session_start
  on_step_start
  on_phase_start
  on_phase_finish
  on_harness_call
  on_artifact
  on_step_finish
  on_step_error
  on_session_finish

  EvidenceRecorder 就是一个默认 hook consumer。

  未来这些也能接：

  terminal progress
  debug timeline
  json report
  Control Plane live timeline
  CI reporter

  这比让 Runner 直接 import 所有模块干净得多。

  团队分工建议

  针对这三个模块，可以这样分：

  Senior A: StepRunner Protocol
    - ExecutionSession
    - StepRunner
    - phase protocol
    - StepCallInfo / StepPhaseReport
    - cancellation / retry rules

  Senior B: HarnessInterface
    - Harness contract
    - FakeHarness
    - AndroidHarness spike
    - platform error mapping

  Engineer C: Evidence System
    - EvidenceRecorder
    - EvidenceBundle manifest
    - artifact refs
    - event sink

  Engineer D: Integration slice
    - one tap step through FakeHarness
    - one failure step through FakeHarness
    - report/verifier input from EvidenceBundle

  如果只有两个资深工程师：

  Senior A owns runner protocol.
  Senior B owns harness contract.
  Evidence schema is jointly reviewed by both.

  我建议的设计方向

  不要设计成：

  StepRunner contains EvidenceBundle and calls Android directly

  应该设计成：

  StepRunner
    -> calls HarnessInterface
    -> emits RunnerEvents
    -> EvidenceRecorder builds EvidenceBundle

  这是最接近 pytest 精髓的方式。

  Future consideration: 进一步靠近 xUnit/pytest 的异常语义

  当前 StepSequenceRunner 已经按 xUnit 风格处理 normal body 和 teardown：normal step 失败会停止后续业务步骤，但 teardown steps 必须执行。后续还需要评估是否把 Harness 层的失败表达从“返回 failed result”逐步升级为 typed exception。

  目标方向：

  - HarnessInterface.invoke_action 遇到目标找不到、断言失败、配置错误、超时等测试失败时，可以 raise typed HarnessActionError。
  - StepRunner 作为异常边界，捕获 HarnessActionError，并转换成 HarnessActionResult、StepPhaseReport、RunnerStepResult。
  - EvidenceBundle 和 report 继续消费结构化结果，不直接依赖 Python exception object。
  - teardown/finalize 仍然必须在异常路径上执行。
  - CLI 不应因为 testcase 失败直接 abort；失败 case 仍然要产出 evidence-manifest 和 core-report。

  推荐分批：

  1. 在 models 中定义 HarnessActionError 或等价 typed action exception，StepRunner 先兼容捕获它，同时继续支持现有 HarnessActionResult 返回值。
  2. AndroidHarness 把 driver failed result 转换为 HarnessActionError，让 Harness 层更接近 xUnit 的“失败即异常”语义。
  3. 最后再评估 AndroidDriverInterface 是否也改成异常式 API。这个影响用户自定义 driver，暂时不急。

  暂不做的事情：

  - 不让 typed exception 穿透到 CLI。
  - 不用异常替代 EvidenceBundle 中的结构化 failure_category/error_message。
  - 不因为 normal step 失败继续执行所有后续业务步骤。
