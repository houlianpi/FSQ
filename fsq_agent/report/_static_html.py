# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import html
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path


def generate_static_run_report(run_dir: Path, facts: Mapping[str, object]) -> Path:
    root = run_dir.resolve()
    if not root.is_dir():
        raise ValueError("Run directory is unavailable.")
    title = html.escape(str(facts.get("run_id", root.name)))
    payload = html.escape(json.dumps(_redact_tree(dict(facts)), ensure_ascii=False, indent=2, default=str))
    allowed = {".png", ".jpg", ".jpeg", ".txt", ".json", ".jsonl", ".md", ".yaml", ".yml"}
    artifacts = [
        f'<li><a href="{html.escape(path.name, quote=True)}">{html.escape(path.name)}</a></li>'
        for path in sorted(root.iterdir())
        if path.is_file() and not path.is_symlink() and path.suffix.casefold() in allowed
    ]
    report = _load_object(root, ("core-report.json", "report.json", "report-fallback.json"))
    manifest = _load_object(root, ("evidence-manifest.json",))
    events = _load_jsonl(root / "events.jsonl")
    steps = report.get("steps", []) if report else []
    timeline = _table(steps if isinstance(steps, list) else [], ("step_id", "status", "duration_ms", "error_message"))
    logs = _table(events, ("time", "level", "phase", "label", "status", "message"))
    evidence = manifest.get("artifacts", []) if manifest else []
    evidence_rows = evidence if isinstance(evidence, list) else []
    images = []
    snapshots = []
    for item in evidence_rows:
        if not isinstance(item, dict):
            continue
        relative = item.get("path")
        contained = _contained_file(root, relative)
        kind = str(item.get("kind", "")).casefold()
        if contained and contained.suffix.casefold() in {".png", ".jpg", ".jpeg"}:
            name = html.escape(str(relative), quote=True)
            images.append(f'<a href="{name}"><img src="{name}" alt="Run screenshot"></a>')
        elif contained and ("snapshot" in kind or contained.suffix.casefold() == ".txt"):
            snapshot = str(_redact(contained.read_text(encoding="utf-8", errors="replace")[:200000]))
            snapshots.append(f"<details><summary>{html.escape(str(relative))}</summary><pre>{html.escape(snapshot)}</pre></details>")
    suggestions = [name for name in ("case-suggestions.json", "candidate.fsq.yaml") if (root / name).is_file()]
    document = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FSQ Run {title}</title><style>body{{font:15px system-ui;margin:2rem;max-width:1100px;color:#242424}}h1{{font-size:1.7rem}}section{{border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f6f6;padding:1rem}}a{{color:#5146e5}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}}img{{max-width:240px;max-height:180px;margin:.4rem}}</style></head><body><h1>FSQ Run {title}</h1><section><h2>Overview, source, result, timing and runtime</h2><pre>{payload}</pre></section><section><h2>Step timeline</h2>{timeline}</section><section><h2>Screenshots</h2>{"".join(images) or "Unavailable"}</section><section><h2>UI snapshots</h2>{"".join(snapshots) or "Unavailable"}</section><section><h2>Structured logs</h2>{logs}</section><section><h2>Evidence</h2>{_table(evidence_rows, ("kind", "path", "step_id", "phase"))}</section><section><h2>Suggestions and candidate Case</h2><ul>{"".join(f'<li><a href="{html.escape(name, quote=True)}">{html.escape(name)}</a></li>' for name in suggestions) or "<li>Unavailable</li>"}</ul></section><section><h2>Allowlisted artifacts</h2><ul>{"".join(artifacts) or "<li>Unavailable</li>"}</ul></section></body></html>"""
    descriptor, temporary = tempfile.mkstemp(prefix=".report.", suffix=".tmp", dir=root)
    target = root / "report.html"
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(target)
    except Exception:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def _load_object(root: Path, names: tuple[str, ...]) -> dict[str, object]:
    for name in names:
        try:
            value = json.loads((root / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return {}


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    values = []
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            values.append(_safe_log_event(value))
    return values


def _safe_log_event(value: dict[str, object]) -> dict[str, object]:
    allowed = ("sequence", "time", "level", "phase", "tool", "label", "status", "message")
    return {key: _redact(value[key]) for key in allowed if key in value}


def _redact(value: object) -> object:
    if isinstance(value, str):
        value = re.sub(r"(?i)(authorization|cookie)\s*[:=]\s*[^\r\n]+", r"\1=[REDACTED]", value)
        return re.sub(r"(?i)(bearer|token|api[_-]?key|secret|password|passwd|pwd)\s*[:=]?\s*[^\s,;]+", r"\1=[REDACTED]", value)[:4000]
    if isinstance(value, int) or value is None:
        return value
    return str(value)[:4000]


def _redact_tree(value: object) -> object:
    secret_keys = ("token", "api_key", "apikey", "authorization", "cookie", "secret", "password", "passwd", "pwd")
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if any(part in str(key).casefold() for part in secret_keys) else _redact_tree(item)) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_redact_tree(item) for item in value]
    return _redact(value)


def _contained_file(root: Path, value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    candidate = (root / value).resolve()
    return candidate if candidate.is_relative_to(root) and candidate.is_file() and not candidate.is_symlink() else None


def _table(rows: list[object], columns: tuple[str, ...]) -> str:
    valid = [row for row in rows if isinstance(row, dict)]
    if not valid:
        return "Unavailable"
    head = "".join(f"<th>{html.escape(column.replace('_', ' ').title())}</th>" for column in columns)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(_redact(row.get(column, ''))))}</td>" for column in columns) + "</tr>" for row in valid)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


__all__ = ["generate_static_run_report"]
