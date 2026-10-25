"""Ingestion domain service implementing business rules, normalization, and persistence.

Conforms to D05, D06, D07, and D11.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from logpilot_api.core.security import (
    decode_access_token,
    generate_source_key,
    hash_source_key,
    verify_source_key,
)
from logpilot_api.modules.identity.repository import UserRepository
from logpilot_api.modules.ingestion.models import IngestionRun, LogEvent, LogSource
from logpilot_api.modules.ingestion.normalizer import (
    compute_event_hash,
    normalize_severity,
    normalize_timestamp,
    redact_secrets,
    sanitize_attributes,
)
from logpilot_api.modules.ingestion.repository import IngestionRepository
from logpilot_api.modules.ingestion.schemas import LogIngestRequest, LogSourceCreate
from logpilot_api.modules.projects.repository import ProjectMembershipRepository, ProjectRepository


class IngestionService:
    """Service orchestrating ingestion validation, authorization, normalization, and persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion_repo = IngestionRepository(session)
        self.project_repo = ProjectRepository(session)

    async def register_log_source(
        self, project_id: uuid.UUID, data: LogSourceCreate
    ) -> tuple[LogSource, str]:
        """Register a new telemetry emitter under a project, issuing a source key (D06 & D11)."""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project '{project_id}' not found.")

        # Check duplicate source name within project and environment
        existing = await self.ingestion_repo.get_log_source_by_name(
            project_id=project_id, name=data.name, environment=data.environment
        )
        if existing:
            raise ConflictError(
                f"Log source '{data.name}' already registered in environment '{data.environment}'."
            )

        raw_key = generate_source_key()
        key_hash = hash_source_key(raw_key)

        source = await self.ingestion_repo.create_log_source(
            project_id=project_id, data=data, ingestion_key_hash=key_hash
        )
        return source, raw_key

    async def get_log_source(self, project_id: uuid.UUID, log_source_id: uuid.UUID) -> LogSource:
        """Retrieve specific log source verifying project ownership (D06 § 7.4)."""
        source = await self.ingestion_repo.get_log_source(project_id, log_source_id)
        if not source:
            raise NotFoundError("Log source not found or does not belong to specified project.")
        return source

    async def list_log_sources(self, project_id: uuid.UUID) -> Sequence[LogSource]:
        """List configured log sources scoped strictly to a project."""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project '{project_id}' not found.")
        return await self.ingestion_repo.list_log_sources(project_id)

    async def verify_credentials(
        self,
        log_source: LogSource,
        source_key: str | None,
        bearer_token: str | None,
    ) -> None:
        """Authenticate caller against source credentials or bearer token (D11 & D06)."""
        if source_key:
            if not log_source.ingestion_key_hash or not verify_source_key(
                source_key, log_source.ingestion_key_hash
            ):
                raise UnauthorizedError("Invalid source key provided in 'X-LogPilot-Source-Key'.")
            return

        if bearer_token:
            parts = bearer_token.strip().split()
            if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
                raise UnauthorizedError("Invalid authorization format. Expected 'Bearer <token>'.")

            payload = decode_access_token(parts[1].strip())
            try:
                user_id = uuid.UUID(payload["sub"])
            except (ValueError, KeyError) as exc:
                raise UnauthorizedError(
                    "Invalid subject identifier in authentication token."
                ) from exc

            user_repo = UserRepository(self.session)
            user = await user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                raise UnauthorizedError("User account not found or inactive.")

            membership_repo = ProjectMembershipRepository(self.session)
            membership = await membership_repo.get_membership(log_source.project_id, user.id)
            if not membership:
                raise NotFoundError(
                    "Log source not found or does not belong to specified project.",
                    code="RESOURCE_NOT_FOUND",
                )

            if membership.role == "VIEWER":
                raise ForbiddenError("VIEWER role cannot ingest telemetry.")

            return

        raise UnauthorizedError(
            "Authentication required. Provide 'X-LogPilot-Source-Key' or 'Authorization: Bearer'."
        )

    async def ingest_batch(
        self,
        project_id: uuid.UUID,
        log_source_id: uuid.UUID,
        payload: LogIngestRequest,
        source_key: str | None,
        bearer_token: str | None,
    ) -> tuple[IngestionRun, int]:
        """Process and persist an ingestion batch conforming to D06 § 7.4 and D07."""
        source = await self.ingestion_repo.get_log_source(project_id, log_source_id)
        if not source:
            raise NotFoundError("Log source not found or does not belong to specified project.")

        if not source.is_active:
            raise BadRequestError(f"Log source '{source.name}' is currently deactivated.")

        # Authenticate telemetry emitter
        await self.verify_credentials(source, source_key=source_key, bearer_token=bearer_token)

        if not payload.events:
            raise BadRequestError("Event batch cannot be empty.")

        # Record ingestion run in STARTED state
        run = await self.ingestion_repo.create_ingestion_run(
            log_source_id=log_source_id, status="STARTED"
        )

        now_utc = datetime.now(UTC)
        normalized_events: list[LogEvent] = []

        for item in payload.events:
            attrs = dict(item.attributes)
            level, attrs = normalize_severity(item.level, attrs)
            ts, attrs = normalize_timestamp(item.timestamp, attrs)
            cleaned_message = redact_secrets(item.message)
            cleaned_attrs = sanitize_attributes(attrs)
            event_hash = compute_event_hash(project_id, log_source_id, ts, cleaned_message)

            event = LogEvent(
                id=uuid.uuid4(),
                project_id=project_id,
                log_source_id=log_source_id,
                timestamp=ts,
                level=level,
                message_raw=cleaned_message,
                attributes=cleaned_attrs,
                event_hash=event_hash,
                ingested_at=now_utc,
            )
            normalized_events.append(event)

        # Persist events with deduplication
        persisted_count = await self.ingestion_repo.persist_events(
            project_id=project_id,
            log_source_id=log_source_id,
            events=normalized_events,
        )

        # Update run to COMPLETED
        await self.ingestion_repo.update_ingestion_run(
            run=run,
            status="COMPLETED",
            events_processed=persisted_count,
            errors_count=0,
        )

        return run, len(payload.events)

    async def get_ingestion_run(
        self, project_id: uuid.UUID, ingestion_run_id: uuid.UUID
    ) -> IngestionRun:
        """Retrieve an ingestion run verifying project ownership (D06 § 7.4)."""
        run = await self.ingestion_repo.get_ingestion_run(project_id, ingestion_run_id)
        if not run:
            raise NotFoundError("Ingestion run not found or does not belong to specified project.")
        return run
