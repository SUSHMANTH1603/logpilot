# LogPilot — Development Standards

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Protected. Production-ready code only. |
| `develop` | Integration branch. All feature branches merge here first. |
| `feature/<name>` | Feature development. Branch from `develop`, merge back to `develop`. |
| `fix/<name>` | Bug fixes. Branch from `develop` (or `main` for hotfixes). |
| `docs/<name>` | Documentation-only changes. |
| `experiment/<name>` | Research experiments and ML evaluation work. |

### Rules

- `main` is protected — no direct pushes
- All changes go through pull requests
- Feature branches must be up-to-date with `develop` before merging

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Usage |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Build, CI, tooling, or maintenance |
| `perf` | Performance improvement |
| `style` | Formatting, whitespace (no logic change) |
| `ci` | CI/CD pipeline changes |
| `experiment` | Research/ML experiment work |

### Scopes

Use the component name: `api`, `web`, `extension`, `agent`, `worker`, `ml`, `rca`, `rag`, `infra`, `docs`, `schemas`, etc.

### Examples

```
feat(api): add incident creation endpoint
fix(worker): handle empty log lines in ingestion
docs(adr): add ADR-011 for caching strategy
test(ml): add anomaly detection unit tests
refactor(rca): extract evidence scoring into separate module
experiment(ml): baseline isolation forest evaluation
```

## Code Quality

### Python

- **Linting**: Ruff (linter + formatter)
- **Type checking**: mypy (strict mode)
- **Testing**: Pytest
- **Formatting**: Ruff formatter (or Black — **TBD**, will standardize on one)
- **Import sorting**: Ruff (isort-compatible rules)

### TypeScript

- **Linting**: ESLint
- **Type checking**: TypeScript strict mode
- **Testing**: Vitest (web), VS Code extension test framework (extension)
- **Formatting**: Prettier
- **E2E testing**: Playwright (web dashboard)

### General

- All code must pass linting and type checking before merge
- All new features must include tests
- Test coverage targets will be established when the test suite is set up (**TBD**)

## Pull Request Process

1. Create a feature branch from `develop`
2. Implement changes with tests
3. Ensure all CI checks pass (lint, type check, test)
4. Create a pull request to `develop`
5. At least one review required before merge
6. Squash-merge to keep history clean (or merge commits if the branch has meaningful intermediate commits — team preference **TBD**)

## Project Structure Conventions

### Python Packages

- Each Python component (`apps/api/`, `agent/logpilot-agent/`, `workers/*`, `ml/*`, `packages/schemas/`) will have its own `pyproject.toml` when implementation begins
- Use `src/` layout where appropriate
- Shared domain logic lives in importable packages, not duplicated

### TypeScript Packages

- `apps/web/` and `apps/vscode-extension/` will have their own `package.json` when implementation begins
- Use TypeScript strict mode

### Configuration

- Environment-specific configuration via `.env` files (never committed)
- Provide `.env.example` templates
- Application configuration via Pydantic `Settings` classes

## Documentation Standards

- All public APIs must have docstrings
- Complex algorithms must have inline comments explaining the approach
- Architecture changes require an ADR
- README files in major directories explain the directory's purpose
- Development guides live in `docs/development/`

## Security Practices

- Never commit secrets, keys, or credentials
- Use `.env` files for local secrets (gitignored)
- All code handling user data or repository content must consider secret redaction
- Dependencies must be reviewed for known vulnerabilities before adoption
- Authentication and authorization must be tested

## CI/CD

GitHub Actions will be used for CI/CD. The pipeline will include:

- Linting and formatting checks
- Type checking
- Unit tests
- Integration tests (where applicable)
- Build verification

CI/CD pipeline implementation is **TBD**.
