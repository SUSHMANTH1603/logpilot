"""Ingestion API route endpoints conforming strictly to D06 § 7.4."""

import uuid

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.api.deps import get_session, verify_bearer_token
from logpilot_api.modules.ingestion.schemas import (
    IngestionRunResponse,
    LogIngestRequest,
    LogIngestResponse,
    LogSourceCreate,
    LogSourceResponse,
)
from logpilot_api.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["Log Ingestion"])


@router.post(
    "/log-sources",
    response_model=LogSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a telemetry emitter under a project",
)
async def register_log_source(
    project_id: uuid.UUID,
    payload: LogSourceCreate,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> LogSourceResponse:
    """Register a new log source and issue an ingestion key (D06 § 7.4)."""
    service = IngestionService(session)
    source, plain_key = await service.register_log_source(project_id, payload)
    resp = LogSourceResponse.model_validate(source)
    resp.ingestion_key = plain_key
    return resp


@router.get(
    "/log-sources",
    response_model=list[LogSourceResponse],
    summary="List configured log sources for a project",
)
async def list_log_sources(
    project_id: uuid.UUID,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> list[LogSourceResponse]:
    """List all log sources scoped strictly to the specified project (D06 § 7.4)."""
    service = IngestionService(session)
    sources = await service.list_log_sources(project_id)
    return [LogSourceResponse.model_validate(s) for s in sources]


@router.get(
    "/log-sources/{log_source_id}",
    response_model=LogSourceResponse,
    summary="Get specific log source details",
)
async def get_log_source(
    project_id: uuid.UUID,
    log_source_id: uuid.UUID,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> LogSourceResponse:
    """Retrieve details for a specific log source (D06 § 7.4)."""
    service = IngestionService(session)
    source = await service.get_log_source(project_id, log_source_id)
    return LogSourceResponse.model_validate(source)


@router.post(
    "/log-sources/{log_source_id}/ingest",
    response_model=LogIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a batch of log lines for ingestion",
)
async def ingest_logs(
    project_id: uuid.UUID,
    log_source_id: uuid.UUID,
    payload: LogIngestRequest,
    x_logpilot_source_key: str | None = Header(default=None, alias="X-LogPilot-Source-Key"),
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> LogIngestResponse:
    """Submit a batch of sanitized log lines for ingestion (D06 § 7.4)."""
    service = IngestionService(session)
    run, count = await service.ingest_batch(
        project_id=project_id,
        log_source_id=log_source_id,
        payload=payload,
        source_key=x_logpilot_source_key,
        bearer_token=authorization,
    )
    return LogIngestResponse(
        ingestion_run_id=run.id,
        status=run.status,
        received_count=count,
        enqueued_at=run.started_at,
    )


@router.get(
    "/ingestion-runs/{ingestion_run_id}",
    response_model=IngestionRunResponse,
    summary="Inspect status and metrics of an ingestion run",
)
async def get_ingestion_run(
    project_id: uuid.UUID,
    ingestion_run_id: uuid.UUID,
    _token: str = Depends(verify_bearer_token),
    session: AsyncSession = Depends(get_session),
) -> IngestionRunResponse:
    """Retrieve status, events_processed, and error metrics for an ingestion run (D06 § 7.4)."""
    service = IngestionService(session)
    run = await service.get_ingestion_run(project_id, ingestion_run_id)
    return IngestionRunResponse.model_validate(run)
