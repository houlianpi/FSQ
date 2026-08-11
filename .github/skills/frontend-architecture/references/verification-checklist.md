# Frontend Verification Checklist

Scale verification to the changed behavior and the confirmed module SPEC. Run the cheapest check that can falsify the current implementation first.

## Deterministic Checks

- Use the repository's locked dependency installation when dependencies or the build environment need validation.
- Run the configured production build for every frontend source or build-configuration change.
- Run configured type checking, lint, formatting, and unit/component tests for the touched module.
- Run focused tests before broad suites, then run broader checks when shared contracts or packaging changed.
- Confirm the manifest and lock file are synchronized after dependency changes.
- Confirm generated assets and `node_modules` remain untracked.

Do not invent a command that the repository does not provide. If an expected check is absent, report the gap and use the closest executable evidence available.

## Browser Behavior

For user-visible or browser-lifecycle changes:

- Exercise the primary workflow and the affected loading, empty, error, disabled, cancellation, and completion states.
- Test representative desktop and narrow viewports.
- Check keyboard navigation, visible focus, accessible names, and focus restoration.
- Check reduced-motion behavior when animation or transitions exist.
- Inspect console errors, unhandled rejections, failed requests, and reconnect loops.
- Verify long content, localization expansion when relevant, overflow, and panel resizing without overlap.
- Capture screenshots when layout, styling, responsive behavior, or visual state distinction changed.

## Integration Boundaries

- Verify JSON error and unavailable responses remain actionable.
- Verify streams append, resume, reconnect, and clean up as specified.
- Verify binary upload/download, media playback, object URL cleanup, and HTTP range behavior when affected.
- Verify backend-owned validation and filesystem safety are not duplicated or weakened in browser code.
- Verify production static serving and packaged assets when build output or package integration changed.

## Evidence Record

Record the commands run, their results, browser viewports and workflows exercised, screenshots captured, and any unavailable checks. A successful build alone is insufficient when the confirmed SPEC requires interaction, responsive, accessibility, or visual evidence.