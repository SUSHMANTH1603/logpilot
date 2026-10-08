# LogPilot — AI-Assisted Development Workflow

## Overview

LogPilot development uses AI-assisted engineering (Claude / Antigravity) as a core part of the development process. This document defines the workflow, responsibilities, and constraints for AI-assisted development.

## Workflow

```
Requirement
    → AI analysis and proposal
        → Human review and approval
            → Implementation (AI-assisted)
                → Tests (AI-assisted)
                    → AI review
                        → Human approval
                            → Commit
```

### Step 1: Requirement

- A feature, fix, or task is defined with clear acceptance criteria
- The requirement should reference relevant ADRs, architecture documentation, or product specifications

### Step 2: AI Analysis and Proposal

- The AI agent analyzes the requirement in the context of the existing codebase, architecture, and standards
- The AI proposes an implementation approach, identifying:
  - Files to create or modify
  - Architectural implications
  - Potential risks or ambiguities
  - Testing strategy
- **The AI must not make major architectural decisions silently**
- If the requirement is ambiguous, the AI must **stop and ask** rather than inventing architecture

### Step 3: Human Review and Approval

- The developer reviews the proposed approach
- Adjustments are made if needed
- The developer explicitly approves the approach before implementation begins

### Step 4: Implementation

- The AI implements the approved approach
- Implementation follows the project's development standards (see [DEVELOPMENT.md](DEVELOPMENT.md))
- The AI should explain non-obvious design decisions in code comments or PR descriptions

### Step 5: Tests

- All new functionality must include tests
- The AI writes tests as part of the implementation
- Tests must cover:
  - Happy path
  - Error cases
  - Edge cases relevant to the feature

### Step 6: AI Review

- The AI reviews the complete changeset for:
  - Consistency with architecture and standards
  - Test coverage
  - Security considerations
  - Error handling
  - Documentation
  - Adherence to the Definition of Done ([DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md))

### Step 7: Human Approval

- The developer reviews the final implementation
- Code is approved for commit/merge

### Step 8: Commit

- Changes are committed using conventional commit format
- PR is created targeting the appropriate branch

## AI Agent Constraints

### Must Do

- Follow existing architecture and ADRs
- Reference relevant documentation when proposing changes
- Ask for clarification when requirements are ambiguous
- Explain the rationale behind non-obvious decisions
- Write tests for all new functionality
- Consider security implications (secret redaction, input validation, authorization)
- Follow the project's coding standards and conventions
- Preserve existing comments and documentation unrelated to the change

### Must Not Do

- Make major architectural decisions without explicit human approval
- Silently introduce new technologies or dependencies
- Skip tests
- Ignore security considerations
- Implement features beyond the current scope
- Modify production code autonomously in V1
- Send entire repositories or secrets to LLM providers
- Invent product requirements

### When to Stop and Ask

- The requirement is ambiguous or contradictory
- The implementation would require a new ADR or architectural change
- There are multiple valid approaches and the choice has significant implications
- A security concern is identified that is not addressed by the requirement
- The change would affect multiple components in ways not described in the requirement

## Escalation

If the AI agent encounters a situation not covered by this workflow:

1. Document the situation clearly
2. Stop and ask the developer
3. Do not proceed with assumptions about unspecified behavior
