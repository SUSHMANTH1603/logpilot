"""Feature extraction for log windows conforming to D08 § 4.1."""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LogWindowFeatures:
    """Mathematical features extracted from a discrete time window of log events."""

    total_events: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    critical_count: int
    error_rate: float
    warn_to_info_ratio: float
    severity_entropy: float
    distinct_templates_count: int
    event_rate_per_sec: float

    def to_vector(self) -> list[float]:
        """Convert scalar features to an ordered vector for statistical/ML modeling."""
        return [
            float(self.total_events),
            float(self.error_count),
            float(self.warning_count),
            self.error_rate,
            self.warn_to_info_ratio,
            self.severity_entropy,
            float(self.distinct_templates_count),
            self.event_rate_per_sec,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize features to a dictionary suitable for JSON/JSONB storage."""
        return {
            "total_events": self.total_events,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "debug_count": self.debug_count,
            "critical_count": self.critical_count,
            "error_rate": round(self.error_rate, 4),
            "warn_to_info_ratio": round(self.warn_to_info_ratio, 4),
            "severity_entropy": round(self.severity_entropy, 4),
            "distinct_templates_count": self.distinct_templates_count,
            "event_rate_per_sec": round(self.event_rate_per_sec, 4),
        }


def extract_window_features(
    events: Sequence[Any],
    duration_seconds: float = 300.0,
) -> LogWindowFeatures:
    """Extract volumetric, error, and informational features from a sequence of events.

    Args:
        events: Sequence of LogEvent instances or objects with 'level' and 'template_id'.
        duration_seconds: Tumbling window duration in seconds (default 300s = 5 min).

    Returns:
        LogWindowFeatures containing extracted metrics.
    """
    total = len(events)
    if total == 0:
        return LogWindowFeatures(
            total_events=0,
            error_count=0,
            warning_count=0,
            info_count=0,
            debug_count=0,
            critical_count=0,
            error_rate=0.0,
            warn_to_info_ratio=0.0,
            severity_entropy=0.0,
            distinct_templates_count=0,
            event_rate_per_sec=0.0,
        )

    level_counts: Counter[str] = Counter()
    template_ids: set[Any] = set()

    for event in events:
        lvl = getattr(event, "level", "INFO").upper()
        level_counts[lvl] += 1
        tpl_id = getattr(event, "template_id", None)
        if tpl_id is not None:
            template_ids.add(tpl_id)

    error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
    warning_count = level_counts.get("WARNING", 0) + level_counts.get("WARN", 0)
    info_count = level_counts.get("INFO", 0)
    debug_count = level_counts.get("DEBUG", 0)
    critical_count = level_counts.get("CRITICAL", 0)

    error_rate = error_count / total
    warn_to_info_ratio = warning_count / max(1, info_count)

    # Shannon Entropy over severity distribution: H = - sum(p * log2(p))
    entropy = 0.0
    for count in level_counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)

    rate_per_sec = total / max(1.0, duration_seconds)

    return LogWindowFeatures(
        total_events=total,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        debug_count=debug_count,
        critical_count=critical_count,
        error_rate=error_rate,
        warn_to_info_ratio=warn_to_info_ratio,
        severity_entropy=entropy,
        distinct_templates_count=len(template_ids),
        event_rate_per_sec=rate_per_sec,
    )
