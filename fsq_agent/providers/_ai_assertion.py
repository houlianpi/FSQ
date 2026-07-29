# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any

from fsq_agent.models import AIAssertionRequest, AIAssertionResult, ConfigurationError
from fsq_agent.providers._session import ModelProviderSession


class AIAssertionEvaluator:
    def __init__(self, session: ModelProviderSession) -> None:
        self.session = session

    def evaluate(self, request: AIAssertionRequest) -> AIAssertionResult:
        started = time.perf_counter()
        try:
            response = self.session.invoke_responses_sync(input=self._build_input(request))
            payload = self._parse_response(response)
            passed = bool(payload.get("passed"))
            status = "passed" if passed else "failed"
            explanation = str(payload.get("explanation") or payload.get("summary") or "AI assertion evaluated.")
            confidence = payload.get("confidence")
            return AIAssertionResult(
                status=status,
                passed=passed,
                explanation=explanation,
                confidence=confidence if isinstance(confidence, int | float) else None,
                provider=self.session.provider,
                model=self.session.model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                token_usage=self._token_usage(response),
                artifact_refs=[request.screenshot_artifact_ref] if request.screenshot_artifact_ref else [],
                metadata={"provider_metadata": self.session.metadata},
            )
        except Exception as exc:
            if isinstance(exc, ConfigurationError):
                raise
            return AIAssertionResult(
                status="error",
                passed=False,
                explanation="AI assertion evaluation failed.",
                provider=self.session.provider,
                model=self.session.model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                artifact_refs=[request.screenshot_artifact_ref] if request.screenshot_artifact_ref else [],
                error=str(exc) or exc.__class__.__name__,
                metadata={"provider_metadata": self.session.metadata},
            )
        finally:
            self.session.close_sync()

    def close(self) -> None:
        self.session.close_sync()

    def _build_input(self, request: AIAssertionRequest) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Evaluate this explicit platform visual assertion. "
                    "Return JSON only with keys passed (boolean), explanation (short string), and confidence (0 to 1).\n\n"
                    f"Platform: {request.platform}\n"
                    f"Prompt: {request.prompt}\n"
                    f"Context: {json.dumps(request.ui_context, ensure_ascii=False, default=str)}"
                ),
            }
        ]
        screenshot_path = Path(request.screenshot_path) if request.screenshot_path else None
        if screenshot_path and screenshot_path.exists():
            mime_type = mimetypes.guess_type(str(screenshot_path))[0] or "image/png"
            data_url = f"data:{mime_type};base64,{base64.b64encode(screenshot_path.read_bytes()).decode('ascii')}"
            content.append({"type": "input_image", "image_url": data_url})
        return [{"role": "user", "content": content}]

    def _parse_response(self, response: Any) -> dict[str, Any]:
        text = self._response_text(response)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = self._json_object_from_text(text)
        if not isinstance(payload, dict):
            return {"passed": False, "explanation": text[:1000] or "AI assertion returned no parseable verdict."}
        return payload

    def _json_object_from_text(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {"passed": False, "explanation": text[:1000] or "AI assertion returned no parseable verdict."}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {"passed": False, "explanation": text[:1000] or "AI assertion returned no parseable verdict."}
        return payload if isinstance(payload, dict) else {"passed": False, "explanation": text[:1000]}

    def _response_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str):
            return output_text
        if isinstance(response, dict):
            value = response.get("output_text") or response.get("text")
            if isinstance(value, str):
                return value
        output = getattr(response, "output", None)
        if isinstance(output, list):
            pieces: list[str] = []
            for item in output:
                content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for part in content:
                    text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                    if isinstance(text, str):
                        pieces.append(text)
            if pieces:
                return "\n".join(pieces)
        return str(response)

    def _token_usage(self, response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if isinstance(response, dict):
            usage = response.get("usage", usage)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump(mode="json")
        if not isinstance(usage, dict):
            return {}
        return {str(key): int(value) for key, value in usage.items() if isinstance(value, int)}