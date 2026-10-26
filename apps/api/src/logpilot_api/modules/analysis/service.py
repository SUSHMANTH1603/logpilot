"""Analysis service orchestrating window extraction and anomaly detection."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from logpilot_api.core.config import settings
from logpilot_api.modules.analysis.detectors import HybridAnomalyDetector
from logpilot_api.modules.analysis.features import extract_window_features
from logpilot_api.modules.analysis.models import AnomalySignal
from logpilot_api.modules.analysis.repository import AnalysisRepository
from logpilot_api.modules.ingestion.models import LogEvent

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service orchestrating feature extraction and anomaly detection."""

    def __init__(
        self,
        session: AsyncSession,
        repository: AnalysisRepository | None = None,
        detector: HybridAnomalyDetector | None = None,
    ) -> None:
        self.session = session
        self.repo = repository or AnalysisRepository(session)
        self.detector = detector or HybridAnomalyDetector(
            warmup_windows=settings.analysis_warmup_windows,
            z_threshold=settings.analysis_z_score_threshold,
            isolation_forest_contamination=settings.analysis_isolation_forest_contamination,
        )
        self.window_duration_seconds = settings.analysis_window_duration_seconds

    async def analyze_events(
        self,
        project_id: uuid.UUID,
        log_source_id: uuid.UUID,
        events: Sequence[LogEvent],
    ) -> AnomalySignal | None:
        """Evaluate a newly ingested batch of events for anomalies.

        Extracts features over a tumbling 5-minute window, gathers historical feature
        windows from the database, evaluates the hybrid detector, and persists an
        AnomalySignal if an anomaly is detected.
        """
        if not events:
            return None

        # Determine current window boundary from event timestamps
        latest_ts = max(e.timestamp for e in events)
        # Ensure latest_ts has timezone info
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=UTC)

        window_end = latest_ts
        window_start = window_end - timedelta(seconds=self.window_duration_seconds)

        # Filter events belonging to current window
        curr_window_events = [e for e in events if e.timestamp >= window_start]
        current_features = extract_window_features(
            curr_window_events,
            duration_seconds=float(self.window_duration_seconds),
        )

        # Gather historical window features from database
        history_features = await self._load_historical_windows(
            project_id=project_id,
            log_source_id=log_source_id,
            before_time=window_start,
            num_windows=settings.analysis_warmup_windows,
        )

        # Run hybrid detection
        result = self.detector.detect(current=current_features, history=history_features)

        if not result.is_anomaly or result.anomaly_type is None:
            return None

        # Persist AnomalySignal
        signal = AnomalySignal(
            project_id=project_id,
            log_source_id=log_source_id,
            anomaly_type=result.anomaly_type.value,
            confidence_score=result.confidence_score,
            window_start=window_start,
            window_end=window_end,
            feature_vector=result.feature_vector,
            detected_at=datetime.now(UTC),
        )
        await self.repo.create_signal(signal)
        logger.info(
            "Anomaly detected: type=%s, confidence=%.2f, source=%s, project=%s",
            signal.anomaly_type,
            signal.confidence_score,
            log_source_id,
            project_id,
        )
        return signal

    async def _load_historical_windows(
        self,
        project_id: uuid.UUID,
        log_source_id: uuid.UUID,
        before_time: datetime,
        num_windows: int,
    ) -> list:
        """Load and extract features for past tumbling windows."""
        total_history_span = timedelta(seconds=self.window_duration_seconds * num_windows)
        history_start = before_time - total_history_span

        historical_events = await self.repo.get_log_events_in_range(
            project_id=project_id,
            log_source_id=log_source_id,
            start_time=history_start,
            end_time=before_time,
        )

        if not historical_events:
            return []

        # Slice historical events into tumbling windows
        windows = []
        for i in range(num_windows):
            w_start = history_start + timedelta(seconds=self.window_duration_seconds * i)
            w_end = w_start + timedelta(seconds=self.window_duration_seconds)
            w_events = [
                e
                for e in historical_events
                if (e.timestamp.replace(tzinfo=UTC) if e.timestamp.tzinfo is None else e.timestamp)
                >= w_start
                and (e.timestamp.replace(tzinfo=UTC) if e.timestamp.tzinfo is None else e.timestamp)
                < w_end
            ]
            if w_events:
                windows.append(
                    extract_window_features(
                        w_events, duration_seconds=float(self.window_duration_seconds)
                    )
                )

        return windows
