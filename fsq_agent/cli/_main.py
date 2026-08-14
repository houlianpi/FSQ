# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import asyncio
import json
from enum import IntEnum
from pathlib import Path

import click

from fsq_agent.application import (
    ApplicationError,
    ApplicationErrorCategory,
    ApplicationErrorCode,
    CaseCreateRequest,
    CaseTestRequest,
    WorkspaceRequest,
    configure_provider,
    create_case,
    event_record,
    initialize_workspace,
    list_environments,
    list_providers,
    list_runs,
    normalize_application_error,
    provider_status,
    read_run_logs,
    require_initialized_workspace,
    result_record,
    show_run,
    test_case,
)
from fsq_agent.cli._llm_setup import setup_llm_provider
from fsq_agent.control_plane import ControlPlaneServerOptions, run_control_plane

PLATFORMS = click.Choice(["android", "web", "windows", "macos"])
OUTPUTS = click.Choice(["human", "json", "jsonl"])


class ExitCode(IntEnum):
    SUCCESS = 0
    CASE_FAILED = 1
    USAGE = 2
    WORKSPACE = 3
    UNAVAILABLE = 4
    INTERNAL = 5
    INTERRUPTED = 130


class ProtocolGroup(click.Group):
    def main(self, args=None, prog_name=None, complete_var=None, standalone_mode=True, **extra):
        invocation_args = list(args) if args is not None else None
        try:
            result = super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                **extra,
            )
        except KeyboardInterrupt as exc:
            if standalone_mode:
                raise SystemExit(ExitCode.INTERRUPTED) from exc
            raise click.exceptions.Exit(ExitCode.INTERRUPTED) from exc
        except click.ClickException as exc:
            output = _requested_output(invocation_args)
            if output == "human":
                if standalone_mode:
                    exc.show()
                    raise SystemExit(exc.exit_code) from exc
                raise
            error = ApplicationError(
                code=ApplicationErrorCode.CASE_INVALID,
                category=ApplicationErrorCategory.REQUEST_VALIDATION,
                message=exc.format_message(),
                action="Run the command with --help and correct its arguments.",
            )
            click.echo(json.dumps(error.to_record(operation=_requested_operation(invocation_args)), ensure_ascii=False))
            if standalone_mode:
                raise SystemExit(ExitCode.USAGE) from exc
            raise click.exceptions.Exit(ExitCode.USAGE) from exc
        except ApplicationError as exc:
            return _top_level_error(
                exc,
                _requested_output(invocation_args),
                _requested_operation(invocation_args),
                standalone_mode,
            )
        except Exception as exc:  # noqa: BLE001 - outermost transport boundary.
            return _top_level_error(
                normalize_application_error(exc),
                _requested_output(invocation_args),
                _requested_operation(invocation_args),
                standalone_mode,
            )
        else:
            return _finish_invocation(result, standalone_mode)


def _requested_output(args: list[str] | None) -> str:
    values = args or []
    for index, value in enumerate(values):
        if value == "--output" and index + 1 < len(values):
            return values[index + 1]
        if value.startswith("--output="):
            return value.partition("=")[2]
    return "human"


def _requested_operation(args: list[str] | None) -> str:
    values = args or []
    positional: list[str] = []
    skip_next = False
    for value in values:
        if skip_next:
            skip_next = False
            continue
        if value == "--output":
            skip_next = True
            continue
        if value.startswith("-"):
            continue
        positional.append(value)
    if not positional:
        return "fsq"
    if positional[0] in {"case", "providers", "runs", "environments"} and len(positional) > 1:
        return ".".join(positional[:2])
    return positional[0]


def _finish_invocation(result: object, standalone_mode: bool) -> object:
    if standalone_mode and isinstance(result, int) and result != 0:
        raise SystemExit(result)
    return result


def _top_level_error(error: ApplicationError, output: str, operation: str, standalone_mode: bool) -> None:
    if output == "human":
        click.echo(f"Error: {error.message}", err=True)
        if error.action:
            click.echo(f"Action: {error.action}", err=True)
    else:
        click.echo(json.dumps(error.to_record(operation=operation), ensure_ascii=False, default=str))
    exit_code = _error_exit_code(error)
    if standalone_mode:
        raise SystemExit(exit_code) from error
    raise click.exceptions.Exit(exit_code) from error


@click.group(cls=ProtocolGroup)
@click.option("--output", "output_format", type=OUTPUTS, default="human", show_default=True)
@click.option("--non-interactive", is_flag=True, default=False)
@click.pass_context
def main(context: click.Context, output_format: str, non_interactive: bool) -> None:
    context.ensure_object(dict)
    context.obj.update(output=output_format, non_interactive=non_interactive)


@main.command()
@click.option("--platform", type=PLATFORMS, required=True)
@click.option("--provider", type=click.Choice(["github_copilot", "azure_openai"]), default=None)
@click.pass_context
def init(context: click.Context, platform: str, provider: str | None) -> None:
    if provider:
        setup_llm_provider(provider=provider)
    workspace = initialize_workspace(Path.cwd(), platform)
    if context.obj["output"] == "human":
        click.echo(f"Initialized FSQ Workspace: {workspace}")
    else:
        _emit_terminal(context, {"status": "success", "workspace": str(workspace)})


@main.command()
@click.pass_context
def doctor(context: click.Context) -> None:
    _workspace(context)
    _emit(context, {"status": "ready", "workspace": str(Path.cwd() / ".fsq-agent-workspace")})


@main.group(name="case")
def case_group() -> None:
    pass


@case_group.command(name="create")
@click.option("--platform", type=PLATFORMS, required=True)
@click.option("--goal", required=True)
@click.pass_context
def case_create(context: click.Context, platform: str, goal: str) -> None:
    events: list[dict[str, object]] = []

    def collect_event(event: object) -> None:
        events.append(event.model_dump(mode="json"))

    try:
        result = asyncio.run(
            create_case(
                CaseCreateRequest(current_directory=Path.cwd(), platform=platform, goal=goal),
                event_sink=collect_event,
            )
        )
        _emit_terminal(context, result.model_dump(mode="json"), events=events)
    except ApplicationError as exc:
        _application_error(context, exc)
    except KeyboardInterrupt as exc:
        raise click.exceptions.Exit(ExitCode.INTERRUPTED) from exc
    except Exception as exc:  # noqa: BLE001 - transport boundary normalization.
        _application_error(context, normalize_application_error(exc))
    if result.status != "success":
        raise click.exceptions.Exit(ExitCode.CASE_FAILED)


@case_group.command(name="test")
@click.argument("case_path", type=click.Path(path_type=Path))
@click.option("--platform", type=PLATFORMS, required=True)
@click.option("--suggest", is_flag=True, default=False)
@click.pass_context
def case_test(context: click.Context, case_path: Path, platform: str, suggest: bool) -> None:
    try:
        result = test_case(CaseTestRequest(current_directory=Path.cwd(), platform=platform, case_path=case_path, suggest=suggest))
        _emit_terminal(context, result.model_dump(mode="json"))
    except ApplicationError as exc:
        _application_error(context, exc)
    except KeyboardInterrupt as exc:
        raise click.exceptions.Exit(ExitCode.INTERRUPTED) from exc
    except Exception as exc:  # noqa: BLE001 - transport boundary normalization.
        _application_error(context, normalize_application_error(exc))
    if result.status != "success":
        raise click.exceptions.Exit(ExitCode.CASE_FAILED)


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", type=click.IntRange(1, 65535), default=8879)
@click.option("--open-browser/--no-open-browser", default=True)
def ui(host: str, port: int, open_browser: bool) -> None:
    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=Path.cwd()))
    run_control_plane(ControlPlaneServerOptions(host=host, port=port, open_browser=open_browser, workspace_path=workspace.workspace))


@main.group()
def providers() -> None:
    pass


@providers.command(name="list")
@click.pass_context
def providers_list(context: click.Context) -> None:
    _workspace(context)
    _emit(context, [item.model_dump(mode="json") for item in list_providers()])


@providers.command(name="configure")
@click.argument("name", type=click.Choice(["github_copilot", "azure_openai"]))
@click.pass_context
def providers_configure(context: click.Context, name: str) -> None:
    _workspace(context)
    if context.obj["non_interactive"]:
        raise click.UsageError("providers configure requires an interactive terminal")
    _emit(context, configure_provider(Path.cwd(), name).model_dump(mode="json"))


@providers.command(name="status")
@click.argument("name", required=False)
@click.pass_context
def providers_status(context: click.Context, name: str | None) -> None:
    _workspace(context)
    values = provider_status(name)
    _emit(context, [item.model_dump(mode="json") for item in values])


@main.group()
def runs() -> None:
    pass


def _runs_dir() -> Path:
    workspace = require_initialized_workspace(WorkspaceRequest(current_directory=Path.cwd()))
    return workspace.workspace / "output" / "runs"


@runs.command(name="list")
@click.pass_context
def runs_list(context: click.Context) -> None:
    _emit(context, [item.model_dump(mode="json") for item in list_runs(_runs_dir())])


@runs.command(name="show")
@click.argument("run_id")
@click.pass_context
def runs_show(context: click.Context, run_id: str) -> None:
    _emit(context, show_run(_runs_dir(), run_id))


@runs.command(name="logs")
@click.argument("run_id")
@click.pass_context
def runs_logs(context: click.Context, run_id: str) -> None:
    events = read_run_logs(_runs_dir(), run_id)
    _emit_terminal(context, {"run_id": run_id, "event_count": len(events)}, events=events)


@main.group()
def environments() -> None:
    pass


@environments.command(name="list")
@click.option("--platform", type=PLATFORMS, default=None)
@click.pass_context
def environments_list(context: click.Context, platform: str | None) -> None:
    _workspace(context)
    _emit(context, [item.model_dump(mode="json") for item in list_environments(Path.cwd(), platform)])


@environments.command(name="doctor")
@click.argument("name")
@click.pass_context
def environments_doctor(context: click.Context, name: str) -> None:
    _workspace(context)
    values = [item for item in list_environments(Path.cwd()) if item.name == name]
    _emit(context, [item.model_dump(mode="json") for item in values])


def _workspace(context: click.Context) -> None:
    try:
        require_initialized_workspace(WorkspaceRequest(current_directory=Path.cwd()))
    except ApplicationError as exc:
        _application_error(context, exc)


def _emit(context: click.Context, value: object) -> None:
    output = context.obj["output"]
    if output == "human":
        if isinstance(value, list):
            for item in value:
                click.echo(json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else item)
        else:
            click.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))
    else:
        status = value.get("status", "success") if isinstance(value, dict) else "success"
        warnings = value.get("warnings", []) if isinstance(value, dict) else []
        click.echo(
            json.dumps(
                result_record(value, operation=_context_operation(context), status=str(status), warnings=warnings),
                ensure_ascii=False,
                default=str,
            )
        )


def _emit_terminal(context: click.Context, value: object, *, events: list[dict[str, object]] | None = None) -> None:
    operation = _context_operation(context)
    status = value.get("status", "success") if isinstance(value, dict) else "success"
    warnings = value.get("warnings", []) if isinstance(value, dict) else []
    if context.obj["output"] == "jsonl":
        for event in events or []:
            click.echo(json.dumps(event_record(event, operation=operation), ensure_ascii=False, default=str))
        click.echo(
            json.dumps(
                result_record(value, operation=operation, status=str(status), warnings=warnings),
                ensure_ascii=False,
                default=str,
            )
        )
        return
    _emit(context, value)


def _application_error(context: click.Context, error: ApplicationError) -> None:
    if context.obj["output"] == "human":
        click.echo(f"Error: {error.message}", err=True)
        if error.action:
            click.echo(f"Action: {error.action}", err=True)
    else:
        click.echo(json.dumps(error.to_record(operation=_context_operation(context)), ensure_ascii=False, default=str))
    raise click.exceptions.Exit(_error_exit_code(error))


def _error_exit_code(error: ApplicationError) -> ExitCode:
    mapping = {
        "request_validation": ExitCode.USAGE,
        "workspace_configuration": ExitCode.WORKSPACE,
        "configuration": ExitCode.WORKSPACE,
        "unavailable": ExitCode.UNAVAILABLE,
        "internal": ExitCode.INTERNAL,
    }
    return mapping[error.category.value]


def _context_operation(context: click.Context) -> str:
    parts: list[str] = []
    current: click.Context | None = context
    while current is not None and current.parent is not None:
        parts.append(current.info_name or current.command.name or "unknown")
        current = current.parent
    return ".".join(reversed(parts)) or "fsq"
