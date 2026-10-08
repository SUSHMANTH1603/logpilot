# ADR-008: Multi-Tenancy Strategy

**Status:** Accepted
**Date:** 2026-10-08

## Context

LogPilot must support data isolation between different projects. The system must also be architecturally prepared for a future multi-tenancy hierarchy without requiring a full redesign.

## Decision

### V1: Project-Level Isolation

V1 implements **project-level isolation**:

- Each project has its own isolated data scope
- Logs, incidents, repository context, and analytics are scoped to a project
- Users interact within the context of a specific project

### Future-Ready Architecture

The data model and API design should be future-ready for the following hierarchy:

```
Organization
    → Teams
        → Projects
            → Repositories
                → Services
```

To support this:

- Major database tables and resources should be designed so that `organization_id` and `project_id` columns can be introduced consistently
- API routes should be structured to accommodate scoping (e.g., `/projects/{project_id}/incidents/`)
- Queries and access control should be parameterized by project scope, not hardcoded

### V1 Scope

In V1:

- `project_id` is the primary isolation key
- `organization_id` and `team_id` are **not implemented** but the schema should not make them impossible to add
- Authentication and authorization scope to project level

## Consequences

### Positive

- Clean data isolation from day one
- Future expansion to organization/team hierarchy does not require redesigning the data model
- API design naturally supports scoping

### Negative

- Requires discipline to consistently include project scoping in all new features
- Some V1 queries may have unnecessary indirection if project_id is always the same in a single-project deployment

### Neutral

- The specific authentication/authorization mechanism is **TBD**
- Whether V1 supports multiple projects per deployment or is single-project is **TBD**
- The migration path from V1 single-level to full hierarchy is **TBD**

## Alternatives Considered

1. **No isolation in V1**: Rejected. Adding isolation later requires retrofitting every query and API endpoint.

2. **Full multi-tenancy hierarchy in V1**: Rejected. Over-engineering for current needs; adds complexity without immediate benefit.

3. **Project-level isolation with future-ready design**: Selected. Provides necessary isolation now while keeping the path open.
