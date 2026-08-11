# Frontend Design Rules

Apply these rules only when a confirmed request adds or reshapes user-visible UI.

## Ground The Interface

Before choosing a visual direction, identify:

- The actual product or workflow.
- The primary user and their working context.
- The screen's single most important job.
- Existing visual and interaction conventions that must remain coherent.
- Real content, data density, and exceptional states.

For operational tools such as the FSQ Playground, prefer a quiet, work-focused interface optimized for scanning, comparison, repeated action, and clear status. Do not turn an application workspace into a marketing page.

## Design Before Implementation

For a meaningful visual change, record a compact direction in the design document:

- Color roles and contrast, not decorative color accumulation.
- Type roles and scale appropriate to the density of the interface.
- Layout structure and responsive constraints.
- One justified signature element when the product benefits from it.
- Motion purpose and reduced-motion behavior.

Follow the existing design system when one exists. A new design direction requires a product reason, not novelty by default.

## Complete Interaction States

Design the relevant states before implementation:

- Initial and loading.
- Empty and unavailable.
- Partial data and stale data.
- Error and retry.
- Disabled, busy, cancellation, and completion.
- Optimistic or conflict behavior when applicable.
- Narrow viewport, overflow, and long-content behavior.

Controls must keep stable dimensions and must not overlap when labels, status, or dynamic content change.

## Accessibility And Input

- Start with semantic HTML and native controls.
- Give icon-only or unfamiliar controls accessible names and visible tooltips where useful.
- Preserve logical tab order, visible focus, keyboard operation, and focus restoration.
- Do not rely on color alone for status or selection.
- Respect reduced-motion preferences when motion is present.
- Ensure touch targets and pointer interactions remain usable at narrow widths.
- Use live regions only for updates that users need announced.

## Interface Copy

- Name controls by the action or object users recognize.
- Keep one action name throughout its button, progress, success, and error states.
- Use concise active language and sentence case.
- Make empty and error states say what happened and what action is available.
- Do not expose implementation vocabulary unless the target user works with that concept directly.

## Visual Self-Review

When visual output changes, inspect screenshots at representative desktop and narrow viewports. Check hierarchy, clipping, overlap, focus, state distinction, contrast, content density, and whether decorative choices serve the workflow. Remove elements that do not carry information or support the task.