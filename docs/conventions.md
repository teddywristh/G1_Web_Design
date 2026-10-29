# Repository & Engineering Conventions

This document defines the team conventions for repository organization, branching, commit messages, code style, and pull request workflows for the **Legal AI Assistant** project.

---

## 1. Branching Strategy

We follow a feature-branch workflow based on `main`.

### Main Branch
- `main` is always stable and deployable.
- Direct pushes to `main` are restricted. All changes must arrive via reviewed pull requests.

### Branch Naming Convention
Branches should follow the format: `<type>/<short-description>` using lowercase and hyphens (`kebab-case`).

| Branch Prefix | Purpose | Example |
| :--- | :--- | :--- |
| `feat/` | New features or enhancements | `feat/health-endpoint`, `feat/article-viewer` |
| `fix/` | Bug fixes | `fix/cors-origin-header`, `fix/citation-link` |
| `chore/` | Maintenance, setup, tool configuration | `chore/initial-setup`, `chore/bump-deps` |
| `docs/` | Documentation additions or updates | `docs/architecture-overview`, `docs/setup-guide` |
| `refactor/` | Code refactoring without behavioral change | `refactor/api-schemas`, `refactor/db-session` |
| `test/` | Adding or modifying tests | `test/vector-search-perf`, `test/health-check` |
| `infra/` | Infrastructure, Docker, or CI changes | `infra/postgres-pgvector`, `infra/github-actions` |

---

## 2. Commit Message Conventions

We adhere to the [Conventional Commits](https://www.conventionalcommits.org/) standard. Consistent commit messages generate clean changelogs and simplify code reviews.

### Commit Format
```text
<type>(<scope>): <subject>

[optional body explaining motivation and context]

[optional footer(s), e.g., Closes #123]
```

### Commit Types
- `feat`: A new user-facing or API feature.
- `fix`: A bug fix.
- `docs`: Documentation changes only.
- `style`: Formatting, missing semicolons, whitespace (no code logic change).
- `refactor`: Refactoring production code without fixing a bug or adding a feature.
- `perf`: Code changes that improve performance.
- `test`: Adding missing tests or correcting existing tests.
- `chore`: Build process, dependencies, auxiliary tools, and monorepo configuration.
- `ci`: Changes to CI/CD configuration files and scripts (e.g., GitHub Actions).

### Commit Scopes
Scopes identify which part of the monorepo is affected:
- `web`: Next.js frontend (`apps/web`)
- `api`: FastAPI backend (`apps/api`)
- `ui`: Shared UI library (`packages/ui`)
- `infra`: Docker, database, Redis (`infra/`)
- `docs`: Architecture and developer documentation (`docs/`)
- `scripts`: Utilities and automation scripts (`scripts/`)
- `deps`: Dependency updates
- `root`: Root repository configuration (`.gitignore`, `.editorconfig`, README)

### Commit Rules & Examples
1. Use the imperative, present tense ("add", "fix", "implement", not "added" or "adds").
2. Do not capitalize the first letter of the subject line.
3. Do not place a period (`.`) at the end of the subject line.
4. Limit the subject line to 72 characters.

**Good Examples:**
- `feat(api): add GET /api/v1/health endpoint`
- `fix(web): resolve mobile viewport layout overflow in search bar`
- `chore(root): add .editorconfig and .gitignore for monorepo setup`
- `docs(infra): document postgres pgvector connection settings`
- `test(api): add unit tests for legal document citation parser`

---

## 3. Pull Request (PR) Workflow

### 1. Creating a Pull Request
- Create a PR against `main` using the PR template (`.github/pull_request_template.md`).
- Ensure the PR title follows conventional commit format (e.g., `feat(api): scaffold health endpoint`).
- Reference related issue(s) in the description (e.g., `Closes #5`).

### 2. Pre-PR Checklist
Before requesting reviews, ensure:
- [ ] Code compiles and runs cleanly without unhandled errors.
- [ ] Linters and formatters pass (`ruff check .`, `npm run lint`).
- [ ] All automated tests pass (`pytest`, `npm test`).
- [ ] No secrets, keys, or credentials are committed.
- [ ] `.env.example` is updated if new configuration is introduced.
- [ ] Documentation is updated to reflect new functionality.

### 3. Review & Merge Standards
- At least one code review approval is required from the component owner (see `CODEOWNERS`).
- All GitHub Actions CI checks must be green.
- PRs should be merged using **Squash and Merge** or **Rebase and Merge** to maintain a clean linear Git history.

---

## 4. Code Formatting & Linting Standards

- **EditorConfig**: Supported by all major IDEs via `.editorconfig`.
- **Python (apps/api)**:
  - Formatter & Linter: `Ruff`
  - Max line length: 88 characters (PEP 8 compatible)
  - Type hints: Explicit type annotations encouraged for all function signatures.
- **TypeScript / React (apps/web, packages/ui)**:
  - Linter: `ESLint`
  - Formatter: `Prettier` (configured in web package)
  - Strict typing: `strict: true` in `tsconfig.json`, no implicit `any`.
- **Environment & Secrets**:
  - Never commit real passwords, API tokens, or session secrets.
  - Always provide clean placeholders in `.env.example`.
