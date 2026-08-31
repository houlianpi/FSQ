# FSQ v0.1.0 Demo Storyboard

## Deliverable

- Duration: 30–45 seconds.
- Canvas: 1920×1080 master; export a 1280px-wide MP4 and an optimized README GIF.
- Language: interface audio is optional; English captions are mandatory, Chinese captions are supplied separately.
- Source: release-candidate build, a public TodoMVC target, dedicated demo Workspace, and a Provider configuration with no visible secrets.

## Shot list

| Time | Picture | Caption | Proof shown |
|---|---|---|---|
| 00:00–00:04 | FSQ logo and workflow graphic | “AI UI automation should show its work.” | Project identity |
| 00:04–00:09 | Terminal or Control Plane: Workspace and readiness context | “Install once. Check real readiness.” | Current CLI and no dynamic installer |
| 00:09–00:16 | Control Plane Devices: enter the TodoMVC goal and start Explore | “Describe a user-visible goal.” | Real goal input and execution start |
| 00:16–00:24 | Timeline plus Before/After and UI Tree evidence | “Every action leaves inspectable evidence.” | Real persisted evidence |
| 00:24–00:30 | Terminal or Control Plane showing successful Run and candidate Case | “Review what actually ran.” | Run-local outcome and Case |
| 00:30–00:37 | Strict Replay of the reviewed public Case | “Replay deterministically.” | No planning LLM in strict flow |
| 00:37–00:43 | Offline HTML report followed by four-platform lockup | “Web · Android · Windows · macOS” | Report and platform scope |

## Recording setup

1. Install the final wheel into a clean environment; do not record from an editable checkout.
2. Set the OS account name, host name, browser profile, bookmarks, notifications, clock, and terminal prompt to neutral demo values.
3. Use a new Workspace named `fsq-web-demo` under a neutral path. Clear unrelated Workspaces and Runs from the UI.
4. Use a public no-account demo target only. Do not open email, chat, internal portals, private repositories, or account pages.
5. Set browser zoom to 100%, Control Plane zoom to 100%, and terminal font large enough for 1280px export.
6. Disable notifications, password managers, autofill, and clipboard-history overlays.
7. Record one continuous master; derive all clips and stills from the same approved take.

## Capture checkpoints

- `01-describe-goal.png`: Control Plane goal entry with neutral, real state.
- `02-execute-workflow.png`: active execution timeline without codes, tokens, paths, or device identifiers.
- `03-capture-evidence.png`: real Before/After or UI Tree evidence from the public demo target.
- `04-generate-candidate.png`: Run-local candidate Case generated from persisted execution facts.
- `05-inspect-run.png`: offline HTML report with redacted neutral metadata.

The final repository must not contain placeholder or synthetic product screenshots. If any checkpoint cannot be captured safely, omit it rather than staging false evidence.

## Export

- Master MP4: H.264, 1920×1080, 30 fps, high quality, no embedded private metadata.
- Web MP4: 1280×720, target under 12 MB.
- README GIF: 1280px wide, 12–15 fps, optimized palette, target under 8 MB; retain the MP4 link for readable detail and accessibility.
- Thumbnail: 1280×720 PNG, derived from a real approved frame.
- Strip audio unless narration has been approved and transcripted.

## Acceptance

Watch the export with audio muted and verify that a first-time user can identify the problem, execution, evidence, Case, replay, and supported platforms. Then complete every item in [media acceptance](media-acceptance.md).
