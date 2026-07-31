# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

from fsq_agent.models import StepResult, VerificationResult

_TOOL_USAGE_MARKERS = (
    "invalid argument",
    "invalid parameter",
    "schema",
    "unsupported",
    "not supported",
    "only supported",
    "parameter is",
    "failed to perform actions",
    "tool usage issue",
    "conflicting key identities",
    "ambiguous",
)

_SEMANTIC_ACTION_MARKERS = (
    "presskey",
    "press key",
    "key action",
    "ordered key",
)

_PROVIDER_CONTENT_FILTER_MARKERS = (
    "provider_content_filter",
    "content_filter",
)

_PROVIDER_INCOMPLETE_MARKERS = (
    "provider_response_incomplete",
    "response.incomplete",
    "status=incomplete",
)


class FailureAnalyzer:
    def classify(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> str:
        if verification.status == "success":
            return "success"
        if self._has_provider_content_filter(steps, verification, tool_calls or []):
            return "provider_content_filter"
        if self._has_provider_response_incomplete(steps, verification, tool_calls or []):
            return "provider_response_incomplete"
        labels: list[str] = []
        if self._has_tool_usage_error(steps, verification, tool_calls or []):
            labels.append("tool_usage_error")
        if self._has_semantic_action_unmet(verification):
            labels.append("semantic_action_unmet")
        if labels:
            return " + ".join(labels)
        if any(step.status == "failed" and step.error for step in steps):
            return "execution issue"
        if verification.status == "inconclusive":
            return "verification issue"
        return "planning issue"

    def _has_tool_usage_error(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        texts = [self._normalize(step.error) for step in steps if step.status == "failed" and step.error]
        texts.extend(self._normalize(value) for value in verification.diagnostics)
        for call in tool_calls:
            texts.append(self._normalize(call.get("output_preview")))
            texts.append(self._normalize(call.get("error")))
        return any(any(marker in text for marker in _TOOL_USAGE_MARKERS) for text in texts)

    def _has_provider_content_filter(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        texts = self._failure_texts(steps, verification, tool_calls)
        return any(any(marker in text for marker in _PROVIDER_CONTENT_FILTER_MARKERS) for text in texts)

    def _has_provider_response_incomplete(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        texts = self._failure_texts(steps, verification, tool_calls)
        return any(any(marker in text for marker in _PROVIDER_INCOMPLETE_MARKERS) for text in texts)

    def _failure_texts(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]],
    ) -> list[str]:
        texts = []
        for step in steps:
            if step.status == "failed":
                texts.append(self._normalize(step.error))
                texts.append(self._normalize(step.actual_outcome))
                texts.append(self._normalize(step.tool_output))
        texts.append(self._normalize(verification.summary))
        texts.extend(self._normalize(value) for value in verification.diagnostics)
        texts.extend(self._normalize(value) for value in verification.unmet_criteria)
        for call in tool_calls:
            texts.append(self._normalize(call.get("output_preview")))
            texts.append(self._normalize(call.get("error")))
            texts.append(self._normalize(call.get("status")))
        return texts

    def _has_semantic_action_unmet(self, verification: VerificationResult) -> bool:
        texts = [self._normalize(value) for value in verification.unmet_criteria]
        texts.extend(self._normalize(value) for value in verification.diagnostics)
        texts.append(self._normalize(verification.summary))
        return any(any(marker in text for marker in _SEMANTIC_ACTION_MARKERS) for text in texts)

    def _normalize(self, value: Any) -> str:
        return str(value or "").lower()
