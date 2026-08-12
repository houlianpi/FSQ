# Frontend SPEC Audit Checklist

Audit frontend implementation against the confirmed root and relevant frontend/backend module specs plus the actual diff. Tests and screenshots are supporting evidence, not substitutes for diff inspection.

Use these as frontend domain checks within the consolidated project implementation audit. Do not start a separate synchronization scan or repair loop.

## Ownership And Structure

- Root module navigation points to the actual parent frontend SPEC.
- Parent frontend specs link independently owned child modules without duplicating application behavior.
- Child specs match actual entries, source files, exports, routes, and feature boundaries.
- Authored source, generated assets, backend implementation, and package output remain in their documented ownership boundaries.
- Implementation folders do not acquire artificial specs unless they became independent modules.

## Framework And Dependencies

- The implemented framework and source language match the module SPEC.
- React/TypeScript is not mixed into a module whose current SPEC still names a legacy framework exception.
- npm manifest, lock file, Vite configuration, and imported packages agree.
- Exact versions live in the manifest and lock file rather than skill instructions.
- No unapproved Next.js, Vercel, React Native, remote-runtime, or generated/vendor dependency surface appears.

## State And Integration

- Server data, durable browser preferences, transient interaction state, and derived values follow the documented owners.
- Effects and external subscriptions have cleanup paths.
- Browser code consumes documented transport contracts and does not import backend implementation or duplicate backend security/filesystem policy.
- Loading, empty, partial, error, disabled, cancellation, conflict, and completion behavior matches the SPEC where applicable.

## User Interface

- Component and composition boundaries match the documented architecture level.
- Required semantic roles, accessible names, keyboard behavior, focus treatment, and reduced-motion handling are implemented.
- Responsive constraints prevent clipping and incoherent overlap at the required viewports.
- Interface copy and status transitions remain consistent with the confirmed behavior.

## Verification Evidence

- Required build, type, lint, unit/component, integration, and package checks were run.
- User-visible changes have the browser workflow and viewport evidence required by the SPEC.
- Visual changes include screenshot review when required.
- Console, network, stream, binary, range, and accessibility evidence is present when those boundaries changed.
- Missing tools or checks are reported as gaps rather than silently treated as passing.

## Verdict

For each applicable SPEC item, cite concrete diff evidence and classify it using the repository audit verdicts. Any missing, incomplete, diverged, interface-only, mock/stub, boundary-violation, or unresolved human-decision item blocks completion.