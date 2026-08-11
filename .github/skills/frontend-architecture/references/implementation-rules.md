# Frontend Implementation Rules

Implement only against confirmed root and frontend module specs.

## Framework And Language

- Use the repository Vite workspace for development and production compilation.
- New React application source uses TypeScript/TSX.
- Let `package.json` and the lock file own exact versions; do not encode dependency versions in agent instructions.
- Do not introduce Next.js, React Server Components, server actions, Vercel hosting APIs, or React Native patterns into this Vite browser application unless a confirmed SPEC changes the platform.
- Do not partially migrate a module whose current SPEC names a different framework or source language.

## Components And Composition

- Organize components by stable behavior and ownership, not every visual wrapper.
- Prefer explicit variants or composition to growing sets of boolean mode props.
- Keep feature-specific components inside their feature boundary.
- Create shared primitives only after multiple consumers demonstrate the same contract.
- Do not nest abstractions that only forward props or rename one call.

## State And Effects

- Keep state near the component or feature that owns its lifecycle.
- Compute derived values during render instead of copying them into state through effects.
- Use effects only to synchronize with external systems such as streams, timers, browser APIs, or imperative libraries.
- Clean up subscriptions, `EventSource`, timers, object URLs, and global event listeners.
- Separate server data, durable browser preferences, transient interaction state, and derived view state.
- Use transitions or deferred values only when a non-urgent expensive update affects responsiveness.

## Async And Transport

- Keep API, SSE, WebSocket, binary media, and persistence boundaries explicit and testable.
- Start independent requests together and await them together when ordering is unnecessary.
- Preserve cancellation, stale-response, reconnect, and cleanup semantics from the module SPEC.
- Parse and validate untrusted transport data at the boundary appropriate to its risk.
- Do not reproduce backend authorization, filesystem, or validation policy in browser code.

## Rendering And Performance

- Import directly from the module needed by the browser bundle.
- Defer heavy optional code until the related feature is activated when bundle evidence justifies it.
- Keep frequently changing transient values out of broad render subscriptions.
- Use memoization only for measured expensive work or stable component boundaries.
- Prefer CSS classes and compositor-friendly properties for repeated visual updates.
- Preserve stable layout dimensions for toolbars, panels, grids, media, and status surfaces.

## Styling And Accessibility

- Follow the module's existing visual language unless the confirmed design changes it.
- Use design tokens or CSS custom properties for repeated semantic values.
- Keep selector specificity predictable and avoid selectors that unintentionally override component variants.
- Use semantic elements and native controls before recreating behavior.
- Preserve accessible names, visible focus, keyboard behavior, and reduced-motion handling required by the SPEC.

## Dependencies And Generated Files

- Use existing libraries when they already own the needed behavior.
- Add a dependency only when it removes meaningful complexity and matches the confirmed architecture.
- Update both npm manifest and lock file for dependency changes.
- Never edit, vendor, or commit generated Vite assets or `node_modules` as authored source.