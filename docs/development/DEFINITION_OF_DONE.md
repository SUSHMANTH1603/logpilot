# LogPilot — Definition of Done

## Overview

A feature, task, or fix is **not considered complete** until all applicable criteria below are satisfied. This checklist ensures consistent quality across the project.

## Checklist

### Implementation

- [ ] Code is implemented according to the approved design/proposal
- [ ] Code follows project coding standards ([DEVELOPMENT.md](DEVELOPMENT.md))
- [ ] Code passes linting and formatting checks
- [ ] Code passes type checking (mypy for Python, TypeScript strict mode)
- [ ] No unnecessary dependencies introduced
- [ ] No hardcoded secrets, credentials, or sensitive data
- [ ] Configuration is externalized where appropriate

### Tests

- [ ] Unit tests written for new functionality
- [ ] Unit tests cover happy path, error cases, and relevant edge cases
- [ ] Integration tests written where the feature interacts with external systems or other modules
- [ ] All existing tests continue to pass
- [ ] Test coverage does not decrease (coverage targets **TBD**)

### Error Handling

- [ ] Errors are handled gracefully — no unhandled exceptions in expected failure modes
- [ ] Error messages are informative and actionable
- [ ] Errors are logged appropriately
- [ ] User-facing errors do not leak internal details or secrets

### Security

- [ ] Secret redaction is applied where the feature handles repository content or log data
- [ ] Input validation is implemented for user-provided data
- [ ] Authorization checks are in place where applicable
- [ ] No sensitive data is logged or exposed in error messages
- [ ] `.logpilotignore` rules are respected where applicable

### Documentation

- [ ] Public APIs have docstrings/JSDoc
- [ ] Complex algorithms or non-obvious logic have inline comments
- [ ] README or relevant documentation is updated if the feature changes behavior or adds new capabilities
- [ ] ADR created if the feature involves an architectural decision
- [ ] API documentation is updated if endpoints are added or modified

### Review

- [ ] Code has been reviewed (AI review + human review)
- [ ] Review feedback has been addressed
- [ ] Commit messages follow conventional commit format

### Acceptance Criteria

- [ ] All acceptance criteria specified in the requirement are met
- [ ] Feature works as described — verified manually or via automated tests
- [ ] No regressions introduced

## Applicability

Not every criterion applies to every change:

| Change Type | Applicable Criteria |
|---|---|
| Feature | All |
| Bug fix | Implementation, Tests, Error Handling, Security, Review, Acceptance |
| Documentation | Documentation, Review |
| Refactor | Implementation, Tests, Review |
| Experiment | Implementation, Tests, Documentation (experiment log), Review |
| CI/CD | Implementation, Review |

## Exceptions

If a criterion cannot be satisfied for a specific change, document the reason in the PR description. Do not silently skip criteria.
