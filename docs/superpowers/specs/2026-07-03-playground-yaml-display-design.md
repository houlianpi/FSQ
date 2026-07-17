# Playground YAML Display Design

## Goal

Improve the playground YAML experience by making YAML a first-class left-side workspace section above Session. The section should let a user enter a case YAML path before execution and inspect a styled, structured representation of the input case or generated recorded strict case. The primary UI must not be a raw YAML code viewer.

## Scope

- Add a left-side YAML section between the topbar and Session.
- Keep the YAML path input in the Run section for YAML and Strict YAML modes, while the YAML section displays the loaded Input and Recorded views.
- Show two YAML views in that section: Input and Recorded.
- Add read-only playground HTTP APIs for resolving YAML sources and returning a presentation model for input YAML and recorded YAML artifacts.
- Keep YAML display presentation-only: no editing, mutation, execution, regeneration, or dynamic raw-case strict parsing from the display endpoints.
- Update playground SPEC and tests during implementation.

## Non-Goals

- Do not build a full YAML editor.
- Do not add YAML save, download, formatting, diff, validation, default raw-code display, or inline diagnostics in this design cycle.
- Do not change CLI behavior or recording semantics.
- Do not mutate source case files or run artifacts from the playground UI.
- Do not parse dynamic raw YAML references into strict executable steps for display.

## Proposed UI Design

The left control panel order becomes:

1. Topbar
2. YAML
3. Session
4. Run

The left control panel and right preview panel should visually fill the page height together so the two-column shell has aligned panel edges. The default left width should be narrower than the original 36% layout, with a draggable vertical separator that persists the user's preferred width in browser local storage. Extra vertical space inside the left control panel should be assigned to the YAML display section instead of appearing as empty space below Run.

The Run section owns YAML path entry for YAML and Strict YAML modes. In those modes, path input and Run should be visually grouped in one input row. The YAML section owns YAML preview and recorded YAML display.

The YAML section contains a compact segmented control with two views:

The Input/Recorded tabs should use the same underline tab visual style as the right-side Preview/Progress/Report tabs rather than a segmented-control style.

- Input: shows the currently entered case YAML path and the resolved input file content.
- Recorded: shows the generated `recorded.codex.yaml` for the latest completed dynamic run when available.

Input view behavior:

- Enabled for YAML and Strict YAML modes.
- Input controls/content are hidden in Goal mode because there is no input YAML; Goal mode shows only the Recorded tab. YAML mode shows Input and Recorded tabs. Strict YAML mode shows only the Input tab because strict execution does not generate recorded YAML.
- Uses the path input currently represented by `#case-yaml` in the Run section.
- Loads the input YAML when the user presses Enter in the path field or leaves the path field after changing it.
- May auto-load when the path field loses focus if the path changed.
- Shows case metadata and a styled command/step list after successful load.
- After successful load, the YAML display should not show a separate source-path line above the case summary; the path remains in the Run section input. Loading, empty, and error states may still use concise status text.
- Input YAML validation and load errors should appear in the status text only and should not be duplicated inside the YAML viewer frame.
- Shows a concise error state when the path is missing, unreadable, too large, outside allowed resolution, or not a file.

Recorded view behavior:

- Cleared at the start of a new execution.
- For dynamic goal and dynamic raw YAML runs, reads the recording summary from the completed progress payload and resolves generated YAML from the completed run directory.
- If `recording.status` is `recorded` and `recorded_case_path` is present, displays generated case metadata and recorded commands as styled UI elements.
- If recording is skipped or failed, displays recording status, validation status, warnings, skipped tool calls, and errors from `recording.json` or the progress result summary.
- For Strict YAML runs, displays a stable empty state explaining that strict runs do not generate recorded cases.
- Automatically selects Recorded after a completed dynamic run when recorded YAML is available or recording produced an actionable status.

Shared YAML viewer behavior:

- Read-only presentation.
- Bounded height inside the left panel with internal scrolling.
- Metadata fields for platform, schema, tags, and source path when available. The source path should appear immediately below Description when Description exists. The case name is the section title and should not be repeated as a metadata row; platform/schema should not also appear as title-row badges when shown as fields.
- The case name should sit in a subtle tinted header area so it is visually distinct without becoming a hero block.
- Only the case name row should be sticky at the top of the YAML viewer; tags, metadata, and steps should scroll normally below it.
- Step rows with a step index, an action-name badge colored by inferred kind, optional non-kind status chips, and parameter key/value rows. Inferred kinds should not appear as separate prominent badges.
- Complex parameter values are summarized as nested object/list fields, not displayed as JSON blobs, object/list count filler such as `10 fields`, or as the full YAML document by default. Steps without parameters should not render `No parameters` rows.
- Copy button copies the underlying YAML text when content is available; raw text is copy-source data, not the primary visual UI.

## HTTP API Design

Add two read-only playground endpoints.

### `GET /yaml/input?path=...`

Resolves an input case YAML file and returns a styled-display presentation model.

Resolution rules:

- Use the same candidate order as execution: `settings.cases.dir / path`, then `Path.cwd() / path` for relative paths, and the absolute path directly for absolute paths.
- Return only files, not directories.
- Read UTF-8 text.
- Parse YAML documents for display only. This parsing must not create strict executable steps, normalize capabilities, execute actions, or mutate source files.
- Enforce a conservative display size limit to avoid locking the UI on very large files.

Successful response shape:

```json
{
  "kind": "input",
  "path": "original user path",
  "resolvedPath": "absolute resolved path",
  "sizeBytes": 1234,
  "display": {
    "metadata": {"name": "Sample", "platform": "android", "schemaVersion": "fsq.ai-test/v1"},
    "steps": [{"index": 1, "action": "launchApp", "params": []}]
  },
  "content": "schemaVersion: fsq.ai-test/v1\n..."
}
```

Error response shape:

```json
{
  "available": false,
  "error": "Case YAML not found: sample.codex.yaml"
}
```

### `GET /yaml/recorded/{request_or_run_id}`

Resolves generated recorded YAML for a completed dynamic run and returns recording metadata plus a styled-display presentation model when generated YAML exists.

Resolution rules:

- Resolve `{request_or_run_id}` through playground state when it is a request id; otherwise treat it as a run id.
- Read only under `settings.output.runs_dir / run_id`.
- Prefer `recording.json` for status metadata.
- Read `recorded.codex.yaml` only when present and inside the run directory.
- Parse generated YAML for display only. The raw YAML text may be returned for copy support but must not be the default rendered view.

Successful response shape when YAML exists:

```json
{
  "kind": "recorded",
  "runId": "run-id",
  "status": "recorded",
  "validationStatus": "passed",
  "draft": false,
  "commandCount": 4,
  "recordedCasePath": ".../recorded.codex.yaml",
  "warnings": [],
  "errors": [],
  "display": {
    "metadata": {"name": "Recorded case", "platform": "android", "schemaVersion": "fsq.ai-test/v1"},
    "steps": [{"index": 1, "action": "launchApp", "params": []}]
  },
  "content": "schemaVersion: fsq.ai-test/v1\n..."
}
```

Response shape when recording has no generated YAML:

```json
{
  "kind": "recorded",
  "runId": "run-id",
  "status": "skipped",
  "validationStatus": "not_run",
  "draft": true,
  "commandCount": 0,
  "warnings": ["No replayable commands found."],
  "errors": [],
  "content": null
}
```

## Data and Control Flow

1. User selects YAML or Strict YAML mode.
2. The browser shows the left-side YAML section and focuses the YAML path field when appropriate.
3. User enters a case path and requests preview.
4. Browser calls `GET /yaml/input?path=...` and renders the read-only styled Input view from the returned display model.
5. User starts execution. The existing `POST /execute` body continues to send `caseYamlPath` or `strictCaseYamlPath` from the YAML section path field.
6. Browser clears only Recorded state, keeps Input state, and begins progress streaming.
7. When execution completes, browser checks `progress.result.recording` and the run id.
8. Browser calls `GET /yaml/recorded/{run_id}` for dynamic runs when recording was attempted, then renders the styled Recorded view from the returned display model.
9. Browser does not call the recorded endpoint for strict runs except to show a stable no-recording state if needed.

## Module Ownership and Architecture

Architecture level: Level 3 Layered Application.

Rationale: `playground` already coordinates HTTP transport, static UI, runtime state, execution, reports, replay artifacts, and recording summaries. YAML display remains an entry-layer presentation and artifact-resolution concern inside the existing `playground` module. No new package or cross-module abstraction is justified.

Affected module boundaries:

- `fsq_agent.playground._server`: owns the new read-only HTTP route dispatch and safe path/artifact reading.
- `fsq_agent.playground._server`: owns display-only YAML parsing into a safe presentation model. It must not invoke strict executable-step conversion for this display feature.
- `fsq_agent.playground._execution`: may expose or reuse existing case path resolution logic through a private helper, keeping execution semantics unchanged.
- `fsq_agent.playground._state`: no required persistence changes; existing request id to run id lookup is enough for recorded YAML resolution.
- `fsq_agent.playground.static`: owns left-side YAML UI, segmented Input/Recorded state, copy behavior, and lightweight syntax highlighting.
- `fsq_agent.playground.SPEC.md`: must document new endpoints and UI behavior before implementation.
- `tests/test_playground.py`: should cover endpoint behavior and static UI contracts.

Dependency direction remains unchanged. `playground` may depend on `config`, `fsq`, `agent`, `core`, and `report` as already specified, but no lower-level module may depend on `playground`.

## Error Handling and Edge Cases

- Missing path: show a local or API error state without starting a run.
- Missing file: return structured 404-style JSON from the preview endpoint.
- Directory path: return structured error; do not list directory contents.
- Non-UTF-8 file: return structured read error.
- Very large YAML: return structured size-limit error for display; execution path remains unchanged unless existing execution validation rejects it.
- Recording skipped: show recording status and warnings instead of an empty code panel.
- Recording failed: show errors and validation status without changing run status.
- `recorded.codex.yaml` missing but `recording.json` present: show metadata and no-content state.
- Request id no longer maps to a run id: return structured not-found error.
- Strict run: do not imply a generated recorded YAML exists.
- Copy action with no content: keep disabled.

## Verification Expectations

- Unit tests for `GET /yaml/input` success, missing file, directory path, and size-limit behavior.
- Unit tests for `GET /yaml/recorded/{id}` with recorded content, skipped recording metadata, failed recording metadata, missing run id, and path safety.
- Static UI tests confirming:
  - YAML section appears above Session.
  - YAML path input appears under Run for YAML and Strict YAML modes.
  - Run uses the YAML section path for YAML and Strict YAML modes.
  - Input and Recorded segmented controls exist.
  - Copy control exists.
  - Styled metadata and step rows render from display models.
  - Recorded YAML is loaded after dynamic completion.
  - Strict runs show a no-recorded-YAML state.
- Run `python -m pytest tests/test_playground.py`.
- Run editor diagnostics for changed playground static files, `fsq_agent/playground/SPEC.md`, and `tests/test_playground.py`.

## Open Questions Resolved

- YAML should include both input YAML and generated recorded YAML.
- YAML should not be a right-side tab. It belongs in the left control panel above Session.
- The YAML path input should remain in Run while YAML preview/display stays above Session.
- YAML should be shown as styled structured UI, not as the raw original YAML document.
