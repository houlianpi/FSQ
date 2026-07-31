# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest

from fsq_agent import models
from fsq_agent.models import (
    AgentFinalOutput,
    AgentTaskInput,
    ExecutionStep,
    GoalPrePlan,
    HarnessSettings,
    LocalToolOutputSettings,
    OpenAIAgentsSettings,
    PageKnowledgeIndex,
    PageKnowledgePage,
    SkillConfig,
    Task,
)


def test_task_defaults() -> None:
    task = Task(description="Do a thing")

    assert task.id == "task"
    assert task.name == "Task"
    assert task.acceptance_criteria == []
    assert task.planning_reference_kind is None
    assert task.planning_reference_text is None
    assert task.key_actions == []
    assert task.verification_goal is None
    assert task.timeout_seconds == 300
    assert task.max_retries == 3
    assert task.knowledge_refs == []


def test_execution_step_requires_positive_id() -> None:
    step = ExecutionStep(
        step_id=1,
        action="write",
        tool="file.write",
        tool_input={"path": "out.txt", "content": "ok"},
        expected_outcome="file written",
    )

    assert step.step_id == 1


def test_agent_final_output_defaults_schema_version() -> None:
    output = AgentFinalOutput(status="success", summary="Done")

    assert output.schema_version == "task_run_v1"
    assert output.pre_plan == []


def test_agent_task_input_wraps_task_contract() -> None:
    task = Task(
        id="task-1",
        description="Do a thing",
        key_actions=["Key action 1: tap button"],
        verification_goal="Verify that doing the thing is complete.",
    )
    task_input = AgentTaskInput(
        task=task,
        acceptance_criteria=task.acceptance_criteria,
        key_actions=task.key_actions,
        verification_goal=task.verification_goal,
        acceptance_policy="Use provided criteria.",
    )

    assert task_input.schema_version == "task_input_v1"
    assert task_input.output_contract == "task_run_v1"
    assert task_input.task.id == "task-1"
    assert task_input.key_actions == ["Key action 1: tap button"]
    assert task_input.verification_goal == "Verify that doing the thing is complete."


def test_openai_agents_settings_defaults_to_safe_offline_mode() -> None:
    settings = OpenAIAgentsSettings()

    assert settings.provider == "github_copilot"
    assert settings.model == "gpt-5.5"
    assert settings.api_key_env == "AZURE_OPENAI_API_KEY"
    assert settings.tracing_enabled is True
    assert not hasattr(settings.prompt, "custom_instructions")
    assert not hasattr(settings.prompt, "custom_instructions_path")
    assert settings.prompt.agent_template_path is None
    assert settings.prompt.task_template_path is None
    assert settings.prompt.variables == {}
    assert settings.context_trimming.enabled is True
    assert settings.context_trimming.max_tool_output_chars == 30000
    assert settings.local_tool_output.always_write_artifact is True
    assert settings.local_tool_output.full_output_max_chars == 30000


def test_harness_settings_default_to_android_uiautomator2() -> None:
    settings = HarnessSettings()

    assert settings.platform == "android"
    assert settings.android.backend == "uiautomator2"
    assert settings.android.app_id is None
    assert settings.android.serial is None


def test_skill_config_defaults_to_markdown() -> None:
    skill = SkillConfig(name="browser-testing", path="browser-testing.md")

    assert skill.kind == "markdown"
    assert skill.required is False


def test_models_public_surface_does_not_export_removed_tool_execution_settings() -> None:
    assert "ShellSettings" not in models.__all__
    assert "CLIToolConfig" not in models.__all__
    assert "DeprecatedToolSettings" not in models.__all__
    assert "VerificationCriterion" not in models.__all__
    assert "VerificationMode" not in models.__all__
    assert "VerificationSettings" not in models.__all__
    assert not hasattr(models, "ShellSettings")
    assert not hasattr(models, "CLIToolConfig")
    assert not hasattr(models, "DeprecatedToolSettings")
    assert not hasattr(models, "VerificationCriterion")
    assert not hasattr(models, "VerificationMode")
    assert not hasattr(models, "VerificationSettings")


def test_local_tool_output_rejects_artifact_subdir_escape() -> None:
    with pytest.raises(ValueError, match="artifact_subdir"):
        LocalToolOutputSettings(artifact_subdir="../outside")


def test_page_knowledge_page_uses_semantic_identifiers_and_reference_locators() -> None:
    page = PageKnowledgePage.model_validate(
        {
            "page_id": "edge_android_new_tab_page",
            "name": "New Tab Page",
            "identifiers": [{"name": "Account menu visible", "description": "Account entry is visible."}],
            "images": [{"path": "../assets/pages/ntp.png", "description": "Typical NTP."}],
            "elements": [
                {
                    "name": "Browser menu",
                    "role": "button",
                    "reference_locators": [
                        {
                            "strategy": "id",
                            "selector": "com.microsoft.emmx:id/overflow_button_bottom",
                            "confidence": "high",
                            "notes": "Observed in bottom toolbar mode.",
                        }
                    ],
                    "operations": [
                        {
                            "operation": "tap",
                            "result": {
                                "type": "navigate",
                                "to_page_id": "edge_android_overflow_menu",
                                "description": "Opens the overflow menu.",
                            },
                        }
                    ],
                }
            ],
        }
    )

    assert page.schema_version == "page_knowledge_page_v1"
    assert page.identifiers[0].model_dump() == {"name": "Account menu visible", "description": "Account entry is visible."}
    assert page.elements[0].reference_locators[0].confidence == "high"
    assert page.elements[0].operations[0].result.to_page_id == "edge_android_overflow_menu"


def test_page_knowledge_index_and_goal_pre_plan_defaults() -> None:
    index = PageKnowledgeIndex(
        product="Microsoft Edge",
        platform="Android",
        pages=[
            {
                "page_id": "edge_android_new_tab_page",
                "file": "pages/edge_android_new_tab_page.md",
                "name": "New Tab Page",
                "intents": ["new tab", "search"],
            }
        ],
    )
    plan = GoalPrePlan(
        goal="Open downloads",
        key_actions=[{"step_id": 1, "action": "Open browser menu", "source_page_ids": ["edge_android_new_tab_page"]}],
        verification_goal="Verify that Downloads can be opened from the browser menu.",
    )

    assert index.schema_version == "page_knowledge_index_v1"
    assert index.pages[0].page_id == "edge_android_new_tab_page"
    assert plan.schema_version == "goal_pre_plan_v1"
    assert plan.key_actions[0].step_id == 1
    assert plan.verification_goal == "Verify that Downloads can be opened from the browser menu."
