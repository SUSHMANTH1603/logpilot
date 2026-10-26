"""Unit tests for feature extraction and anomaly detectors conforming to D08 § 4."""

from dataclasses import dataclass
from datetime import UTC, datetime

from logpilot_api.modules.analysis.detectors import (
    HybridAnomalyDetector,
    IsolationForestDetector,
    StatisticalBaselineDetector,
    normalize_z_to_confidence,
)
from logpilot_api.modules.analysis.features import LogWindowFeatures, extract_window_features
from logpilot_api.modules.analysis.models import AnomalyType


@dataclass
class DummyEvent:
    level: str
    template_id: str | None = None
    timestamp: datetime = datetime.now(UTC)


def test_feature_extraction_empty_events() -> None:
    """Empty event sequence produces zeroed metrics and zero entropy."""
    feats = extract_window_features([])
    assert feats.total_events == 0
    assert feats.error_count == 0
    assert feats.error_rate == 0.0
    assert feats.severity_entropy == 0.0
    assert feats.distinct_templates_count == 0
    assert feats.event_rate_per_sec == 0.0
    assert len(feats.to_vector()) == 8
    assert "total_events" in feats.to_dict()


def test_feature_extraction_mixed_events() -> None:
    """Mixed events produce accurate rates and positive Shannon entropy."""
    events = [
        DummyEvent(level="INFO", template_id="tpl_1"),
        DummyEvent(level="INFO", template_id="tpl_1"),
        DummyEvent(level="WARNING", template_id="tpl_2"),
        DummyEvent(level="ERROR", template_id="tpl_3"),
        DummyEvent(level="CRITICAL", template_id="tpl_3"),
    ]
    feats = extract_window_features(events, duration_seconds=300.0)
    assert feats.total_events == 5
    assert feats.error_count == 2  # ERROR + CRITICAL
    assert feats.warning_count == 1
    assert feats.info_count == 2
    assert feats.error_rate == 0.4
    assert feats.distinct_templates_count == 3
    assert feats.severity_entropy > 0.0
    assert feats.event_rate_per_sec > 0.0


def test_normalize_z_to_confidence_boundaries() -> None:
    """Verify confidence normalization is strictly bounded in [0.0, 1.0]."""
    assert normalize_z_to_confidence(0.0, 3.0) == 0.0
    assert normalize_z_to_confidence(-1.0, 3.0) == 0.0
    # Below threshold
    conf_below = normalize_z_to_confidence(2.0, 3.0)
    assert 0.0 < conf_below < 0.70
    # Exactly at threshold
    conf_at = normalize_z_to_confidence(3.0, 3.0)
    assert round(conf_at, 2) == 0.70
    # High Z-score
    conf_high = normalize_z_to_confidence(6.0, 3.0)
    assert 0.70 < conf_high <= 1.0
    # Extreme Z-score does not exceed 1.0
    conf_extreme = normalize_z_to_confidence(100.0, 3.0)
    assert conf_extreme <= 1.0


def test_statistical_detector_empty_history() -> None:
    """Statistical detector handles empty history gracefully."""
    detector = StatisticalBaselineDetector(z_threshold=3.0)
    curr = extract_window_features([DummyEvent(level="ERROR")])
    res = detector.detect(curr, [])
    assert not res.is_anomaly
    assert res.confidence_score == 0.0


def test_statistical_detector_zero_variance() -> None:
    """Statistical detector handles zero variance in historical baseline without zero division."""
    detector = StatisticalBaselineDetector(z_threshold=3.0)
    # History with zero error rate and 10 events every window
    history = [
        LogWindowFeatures(
            total_events=10,
            error_count=0,
            warning_count=0,
            info_count=10,
            debug_count=0,
            critical_count=0,
            error_rate=0.0,
            warn_to_info_ratio=0.0,
            severity_entropy=0.0,
            distinct_templates_count=1,
            event_rate_per_sec=0.033,
        )
        for _ in range(12)
    ]

    # Current window with zero errors -> inlier
    res_normal = detector.detect(history[0], history)
    assert not res_normal.is_anomaly

    # Current window with sudden error surge -> flags error spike safely
    curr_anomaly = LogWindowFeatures(
        total_events=20,
        error_count=10,
        warning_count=0,
        info_count=10,
        debug_count=0,
        critical_count=0,
        error_rate=0.5,
        warn_to_info_ratio=0.0,
        severity_entropy=1.0,
        distinct_templates_count=2,
        event_rate_per_sec=0.066,
    )
    res_spike = detector.detect(curr_anomaly, history)
    assert res_spike.is_anomaly
    assert res_spike.anomaly_type == AnomalyType.ERROR_RATE_SPIKE
    assert 0.70 <= res_spike.confidence_score <= 1.0


def test_statistical_detector_volume_drop() -> None:
    """Sudden total volume collapse when historical volume is high flags VOLUME_DROP."""
    detector = StatisticalBaselineDetector(z_threshold=3.0)
    history = [
        LogWindowFeatures(
            total_events=100,
            error_count=0,
            warning_count=0,
            info_count=100,
            debug_count=0,
            critical_count=0,
            error_rate=0.0,
            warn_to_info_ratio=0.0,
            severity_entropy=0.0,
            distinct_templates_count=5,
            event_rate_per_sec=0.33,
        )
        for _ in range(12)
    ]
    curr_empty = extract_window_features([])
    res = detector.detect(curr_empty, history)
    assert res.is_anomaly
    assert res.anomaly_type == AnomalyType.VOLUME_DROP
    assert res.confidence_score >= 0.70


def test_isolation_forest_detector_behavior() -> None:
    """Isolation Forest detector flags extreme vector deviations."""
    detector = IsolationForestDetector(contamination=0.05)
    # Generate historical windows with realistic natural variation
    history = [
        LogWindowFeatures(
            total_events=50 + (i % 7),
            error_count=1 if i % 3 == 0 else 0,
            warning_count=2,
            info_count=47 + (i % 5),
            debug_count=0,
            critical_count=0,
            error_rate=0.02 if i % 3 == 0 else 0.0,
            warn_to_info_ratio=0.04,
            severity_entropy=0.2,
            distinct_templates_count=5,
            event_rate_per_sec=0.16,
        )
        for i in range(30)
    ]

    # Outlier window with extreme rate and errors
    outlier_window = LogWindowFeatures(
        total_events=5000,
        error_count=4000,
        warning_count=500,
        info_count=500,
        debug_count=0,
        critical_count=500,
        error_rate=0.80,
        warn_to_info_ratio=1.0,
        severity_entropy=1.5,
        distinct_templates_count=50,
        event_rate_per_sec=16.6,
    )
    res = detector.detect(outlier_window, history)
    assert res.is_anomaly
    assert 0.70 <= res.confidence_score <= 1.0


def test_hybrid_detector_warmup_vs_ml_phase() -> None:
    """Hybrid detector applies static rules during warm-up and statistical/ML after."""
    hybrid = HybridAnomalyDetector(warmup_windows=10, z_threshold=3.0)

    # 1. During Warm-up (< 10 windows)
    history_short = [
        LogWindowFeatures(
            total_events=10,
            error_count=0,
            warning_count=0,
            info_count=10,
            debug_count=0,
            critical_count=0,
            error_rate=0.0,
            warn_to_info_ratio=0.0,
            severity_entropy=0.0,
            distinct_templates_count=1,
            event_rate_per_sec=0.033,
        )
        for _ in range(5)
    ]

    # Mild error: during warmup, not enough to trigger static rules
    mild_err = LogWindowFeatures(
        total_events=10,
        error_count=1,
        warning_count=0,
        info_count=9,
        debug_count=0,
        critical_count=0,
        error_rate=0.10,
        warn_to_info_ratio=0.0,
        severity_entropy=0.3,
        distinct_templates_count=1,
        event_rate_per_sec=0.033,
    )
    res_mild = hybrid.detect(mild_err, history_short)
    assert not res_mild.is_anomaly

    # Critical event during warm-up -> static rule flags immediately
    crit_window = LogWindowFeatures(
        total_events=10,
        error_count=1,
        warning_count=0,
        info_count=9,
        debug_count=0,
        critical_count=1,
        error_rate=0.10,
        warn_to_info_ratio=0.0,
        severity_entropy=0.3,
        distinct_templates_count=1,
        event_rate_per_sec=0.033,
    )
    res_crit = hybrid.detect(crit_window, history_short)
    assert res_crit.is_anomaly
    assert res_crit.confidence_score == 0.85
    assert res_crit.detector_name == "warmup_static_rules"

    # 2. Beyond Warm-up (>= 10 windows) -> activates statistical & ML scoring
    history_full = [history_short[0] for _ in range(12)]
    res_post_warmup = hybrid.detect(crit_window, history_full)
    assert res_post_warmup.is_anomaly
    assert res_post_warmup.detector_name == "statistical_baseline"
