# Frontend Architecture Levels

Choose the lowest level that keeps the current module understandable, testable, and changeable. Record the selected level and concrete boundaries in the module SPEC.

## Level 1: Static Or Minimal Interactive Page

Use when the page is primarily content or contains a few independent interactions.

Typical shape:

```text
app/
  index.html
  entry.tsx
  styles.css
```

Rules:

- Keep state local to the interaction that owns it.
- Avoid routers, global stores, data layers, and design-system scaffolding.
- Use semantic HTML before creating abstractions.

Escalate when multiple workflows coordinate shared state or external data.

## Level 2: Component Application

Use for a focused application with reusable components, locally coordinated state, and a small backend integration surface.

Typical shape:

```text
app/
  entry.tsx
  App.tsx
  components/
  api/
  styles/
```

Rules:

- Organize components around stable behavior and ownership.
- Keep state close to its owner and lift it only for real sibling coordination.
- Isolate transport details when more than one component or workflow uses them.
- Do not add a global store or router solely because the app uses React.

Escalate when several workflows share lifecycle, server state, navigation, or persistence rules.

## Level 3: Layered Frontend Application

Use for an application with multiple coordinated workflows, explicit transport adapters, complex view/domain state, or independent feature areas.

Typical shape:

```text
app/
  entry.tsx
  shell/
  features/
  api/
  state/
  shared/
```

Rules:

- Keep application shell, feature workflows, transport adapters, and shared primitives as distinct ownership areas.
- Separate server data, durable browser preferences, transient interaction state, and derived view values.
- Add routing, server-state libraries, or global stores only when their ownership and lifecycle solve measured complexity.
- Prevent shared folders from becoming unowned collections of unrelated helpers.

## Existing Module Exceptions

An existing module that does not fit these normalized levels may retain a named legacy architecture exception when its SPEC accurately describes current source, state, and integration boundaries. Feature work must not silently introduce a second framework or partial architecture migration. A framework or architecture migration requires its own confirmed SPEC update.

## Selection Questions

Use these questions to choose a level:

1. How many independent user workflows share state or lifecycle?
2. Which state is server-owned, browser-persisted, transient, or derived?
3. How many components consume each backend contract?
4. Does navigation need durable URLs or history semantics?
5. Which boundaries need isolated tests or independent change?

If a proposed layer only renames a call or passes values through unchanged, remove it or choose a lower level.