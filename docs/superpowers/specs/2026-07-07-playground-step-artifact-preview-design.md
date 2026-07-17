# Playground Step Artifact Preview Design

## Goal

Let the playground Preview pane show the artifacts produced by a clicked YAML step card. The display should show whatever exists for that step: screenshots, UI trees, page snapshots, UI snapshots, or a clear no-artifacts state. Screenshot artifacts should be visually useful for debugging, including a before-to-after comparison when both before and after screenshots exist.

## Scope

- Add a step-artifact preview flow between the left-side Input YAML step cards and the right-side Preview pane.
- Add a case-level preview flow from the YAML case name/title card to the right-side replay video preview.
- Support Strict YAML runs with precise step mapping through runner/evidence step ids.
- Support dynamic raw-YAML runs on a best-effort basis when progress events expose runner step metadata or action/tool names.
- Show screenshots in the Preview pane for the clicked step.
- Show a before -> after screenshot comparison when a step has both before and after screenshot artifacts.
- Show any UI tree, page snapshot, or UI snapshot artifacts below the screenshot area.
- Keep the feature read-only and run-local.
- Preserve the existing live screenshot, replay-video, Progress, and Report behavior during execution. Step artifact preview is only entered after a run completes and the user clicks a YAML step card.
- After a run completes, let clicking the YAML case name/title card show the recorded replay video for the completed run when available.
- Update playground SPEC and tests during implementation.

## Non-Goals

- Do not add artifact editing, saving, deleting, annotating, diffing, or regeneration.
- Do not change runner evidence capture policy.
- Do not change CLI behavior or strict execution semantics.
- Do not parse dynamic raw YAML into strict executable steps to make matching exact.
- Do not introduce a database or durable index outside existing run output artifacts.
- Do not show raw full-run artifacts unrelated to the clicked step.

## Proposed UI Design

The existing right-side Preview tab gains a step-artifact preview mode. The Preview tab still owns the current live screenshot and replay-video behavior while a run is executing. Step-artifact preview temporarily replaces the visible Preview contents only after execution completes and the user clicks a YAML step card.

When a YAML step card is clicked after a run completes:

1. The clicked step card keeps the selected styling already used by the YAML section.
2. The browser switches the right-side panel to the Preview tab.
3. The Preview pane loads artifacts for that step.
4. The Preview pane renders whichever artifacts exist.

When a YAML step card is clicked while a run is still executing, the YAML card selection behavior may still apply, but the Preview pane must remain on its existing live execution display and must not request or render step artifacts yet.

When the YAML case name/title card is clicked after a run completes:

1. The case title card keeps the selected styling already used by the YAML section.
2. The browser switches the right-side panel to the Preview tab.
3. The Preview pane shows the recorded replay video for the completed run when one is available.
4. If the replay video is not available yet but replay frames exist, the existing replay-video generation/loading behavior may be used.
5. If neither replay video nor replay frames are available, show a concise no-video state.

When the YAML case name/title card is clicked while a run is still executing, the Preview pane must remain on its existing live execution display and must not replace live preview content with replay video.

Screenshot display rules:

- If the step has both before and after screenshots, show them as a side-by-side before -> after comparison with stable labels.
- If only one screenshot exists, show it as a single screenshot preview with its phase label when available.
- If more than two screenshots exist, show the most useful pair first: prefer before and after; otherwise show the earliest and latest screenshots. Additional screenshots may appear as a compact strip/list below the primary image row.
- If a failure screenshot exists, include it in the screenshot list and label it as failure.
- Screenshots should use stable responsive sizing and must not overlap text or other preview content.

Structured artifact display rules:

- UI tree, page snapshot, and UI snapshot artifacts are shown below the screenshot area.
- Each structured artifact is displayed in a compact read-only panel with a label, phase, and monospaced content.
- If multiple structured artifacts exist, show one panel per artifact ordered by phase/timestamp.
- Long structured content should scroll inside its own bounded area rather than stretching the whole page.
- If there are screenshots and structured artifacts, screenshots stay visually first and structured artifacts follow below.
- If there are no screenshots but structured artifacts exist, the structured artifact area becomes the primary preview content.

Empty and loading states:

- While artifacts are loading, show a concise loading state in the Preview pane.
- If the selected step has no artifacts yet, show a no-artifacts state tied to that step.
- If artifact lookup fails, show a concise error in the Preview pane without changing run status.
- Do not render empty screenshot or UI-tree placeholders for artifact kinds that do not exist.

Execution-progress interaction:

- Strict YAML step progress should continue to highlight the matching YAML step card and scroll it toward the vertical center of the YAML viewer when needed.
- During execution, active-step highlighting and YAML viewer scrolling must not change the right-side Preview content.
- During execution, clicking a step card must not call the step-artifacts endpoint and must not replace live screenshot/replay Preview content.
- During execution, clicking the case name/title card must not replace live Preview content with replay video.
- After execution completes, clicking a step card loads that step's artifacts and switches the right-side panel to Preview.
- After execution completes, clicking the case name/title card switches the right-side panel to Preview and displays the run replay video when available.
- Once a completed-run step artifact preview is selected, clicking another step card switches the Preview pane to that step's artifacts.
- Once a completed-run step artifact preview is selected, clicking the case name/title card exits step artifact preview and returns the Preview pane to the run replay video.
- Clear or a new execution resets step artifact preview state and returns Preview to the existing default execution behavior.

## HTTP API Design

Add one read-only endpoint:

### `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}`

Resolves artifacts for one step in a run.

Resolution rules:

- Resolve `{request_or_run_id}` through playground state when it is a request id; otherwise treat it as a run id.
- Read only under `settings.output.runs_dir / run_id`.
- Accept either a strict step id such as `strict_case-step-002` or a 1-based step index such as `2`.
- For Strict YAML runs, prefer `evidence-manifest.json` and filter artifacts by `artifact.step_id`.
- For dynamic runs, inspect `events.jsonl` for `payload.runner_step_id`, `payload.runner_result.step_id`, and `payload.artifact_refs`, then best-effort match by step id/index when available.
- Paths returned in manifest/event artifacts must resolve under the run directory.
- Screenshot artifacts are returned as base64 image content.
- Text artifacts such as `ui_tree`, `page_snapshot`, and `ui_snapshot` are returned as UTF-8 text content with a conservative size limit.

Successful response shape:

```json
{
  "available": true,
  "runId": "strict_case",
  "stepId": "strict_case-step-002",
  "stepIndex": 2,
  "artifacts": [
    {
      "kind": "screenshot",
      "phase": "before",
      "path": "screenshots/strict_case-step-002-before.png",
      "mimeType": "image/png",
      "contentBase64": "..."
    },
    {
      "kind": "screenshot",
      "phase": "after",
      "path": "screenshots/strict_case-step-002-after.png",
      "mimeType": "image/png",
      "contentBase64": "..."
    },
    {
      "kind": "ui_tree",
      "phase": "after",
      "path": "ui-trees/strict_case-step-002-after.xml",
      "mimeType": "application/xml",
      "content": "<hierarchy>...</hierarchy>"
    }
  ]
}
```

No-artifacts response shape:

```json
{
  "available": false,
  "runId": "strict_case",
  "stepId": "strict_case-step-002",
  "stepIndex": 2,
  "artifacts": [],
  "message": "No artifacts for this step yet."
}
```

Error response shape:

```json
{
  "available": false,
  "error": "Run not found: strict_case"
}
```

## Data And Control Flow

1. User loads an Input YAML file in the YAML section.
2. Browser renders step cards with `data-yaml-step-index`, action metadata, and any known step id metadata.
3. User starts execution.
4. Progress events identify the active step when possible.
5. Browser highlights and centers the active YAML step card.
6. Browser leaves the right-side Preview pane on the existing live execution display while the run is active.
7. Execution completes.
8. User clicks the YAML case name/title card, and the browser shows the completed run's replay video in Preview when available.
9. User clicks a YAML step card.
10. Browser records that step as the user-selected step preview and switches to Preview.
11. Browser calls `GET /step-artifacts/{request_or_run_id}/{step_id_or_index}`.
12. Browser renders screenshots first and structured artifacts below.
13. User may click the case name/title card again to leave step artifact preview and show the run replay video.
14. Clear or new execution resets the selected step artifact preview and returns Preview to the existing default behavior.

## Module Ownership And Architecture

Architecture level: Level 3 Layered Application.

Rationale: the feature coordinates static UI, HTTP routes, playground state, run-local artifacts, evidence manifests, and live execution progress. This remains an entry-layer playground concern and does not justify a new package or lower-level dependency.

Affected module boundaries:

- `fsq_agent.playground._server`: owns the new read-only step-artifact endpoint, safe run-directory resolution, artifact filtering, file reading, base64/text content shaping, and structured error responses.
- `fsq_agent.playground._execution`: may continue emitting strict step progress metadata needed by the browser to identify active steps.
- `fsq_agent.playground.static`: owns step-card click handling, Preview pane step-artifact mode, before -> after screenshot layout, structured artifact rendering, loading/error/empty states, and refresh behavior.
- `fsq_agent.playground.static`: owns case name/title card click handling that exits step artifact preview and shows the completed run replay video when available.
- `fsq_agent.playground.SPEC.md`: documents the endpoint and UI behavior before implementation.
- `tests/test_playground.py`: covers endpoint behavior and static UI contracts.

Dependency direction remains unchanged. `playground` may consume existing models and run artifacts; lower-level modules must not import `playground`.

## Error Handling And Edge Cases

- Unknown request id or run id returns a structured not-found response.
- Unknown step id/index returns a no-artifacts or not-found response without failing the run.
- Artifact paths escaping the run directory are ignored or rejected.
- Missing artifact files are skipped with safe metadata omitted from display.
- Non-UTF-8 text artifacts return a concise read error for that artifact or omit content with an artifact-level error.
- Very large text artifacts are truncated or rejected according to a conservative display limit.
- Binary non-image artifacts are listed only when safely identifiable; unsupported binary content is not rendered inline.
- A step with only a UI tree and no screenshot still renders the UI tree in Preview.
- A step with only screenshots renders screenshots and no empty UI-tree region.
- A step with before and failure screenshots but no after screenshot shows available screenshots in phase order.
- Dynamic raw-YAML runs may fail to map a clicked authored YAML step to runtime artifacts; the UI should show a clear no-artifacts state rather than implying execution failed.
- A completed run may have no replay video or replay frames; clicking the case name/title card should show a clear no-video state instead of failing the run.

## Verification Expectations

- Unit tests for `GET /step-artifacts/{id}/{step}` success with before/after screenshots and UI tree content from `evidence-manifest.json`.
- Unit tests for no-artifacts, missing run id, path safety, missing files, and text size-limit behavior.
- Static UI tests confirming:
  - Clicking the YAML case name/title card after completion shows the run replay video preview when available.
  - Clicking the YAML case name/title card during execution does not replace live Preview content.
  - Clicking the YAML case name/title card exits step artifact preview and returns to run replay video.
  - YAML step cards request step artifacts when clicked.
  - Step artifact preview switches the right-side pane to Preview.
  - Screenshots render before -> after when both phases exist.
  - UI tree/page snapshot/UI snapshot content renders below screenshots.
  - Missing artifact kinds do not render empty placeholder regions.
  - Clear/new execution resets step artifact preview state.
  - Running execution does not request step artifacts or replace live Preview content when step cards are highlighted or clicked.
- Run `python -m pytest tests/test_playground.py`.
- Run editor diagnostics for changed playground files and tests.
- Run independent SPEC implementation audit after implementation.

## Open Questions Resolved

- The Preview pane should show whatever artifact kinds exist for the clicked step.
- Two screenshots should display as a before -> after comparison.
- UI-tree and related structured artifacts should render below the screenshot area.
- Missing artifact kinds should not reserve empty UI space.
- Running Preview behavior should remain unchanged; step artifact preview appears only after execution completes and the user clicks a step card.
- Clicking the YAML case name/title card after execution completes should show the recorded replay video for the run.
- Clicking the YAML case name/title card during execution should not replace live Preview content.