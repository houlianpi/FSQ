# Module: skills

## Purpose

Load configured automation skills from local Markdown files, directories, or inline descriptive bundles. Provide only complete skill instructions and file metadata to the OpenAI Agents SDK runtime without coupling skill loading to private knowledge storage or granting command execution authority.

## Dependencies

- `models`: Uses `SkillConfig`, `SkillBundle`, and shared exception types when required skill files are missing or invalid.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `SkillLoader`: Loads configured automation skills from Markdown files, directories, or inline descriptive bundles. Required broken skills fail fast; optional broken skills are skipped with operator-visible diagnostics and are not returned as model-facing bundles.
- `SkillBundle`: Re-exported shared model from `models` for callers that work through the skills module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Skill discovery, Markdown rendering, and inline bundle loading.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing required skill files raise `FsqAgentError` subclasses from `models` with the failing path and skill name. Optional skill entries with missing paths, missing files, unreadable files, invalid directories, or no inline content are skipped and logged as diagnostics. Skipped optional skills must not be returned as warning-only `SkillBundle` values or sent to LLM prompts. Inline skill bundles are accepted as descriptive instructions and do not imply shell execution authority.

## Platform Skill Blocks

Shared skill guidance belongs in `automation-basics.md`.

Android runs should configure `android-harness.md` alongside shared automation guidance. The Android harness skill describes Android action selection, locators, assertions, UI-tree usage, waits, and recovery.

Web runs should configure `web-harness.md` alongside shared automation guidance. The Web harness skill should mirror Playwright's LLM-facing guidance: start browser-owned workflows with `start_browser`, close them with `close_browser`, prefer `page_snapshot` over screenshots for target selection, use replayable semantic locators or stable selectors, use `navigate_to`, `navigate_back`, `click_on`, `type_text`, `select_option`, `hover_on`, `press_key`, `wait_for`, `take_screenshot`, assertion tools, and `assert_with_ai` according to active schemas, avoid `Alt+F4`/`Control+W` as browser lifecycle controls, and reserve unsupported Playwright MCP capability families for future SPEC-reviewed opt-in tools.

macOS runs should configure `macos-harness.md` alongside shared automation guidance. The macOS harness skill should describe desktop aliases, stable accessibility locators, explicit coordinate fallback, Appium Mac2 lifecycle expectations, `ui_snapshot` usage, deterministic assertions such as `assert_visible` and `assert_elements_order`, visual assertions through `assert_with_ai`, and credential text entry through `textType: runtimeSecret` when supported by active schemas.

Future platform skills must be separate platform-specific Markdown bundles instead of expanding existing platform skill files with unrelated platform rules.

## Design Decisions

- Skills are advisory context, not executable authority.
- Local Markdown skills are rendered into instructions/context only when successfully loaded.
- Platform-specific skills should describe scope, AgentTool/CommonTool/PlatformTool selection, argument rules, tool usage error recovery, semantic fidelity rules, and evidence rules. They guide the generic agent for the configured runtime without turning the agent runtime into a platform-specific implementation.
- Skills do not attach command execution tools. Any future command capability requires its own SPEC update outside the skills module.
- Skill models remain centralized in `models` so runtime, tools, and configuration share the same serializable contracts.
- Skill loader diagnostics are operational metadata for logs or runtime events, not prompt content. The LLM should see complete skill instructions or no skill block.
