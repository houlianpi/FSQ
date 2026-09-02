# FSQ Case Format

An FSQ Case is UTF-8 YAML with the `.fsq.yaml` suffix. The current schema identifier is `fsq.ai-test/v1`. The following independent minimum example opens TodoMVC and verifies its heading:

```yaml
schemaVersion: fsq.ai-test/v1
name: TodoMVC smoke test
platform: web
---
- startBrowser
- navigateTo:
    url: https://todomvc.com/examples/react/dist/
- assertVisible:
    target: TodoMVC heading
    locator:
      role: heading
      name: todos
    optional: false
- closeBrowser
```

For a complete recorded workflow with text entry, clicks, and final-state assertions, see [`examples/web/example-domain.fsq.yaml`](../examples/web/example-domain.fsq.yaml).

The first YAML document contains metadata. The optional second document contains ordered commands. Unknown fields, unsupported schema versions, malformed commands, and platform mismatches fail validation.

Commands execute in authored order through the selected platform Harness. Evidence and the authoritative result are written to one Run directory; the source Case is not modified. With `--suggest`, FSQ still executes only once. Later AI analysis cannot operate the UI or rewrite the result.

Prefer semantic roles, accessible names, resource identifiers, and stable application-owned attributes. Keep secrets and machine-specific executable paths out of Cases. Treat generated candidate Cases as proposals requiring review.
