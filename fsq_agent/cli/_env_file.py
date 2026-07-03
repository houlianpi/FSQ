from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnvFileUpdate:
    path: Path
    keys: tuple[str, ...]


def read_env_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OSError(f"Unable to read .env file: {path}") from exc
    values: dict[str, str] = {}
    for raw_line in lines:
        key, value = _split_assignment(raw_line)
        if key is not None:
            values[key] = _strip_env_value(value)
    return values


def upsert_env_values(path: Path, values: dict[str, str]) -> EnvFileUpdate:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    output: list[str] = []
    written: set[str] = set()

    for raw_line in lines:
        key, _value = _split_assignment(raw_line)
        if key in values:
            if key not in written:
                output.append(f"{key}={values[key]}")
                written.add(key)
            continue
        output.append(raw_line)

    for key, value in values.items():
        if key not in written:
            output.append(f"{key}={value}")
            written.add(key)

    path.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")
    return EnvFileUpdate(path=path, keys=tuple(values))


def _split_assignment(raw_line: str) -> tuple[str | None, str]:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
        return None, ""
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None, ""
    key, value = stripped.split("=", 1)
    key = key.strip()
    return (key or None), value.strip()


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value