# Development Constitution

This document defines how the AI coding assistant (Copilot) should generate and modify code and documentation for this project (Python backend + React + Tailwind + Vite frontend).

---

## Core Principles

### 1. Test-Driven, Quality-Gated Development

- All new **production** functionality MUST follow TDD:
  - Write failing tests first, then implement, then refactor.
- No production code without corresponding tests.
- All local and CI tests MUST pass before merge.
- Lint, formatting, and static/type checks are mandatory and MUST pass.

### 2. Modular, Single-Responsibility Architecture

- Code MUST be decomposed into small, cohesive modules with clear boundaries.
- Each module/class/function has a single responsibility.
- Extract reusable logic instead of duplicating it.
- Centralize configuration and constants; avoid magic numbers/strings.
- Follow the project structure: `src/`, `tests/`, `docs/`, `specs/features/{branch_name}/`.

### 3. Explicit, Readable Communication

- All code comments, commit messages, PR descriptions, and docs MUST be in English (except `*_zh.md`).
- Names MUST be meaningful; avoid unclear abbreviations.
- Public APIs need clear docstrings, including rationale if intent is non-obvious.

### 4. Security & Compliance by Design

- Security is mandatory: no hardcoded secrets, validate all inputs, never log sensitive data.
- Follow the concrete security rules in **Cross-Cutting Concerns → Security & Compliance**.

### 5. Observability & Traceability

- Follow the logging and tracing rules defined in **Cross-Cutting Concerns → Observability & Traceability**.

### 6. Performance & Resource Efficiency

- Favor O(n) or O(n log n) algorithms; any O(n²)+ in critical paths requires justification in code comments or PR.
- Do not load >100MB data into memory at once; use streaming/generators.
- Use async I/O or concurrency where appropriate.
- Avoid N+1 database queries; use proper indexing and pagination.

### 7. Consistent Automation

- CI MUST run formatting, linting, static analysis, and tests for every PR.
- Code that breaks automation MUST NOT be merged.
- Any intentional deviation from these standards MUST be documented in the PR description.

---

## Backend Development Standards

### Code Structure & Maintainability

- Use a layered, modular structure under `src/`.
- Keep responsibilities narrow per function/class/module.
- Complex flows MUST be documented with comments or diagrams.
- Prefer proven, well-maintained libraries over niche/unmaintained ones.

**Hard Limits** (enforced via `ruff`, `pylint`, or pre-commit; violations require explicit justification):

- Function length: recommended ≤ 50 lines; MUST NOT exceed 300 lines.
- Class public methods: ≤ 15.
- Function parameters: ≤ 5 (else use a config object/dataclass).
- Nesting depth: ≤ 4.
- Cyclomatic complexity: ≤ 10.

### Type Hints & Static Analysis

**Core Requirements:**

- All functions and methods MUST have type hints for all parameters and return values.
- Functions with no return value MUST be annotated with `-> None`.
- Class attributes SHOULD be annotated (in `__init__` or at class level).
- Module-level constants and variables SHOULD be annotated when not obvious.

**Type Annotation Standards:**

- Avoid `Any` unless absolutely necessary. Use specific types or generics:

  ```python
  # Bad: too permissive
  def process_data(data: Any) -> Any:
      ...

  # Good: specific types
  def process_data(data: dict[str, int]) -> list[str]:
      ...

  # Good: generic
  from typing import TypeVar

  T = TypeVar("T")

  def get_first(items: list[T]) -> T | None:
      return items[0] if items else None
  ```

- Use built-in generics (Python 3.9+):

  ```python
  # Good
  def merge_dicts(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
      ...
  ```

- Use union types with `|` (Python 3.10+) or `Optional`:

  ```python
  def find_user(user_id: int) -> User | None:
      ...
  ```

- Use `Protocol` for structural typing, `TypedDict` for structured dicts, and `collections.abc` (`Iterable`, `Mapping`, etc.) for interfaces.
- Use type aliases for complex/reused types:

  ```python
  UserID = int
  ConfigDict = dict[str, str | int | bool]
  ```

- Use `Literal` for fixed sets:

  ```python
  from typing import Literal

  LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
  ```

**Static Type Checking:**

- Run `mypy` (or `pyright`) in **strict** mode; all type errors MUST be fixed before merge.
- Example `pyproject.toml` settings:

  ```toml
  [tool.mypy]
  strict = true
  warn_unused_ignores = true
  disallow_any_generics = true
  disallow_untyped_defs = true
  ```

- Use `# type: ignore[error-code]` **sparingly** and always with an explanatory comment.

**Exceptions:**

- Test files MAY use relaxed typing (e.g., `Any` for mocks).

### Code Style & Readability

- Use meaningful, descriptive names.
- Git commit messages follow Conventional Commits:

  - Format: `<type>(<scope>): <subject>` (e.g., `feat(api): add user authentication`).

- Each unit test function MUST have a short comment/docstring describing what it tests.
- Use English for all code and docs.

### Testing & Quality Gates

- All production code MUST have corresponding unit tests (`pytest`).
- Tests MUST pass locally and in CI before merge.
- Coverage target:
  - >80% for critical flows.
  - 100% for small utility functions.
- Mock external dependencies (API calls, DB, filesystem) in unit tests.
- Write integration tests for critical end-to-end workflows.

### Dependency & Environment Management

- All dependencies MUST be declared in `pyproject.toml`. No ad-hoc installs.
- New dependencies require a short justification in the PR description.
- Use a virtual environment; package management via `uv`.
- Prefer latest stable versions; avoid deprecated/vulnerable packages.

### Environment Variables

- Use `.env` files (excluded from Git) and load via `python-dotenv` or similar.
- Maintain `.env.example` with all required variables.
- Never commit secrets; manage production secrets via CI/CD or a vault.

---

## Frontend Development Standards

### Component Architecture

- Components MUST follow single responsibility: one main concern per component.
- Prefer functional components with hooks over class components.
- Prefer structure like `ComponentName/index.tsx` (and optional CSS module).
- Maximum component size: 300 lines; refactor into subcomponents/hooks beyond this.
- Props MUST be explicitly typed; avoid `any` unless strictly necessary (document why in a comment).

### React Best Practices

- Use custom hooks (prefixed with `use*`) for reusable stateful logic.
- Avoid prop drilling >2 levels; use Context or state management library.
- Use `useMemo`, `useCallback`, and `React.memo` for expensive or frequently re-rendered parts.
- Isolate side effects in `useEffect` with proper cleanup.
- Use stable, non-index keys for lists (unless truly static).

### TypeScript Requirements

- Enable strict mode in `tsconfig.json`.
- No implicit `any`; all function parameters and returns must have types.
- Use `interface` for object shapes, `type` for unions/intersections.
- Use discriminated unions for complex state (e.g., async state machines).

### UI Design & Visual Consistency

**Design System Foundation:**

- Maintain design tokens in `tailwind.config.js` (and/or `src/styles/tokens.ts`) for:
  - Colors (primary, secondary, semantic: success, warning, error, info).
  - Typography (fonts, sizes, weights, line heights).
  - Spacing.
  - Border radius.
  - Shadows.
  - Animation durations/easing.
- Components MUST use tokens from config; do NOT hardcode values in components.

**AI-Assisted Design Guidance:**

- When implementing UI, ask AI for:
  - Color palettes and semantic mapping.
  - Typography hierarchy and spacing.
  - Accessibility-safe colors and focus states.
  - Recommended patterns for forms, tables, navigation, modals, etc.
- Always provide feature context and user goals so AI can propose appropriate patterns.

**Color & Typography:**

- Use semantic colors for states (success/warning/error/info).
- Maintain good contrast (see Accessibility).
- Use Tailwind scales (`text-sm`, `text-base`, etc.) and consistent font weights.

**Spacing & Layout:**

- Use Tailwind spacing scale (`p-*`, `m-*`, `gap-*`, `space-*`).
- Use consistent container widths (e.g., `max-w-7xl` for main content).
- Use flex/grid patterns for common layouts (lists, cards, forms).

**Component Patterns:**

- Define and reuse variants (e.g., Button: `primary`, `secondary`, `ghost`, `danger`).
- Ensure consistent hover/active/disabled/focus states.

**Iconography & Motion:**

- Use a single icon library (e.g., Heroicons or Lucide).
- Keep animations subtle and performant; respect `prefers-reduced-motion`.

### Styling with Tailwind

**Core Principles:**

- Tailwind utility classes are the primary styling mechanism.
- MUST use tokens/config values from `tailwind.config.js`; avoid hardcoded colors/spacing/font sizes.
- If custom CSS is required, use CSS modules or scoped styles with semantic class names.

**Class Naming & Organization:**

- Order Tailwind classes roughly as: layout → spacing → typography → colors → effects → transitions.

  ```tsx
  <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors" />
  ```

- Use `prettier-plugin-tailwindcss` to sort classes.
- Use `clsx` or `cva` for conditional/variant classes:

  ```tsx
  const buttonClass = clsx(
    "px-4 py-2 rounded font-medium transition-colors",
    variant === "primary" && "bg-blue-600 text-white hover:bg-blue-700",
    variant === "secondary" && "bg-gray-200 text-gray-900 hover:bg-gray-300",
    disabled && "opacity-50 cursor-not-allowed"
  );
  ```

**Custom CSS Guidelines:**

- Semantic class names only (BEM-style preferred):

  - Good: `.card-header`, `.button--primary`, `.modal__overlay`.
  - Bad: `.box1`, `.blue-thing`, `.wrapper2`.

- Avoid `@apply` where possible; prefer reusable React components. Exception: global utilities or third-party overrides where `@apply` is clearly simpler.

**Hardcoded Values:**

- Arbitrary values (`[]` syntax) allowed ONLY when:
  - The value doesn't fit Tailwind's scale, AND
  - It is not reused, AND
  - A short comment explains why.
- Do NOT use arbitrary values for standard colors/spacing:
  - Bad: `bg-[#3b82f6]` (use `bg-blue-600`).
  - Bad: `p-[24px]` (use `p-6`).

**Responsive Design:**

- Mobile-first: base styles for mobile, add breakpoints for larger screens.

  ```tsx
  // Good
  <div className="text-sm md:text-base lg:text-lg" />
  ```

**Dark Mode:**

- Use `dark:` variants for colors.
- Test both light and dark schemes for major pages.

**Performance (CSS/Rendering):**

- Ensure Tailwind content paths are correct so unused CSS is purged.
- Avoid huge un-virtualized lists; use virtualization for lists > ~100 items.

### State Management

- Use `useState` for simple local state.
- Lift state up when shared between parent/child.
- Use Context for cross-cutting concerns (theme, auth, i18n).
- Only introduce external state libraries if complexity justifies it; document why in the PR.

### API Integration & Data Fetching

- Prefer `TanStack Query` (React Query) or `SWR` for server state:
  - Caching, revalidation, retries, and loading/error states handled centrally.
- Otherwise, encapsulate API calls in `src/api/` or `src/services/`.
- Use `async/await` plus `try/catch` for error handling.
- Always reflect loading/error/success states in the UI.
- DO NOT hardcode API URLs; use `import.meta.env`.
- Request and response types MUST be explicitly defined (interfaces/types).

### Build & Bundle Optimization

- Use dynamic imports for code splitting (lazy load routes/heavy components).
- Lazy load non-critical assets; compress images and prefer WebP/AVIF.
- Prefer named exports over default for better tree-shaking.
- Avoid extremely large bundles; use lazy loading and splitting to keep chunk sizes reasonable.

### Testing

- Use Vitest for unit tests, React Testing Library for component tests.
- Test behavior from a user perspective; avoid testing internal implementation details.
- Coverage target: >80% for critical flows, 100% for small utilities.
- Mock API calls; tests MUST NOT hit real networks.

### Accessibility (a11y)

- Use semantic HTML elements (`button`, `nav`, `main`, etc.).
- Add ARIA attributes only when semantics are insufficient.
- Ensure keyboard navigation works (focusable, visible focus states).
- Maintain contrast: ≥ 4.5:1 for normal text, ≥ 3:1 for large text.
- For critical flows, verify with a screen reader or at least inspect accessible names/roles.

### Frontend Performance

- Avoid unnecessary re-renders; use React DevTools Profiler where needed.
- Debounce/throttle high-frequency events (scroll, keypress, live search).
- Use virtualization for large lists (>100 items).
- Aim for Lighthouse: Performance > 90, Accessibility > 95 on key pages.

### Frontend Environment Variables

- Use `.env.local` for local development.
- Access variables via `import.meta.env`.
- Document required variables in `.env.example`.
- Configure production env vars in deployment, not in code.

---

## Cross-Cutting Concerns

### Security & Compliance

**Backend:**

- Never hardcode secrets; always use env vars or a secret manager.
- Validate and sanitize all external inputs (HTTP, CLI, files, etc.).
- Use parameterized queries (no string-concatenated SQL).
- Enforce HTTPS for external service calls.
- Never log passwords, tokens, or sensitive identifiers.

**Frontend:**

- Sanitize any HTML-like user content before rendering (e.g., `DOMPurify`).
- Avoid `dangerouslySetInnerHTML`; if unavoidable, document why and sanitize input.
- Use CSRF protection for state-changing requests.
- Apply Content Security Policy (CSP) where possible.
- Validate/sanitize data from backend before rendering.

### Error Handling & Validation

**Backend API Error Response:**

- Use a consistent error response shape:

  ```json
  {
    "error": {
      "code": "UNIQUE_ERROR_CODE",
      "message": "A human-readable error description.",
      "details": {
        "field_name": "Specific error for this field."
      }
    }
  }
  ```

- Use appropriate HTTP status codes (400, 401, 403, 404, 500, etc.).
- Prefer Pydantic (or similar) for parsing and validating request bodies.

**Frontend Error Handling:**

- Implement a central API error handler to map backend errors to UI messages.
- Use React Error Boundaries for catching render-time errors and showing fallback UI.
- Use client-side validation for forms (e.g., `Zod`, `React Hook Form`).

### Observability & Traceability

**Backend:**

- Use structured JSON logging with appropriate levels.
- Include a correlation/trace ID in logs for each request/critical workflow.
- Always log stack traces for unexpected errors.
- Do not log secrets or personal data.

**Frontend:**

- Capture global errors and unhandled promise rejections.
- For critical flows, log minimal, anonymized telemetry (e.g., success/failure, timing).
- Monitor Core Web Vitals in production when possible.

---

## Collaboration & Process

### Git Workflow

- Branch naming: `feature/{issue-number}-{short-description}` or `fix/{issue-number}-{short-description}`.
- Commit early and often; each commit should be atomic and buildable.
- Create a PR for every feature/fix to trigger CI/CD and enable systematic self-review.
- Rebase on `main` before creating a PR to keep history linear.

### PR Review Checklist (Self-Review)

Before merging a PR, ensure:

- [ ] All automated CI checks have passed.
- [ ] New functionality is covered by tests.
- [ ] Relevant documentation (`README`, `docs/`, code comments) is updated.
- [ ] No hardcoded secrets or sensitive data are introduced.
- [ ] Performance and accessibility are acceptable for affected critical paths.
- [ ] Any deviations from this document are explicitly justified in the PR description.

### Documentation Standards

When Copilot edits documentation (e.g., `README.md`, files in `docs/`):

- Ensure the structure is clear and logical; reorganize if it improves readability.
- Use pseudo-code, diagrams, or examples for complex concepts.
- Write in English, except for `*_zh.md` files, which are in Chinese.
