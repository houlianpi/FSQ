from __future__ import annotations

from hashlib import sha256
from io import StringIO
import os
from pathlib import Path
import tempfile
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from fsq_agent.fsq import FsqCaseLoader
from fsq_agent.models import FsqCaseHook, FsqCaseHookAction


class YamlLifecycleConflictError(Exception):
    pass


class YamlLifecycleValidationError(Exception):
    pass


class YamlLifecycleWriteError(Exception):
    pass


def yaml_revision(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def lifecycle_display(metadata: dict[object, object]) -> dict[str, list[dict[str, object]]]:
    return {
        "onCaseStart": _display_hooks(metadata.get("onCaseStart")),
        "onCaseComplete": _display_hooks(metadata.get("onCaseComplete")),
    }


def save_lifecycle(
    path: Path,
    *,
    expected_revision: str,
    on_case_start: object,
    on_case_complete: object,
    size_limit_bytes: int,
) -> bytes:
    source = path.read_bytes()
    if len(source) > size_limit_bytes:
        raise YamlLifecycleValidationError(f"YAML file is too large to edit ({len(source)} bytes).")
    if yaml_revision(source) != expected_revision:
        raise YamlLifecycleConflictError("Case YAML changed on disk. Reload before saving.")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise YamlLifecycleValidationError("Case YAML must be UTF-8 text.") from exc

    start_hooks = _request_hooks(on_case_start)
    complete_hooks = _request_hooks(on_case_complete)
    yaml_rt = _round_trip_yaml()
    try:
        documents = list(yaml_rt.load_all(text))
    except Exception as exc:
        raise YamlLifecycleValidationError(str(exc) or "Unable to parse YAML for editing.") from exc
    if not documents or not isinstance(documents[0], CommentedMap):
        raise YamlLifecycleValidationError("FSQ metadata document must be a YAML mapping.")

    metadata = documents[0]
    _replace_lifecycle(metadata, "onCaseStart", start_hooks)
    _replace_lifecycle(metadata, "onCaseComplete", complete_hooks)
    try:
        output = StringIO()
        yaml_rt.explicit_start = text.lstrip("\ufeff \t\r\n").startswith("---")
        yaml_rt.dump_all(documents, output)
        saved_text = output.getvalue()
    except Exception as exc:
        raise YamlLifecycleValidationError(str(exc) or "Unable to serialize lifecycle hooks.") from exc
    if "\r\n" in text:
        saved_text = saved_text.replace("\n", "\r\n")
    saved = saved_text.encode("utf-8")
    if len(saved) > size_limit_bytes:
        raise YamlLifecycleValidationError(f"Resulting YAML is too large to edit ({len(saved)} bytes).")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(saved)
            handle.flush()
            os.fsync(handle.fileno())
        FsqCaseLoader().load_case(temporary_path)
        if yaml_revision(path.read_bytes()) != expected_revision:
            raise YamlLifecycleConflictError("Case YAML changed on disk. Reload before saving.")
        try:
            os.replace(temporary_path, path)
        except OSError as exc:
            raise YamlLifecycleWriteError(str(exc) or "Unable to replace case YAML.") from exc
        temporary_path = None
    except YamlLifecycleConflictError:
        raise
    except YamlLifecycleValidationError:
        raise
    except YamlLifecycleWriteError:
        raise
    except OSError as exc:
        raise YamlLifecycleWriteError(str(exc) or "Unable to write temporary case YAML.") from exc
    except Exception as exc:
        raise YamlLifecycleValidationError(str(exc) or "Unable to validate or save lifecycle hooks.") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return saved


def _round_trip_yaml() -> YAML:
    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.explicit_start = False
    yaml_rt.width = 4096
    return yaml_rt


def _display_hooks(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    entries = value if isinstance(value, list) else [value]
    hooks = [FsqCaseHook.model_validate(entry) for entry in entries]
    actions = [action for hook in hooks for action in hook.actions]
    return [
        {"index": index, "action": action.action_name, "value": action.value}
        for index, action in enumerate(actions, start=1)
    ]


def _request_hooks(value: object) -> list[FsqCaseHook]:
    if not isinstance(value, list):
        raise YamlLifecycleValidationError("Lifecycle hook fields must be lists.")
    hooks: list[FsqCaseHook] = []
    try:
        for action in value:
            if not isinstance(action, dict):
                raise YamlLifecycleValidationError("Lifecycle actions must be objects.")
            validated = FsqCaseHookAction.model_validate(
                {"action_name": action.get("action"), "value": action.get("value")}
            )
            hooks.append(FsqCaseHook(actions=[validated]))
    except YamlLifecycleValidationError:
        raise
    except Exception as exc:
        raise YamlLifecycleValidationError(str(exc) or "Invalid lifecycle hook data.") from exc
    return hooks


def _replace_lifecycle(metadata: CommentedMap, key: str, hooks: list[FsqCaseHook]) -> None:
    if not hooks:
        metadata.pop(key, None)
        return
    serialized = CommentedSeq()
    for hook in hooks:
        entry = CommentedMap()
        for action in hook.actions:
            entry[action.action_name] = action.value
        serialized.append(entry)
    if key in metadata:
        metadata[key] = serialized
        return
    if key == "onCaseStart" and "onCaseComplete" in metadata:
        metadata.insert(list(metadata).index("onCaseComplete"), key, serialized)
    else:
        metadata[key] = serialized