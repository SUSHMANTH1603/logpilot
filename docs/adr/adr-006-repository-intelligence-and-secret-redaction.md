# ADR-006: Repository Intelligence and Secret Redaction

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot's value proposition includes understanding repository context — source code, configuration, dependencies, Docker files, project structure, Git history, recent commits, relevant diffs, service relationships, documentation, and historical incidents. This repository intelligence enables the system to correlate runtime anomalies with code changes and provide repository-aware RCA.

However, repository scanning creates security risks: secrets, credentials, and sensitive information in repositories must never be sent to LLM providers or stored in vector indices without redaction.

## Decision

### Repository Intelligence Scope

The system should understand and index:

- Source code structure and content
- Configuration files
- Dependency manifests
- Dockerfiles and container configuration
- Project directory structure
- Git history and recent commits
- Relevant diffs (temporally correlated with incidents)
- Service relationships (inferred from configuration, imports, API calls)
- Documentation and runbooks
- Historical incident data

### Secret Redaction

Secret redaction is a **mandatory, defense-in-depth** requirement:

1. **`.logpilotignore` file**: Users can specify paths and patterns to exclude from scanning (follows `.gitignore` syntax). This is the first layer of defense.

2. **Built-in exclusion rules**: The system applies default exclusions regardless of `.logpilotignore` contents:
   - `.env*`, `*.pem`, `*.key`, `credentials*`, `secrets*`
   - `node_modules/`, `.git/`, `dist/`, `build/`
   - Full list maintained in `.logpilotignore` defaults

3. **Active secret detection**: The system must scan content for patterns that look like secrets (API keys, tokens, passwords, connection strings) and redact them before:
   - Sending content to any LLM provider
   - Storing content in vector indices
   - Including content in incident reports

4. **Safe LLM context construction**: The system must never send an entire repository to an LLM by default. Context sent to LLMs must be:
   - Scoped to relevant files/snippets
   - Filtered through `.logpilotignore` and built-in rules
   - Scanned for and redacted of secrets

### Configurable Exclusions

The `.logpilotignore` specification:

- Uses `.gitignore` pattern syntax
- Is checked into the repository (project-specific)
- Can be supplemented by system-level defaults
- Is documented in the repository root

## Consequences

### Positive

- Developers can trust that secrets are not leaked to LLM providers
- `.logpilotignore` gives developers explicit control over what is scanned
- Defense-in-depth approach means no single mechanism is a single point of failure
- Repository intelligence significantly enhances RCA quality

### Negative

- Active secret detection may produce false positives (redacting non-secret content)
- Secret detection patterns need ongoing maintenance
- Repository scanning adds processing overhead

### Neutral

- The specific secret detection library/approach is **TBD**
- The repository indexing strategy (full re-index vs. incremental) is **TBD**
- How repository context is chunked and embedded for retrieval is **TBD**

## Alternatives Considered

1. **No repository scanning**: Rejected. Eliminates a key differentiating capability and a major evidence signal for RCA.

2. **Trust `.logpilotignore` only**: Rejected. Users may forget to exclude sensitive files; defense-in-depth is necessary.

3. **`.logpilotignore` + built-in rules + active detection**: Selected. Provides multiple layers of protection.
