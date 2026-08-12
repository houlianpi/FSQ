# Python Architecture Audit Checklist

Use this for Python domain checks within `spec-implementation-audit`. SPEC/code synchronization is a category in that consolidated audit, not a separate scan or repair loop.

## SPEC To Code

- Root `SPEC.md` lists all modules changed or added.
- Module `SPEC.md` exists for every touched module.
- Module Purpose matches actual ownership.
- Public Interface matches exported symbols, endpoints, commands, or events.
- Internal Structure matches actual files.
- Dependencies match actual imports.
- Python Architecture level and rationale match implementation complexity.

## Public And Internal Boundaries

- Public symbols are exported through `__init__.py` or documented entry point.
- Internal `_name.py` files are not imported by other modules.
- Tests may import internals only when the project convention permits white-box tests.

## Dependency Direction

- Imports follow the dependency DAG in root `SPEC.md`.
- No cycles were introduced.
- Domain/application code does not import framework or persistence details unless SPEC permits it.

## Model Boundaries

- Pydantic schemas stay at API/config/message boundaries unless SPEC permits combined models.
- ORM models stay in persistence boundaries unless SPEC permits active-record style.
- Domain rules live in domain/application code, not serializers or routers.

## Verification

- Tests cover the public behavior promised by SPEC.
- Relevant verification commands were run.
- Failures, skipped checks, or unavailable tools are reported honestly.

## Verdict Language

Use blocking verdicts for architecture gaps:

- `missing`: required module, export, behavior, or test absent.
- `diverged`: implementation contradicts SPEC.
- `interface-only`: public symbol exists without required behavior.
- `boundary-violation`: import or framework/domain boundary violates SPEC.
- `needs-human-decision`: SPEC and implementation cannot be reconciled without a design decision.
