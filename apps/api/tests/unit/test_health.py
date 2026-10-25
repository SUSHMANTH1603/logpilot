"""Unit tests for service health, liveness, and readiness probes."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_v1_health_contract(client: AsyncClient) -> None:
    """Verify GET /api/v1/health conforms strictly to D06 § 7.1 contract."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "HEALTHY"
    assert "version" in payload
    assert "timestamp" in payload

    # Security check: Ensure zero leakage of internal connection details (D06 § 7.1 / D11)
    text_content = response.text.lower()
    assert "password" not in text_content
    assert "postgres" not in text_content
    assert "redis" not in text_content
    assert "qdrant" not in text_content


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient) -> None:
    """Verify GET /health returns liveness status."""
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "UP"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_request_id_header_middleware(client: AsyncClient) -> None:
    """Verify incoming and outgoing correlation request ID propagation."""
    # Test auto-generation
    res1 = await client.get("/api/v1/health")
    assert "x-request-id" in res1.headers
    assert res1.headers["x-request-id"].startswith("req_")

    # Test client-provided ID preservation
    custom_id = "req_custom_trace_987654321"
    res2 = await client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert res2.headers["x-request-id"] == custom_id
