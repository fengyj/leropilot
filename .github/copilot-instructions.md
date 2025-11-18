# Development Constitution

## Core Principles

### 1. Test-Driven, Quality-Gated Development

All new production functionality MUST follow strict TDD: write failing tests first, then implement, then refactor. No production code without corresponding tests. All local and CI tests MUST pass before merge. Quality gates (lint, formatting, type/static analysis) are mandatory. Principles are enforceable via PR review and CI.

POC Testing Exception: For Proof-of-Concept (POC) artifacts placed under a dedicated `poc/` folder, don't create unit tests.

### 2. Modular, Single-Responsibility Architecture

Code MUST be decomposed into small, cohesive modules with clear boundaries. Each module/class/function has a single responsibility. No "god" classes or giant functions. Reusable logic extracted rather than duplicated. Configuration and constants centralized. Extensibility is achieved through loose coupling and pluggable components.

### 3. Explicit, Readable Communication

Source code comments, commit messages, PR descriptions, and issue discussions MUST be written in English. Naming MUST be meaningful, avoiding unclear abbreviations. Public APIs require clear docstrings with rationale when intent is non-obvious.

### 4. Security & Compliance by Design

No hardcoded secrets. All external inputs validated and sanitized. HTTPS required for network calls. Sensitive data encrypted at rest and never logged. SQL and other queries MUST be parameterized. Security considerations included in design and review.

### 5. Observability & Traceability

Structured (preferably JSON) logging with appropriate levels (DEBUG, INFO, WARNING, ERROR, CRITICAL). Every critical workflow includes a trace_id or correlation identifier. Errors always log stack traces. Logs exclude secrets and personal data. Observability choices enable rapid root cause analysis.

OpenTelemetry integration encouraged where applicable.

### 6. Performance & Resource Efficiency

Critical code paths target O(n) or O(n log n). O(n^2) or worse requires documented justification. Large data handled via streaming/generators; never load >100MB in memory at once. Asynchronous I/O or concurrency used where appropriate. Database access optimized (indexes, pagination; no N+1). Performance rationale documented for deviations.

### 7. Consistent Automation & Continuous Improvement

CI automates formatting, linting, static checks, and tests. Every PR must clear all automation gates. Tooling evolves but never regresses compliance. Self-review checklist completed before requesting review. Violations require explicit, documented justification.

## Code Structure & Maintainability

- Enforce layered, modular structure (`src/`, `tests/`, `docs/`).
- Single responsibility per function/class/module.
- Centralize configuration and constants (no magic numbers/strings inline).
- Specification, plans, and tasks documents are stored under `specs/features/{branch_name}/` directory.
- Document complex flows with comments or diagrams.
- Use "enterprise standard" solutions or best practices where applicable.

Hard Limits (violations require explicit justification):

- Function length: recommended <= 50 lines; MUST NOT exceed 300 lines.
- Class public methods: <= 15.
- Function parameters: <= 5 (else use config object/dataclass).
- Nesting depth: <= 4.
- Loop/cyclomatic complexity: <= 10.

## Code Style & Readability

- Use meaningful, descriptive names; avoid inscrutable abbreviations.
- Important configuration documented in README or dedicated docs.
- Git commit messages follow Conventional Commits.
- Each unit test function must have an explanation about what case it is testing.
- Use English in code files, document files, and git comments.

## Dependency & Environment Management

- All dependencies declared in `pyproject.toml` (and lock file if used). No undeclared installs.
- Introduce new dependency only with documented purpose in PR description.
- Virtual environment required; package management via `uv`.
- Latest version is preferred. Avoid deprecated or vulnerable packages; audit periodically.
- Evaluate compatibility before upgrades; document risk mitigation.

## Documentation Files Editing Standards

- When editing documentations, especially when modifying them, please not just focus on the spot of the content you want to change, but also please make sure the overall structure is clear and easy to read, and no redundant or repeated content exists.
- Don't histate to reorganize the structure of the document if you think it can be improved.
- Use pseudo-code, diagrams, or examples where appropriate to clarify complex concepts. Usually it can make the document more readable.
- Be concise but comprehensive. Avoid unnecessary verbosity while ensuring all critical information is conveyed.
- Provide the relatived links to related documents or external references for further reading when applicable.
- Documents are written in English, unless it's a chinese document (`*.zh.md`).
- When updating documenets, update the English version first, and then update the translated versions.

## Extensibility & Collaboration

- Favor reusable modules over duplicated logic.
- Enable future extension via configuration or plugin-like patterns (where appropriate) without over-engineering.
- Communicate early for cross-cutting changes; document decisions.
