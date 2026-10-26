"""Anomaly detectors conforming to D08 § 4.2-4.3 and Phase 4 approved decisions."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

from logpilot_api.modules.analysis.features import LogWindowFeatures
from logpilot_api.modules.analysis.models import AnomalyType


@dataclass
class DetectionResult:
    """Result emitted by an anomaly detector on a single window."""

    is_anomaly: bool
    anomaly_type: AnomalyType | None = None
    confidence_score: float = 0.0
    detector_name: str = "none"
    feature_vector: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


def normalize_z_to_confidence(z_score: float, z_threshold: float) -> float:
    """Normalize a Z-score >= z_threshold into [0.0, 1.0] confidence score.

    Uses a soft exponential curve where z == z_threshold produces ~0.70 confidence,
    scaling asymptotically toward 1.0 as z increases.
    """
    if z_score <= 0.0:
        return 0.0
    if z_score < z_threshold:
        # Below threshold: scale linearly between 0.0 and 0.69
        return min(0.69, max(0.0, (z_score / z_threshold) * 0.69))

    # At or above threshold: map [z_threshold, inf) -> [0.70, 0.99]
    excess = z_score - z_threshold
    # e.g. excess=0 -> 0.70; excess=3 -> 0.70 + 0.29 * (1 - exp(-1.5)) ~= 0.92
    confidence = 0.70 + 0.29 * (1.0 - math.exp(-excess / 2.0))
    return min(1.0, max(0.0, round(confidence, 4)))


class StatisticalBaselineDetector:
    """Statistical Z-score and rolling-baseline anomaly detector conforming to D08 § 4.2."""

    def __init__(self, z_threshold: float = 3.0) -> None:
        self.z_threshold = z_threshold

    def detect(
        self,
        current: LogWindowFeatures,
        history: Sequence[LogWindowFeatures],
    ) -> DetectionResult:
        """Evaluate current window features against historical baseline."""
        vector_dict = current.to_dict()
        if not history:
            return DetectionResult(
                is_anomaly=False,
                confidence_score=0.0,
                detector_name="statistical_baseline",
                feature_vector=vector_dict,
                details={"reason": "empty_history"},
            )

        # 1. Error rate Z-score
        hist_error_rates = [h.error_rate for h in history]
        mean_err = float(np.mean(hist_error_rates))
        std_err = float(np.std(hist_error_rates))

        z_err = 0.0
        if std_err > 1e-6:
            z_err = (current.error_rate - mean_err) / std_err
        elif current.error_rate > mean_err:
            # Zero variance historical baseline with positive deviation
            z_err = 4.0 if current.error_rate > 0.05 else 0.0

        # 2. Total volume / frequency Z-score
        hist_counts = [float(h.total_events) for h in history]
        mean_cnt = float(np.mean(hist_counts))
        std_cnt = float(np.std(hist_counts))

        z_cnt = 0.0
        if std_cnt > 1e-6:
            z_cnt = (float(current.total_events) - mean_cnt) / std_cnt
        elif float(current.total_events) > mean_cnt and current.total_events > 10:
            z_cnt = 4.0

        # Check for Volume Drop anomaly: sudden collapse in total events
        is_volume_drop = False
        if mean_cnt >= 20.0 and current.total_events == 0:
            is_volume_drop = True

        # Check for error spike or frequency spike
        max_z = max(z_err, z_cnt)
        is_anomaly = max_z >= self.z_threshold or is_volume_drop

        if not is_anomaly:
            return DetectionResult(
                is_anomaly=False,
                confidence_score=normalize_z_to_confidence(max_z, self.z_threshold),
                detector_name="statistical_baseline",
                feature_vector=vector_dict,
                details={"z_error": round(z_err, 3), "z_count": round(z_cnt, 3)},
            )

        # Determine anomaly type
        if is_volume_drop:
            atype = AnomalyType.VOLUME_DROP
            conf = 0.85
        elif z_err >= z_cnt and z_err >= self.z_threshold:
            atype = AnomalyType.ERROR_RATE_SPIKE
            conf = normalize_z_to_confidence(z_err, self.z_threshold)
        elif z_cnt > z_err and z_cnt >= self.z_threshold:
            atype = AnomalyType.FREQUENCY_SPIKE
            conf = normalize_z_to_confidence(z_cnt, self.z_threshold)
        else:
            atype = AnomalyType.BURST_DEVIATION
            conf = normalize_z_to_confidence(max_z, self.z_threshold)

        return DetectionResult(
            is_anomaly=True,
            anomaly_type=atype,
            confidence_score=conf,
            detector_name="statistical_baseline",
            feature_vector=vector_dict,
            details={
                "z_error": round(z_err, 3),
                "z_count": round(z_cnt, 3),
                "mean_error_rate": round(mean_err, 4),
                "std_error_rate": round(std_err, 4),
                "mean_total_events": round(mean_cnt, 2),
                "std_total_events": round(std_cnt, 2),
            },
        )


class IsolationForestDetector:
    """Isolation Forest anomaly detector conforming to D08 § 4.3."""

    def __init__(self, contamination: float = 0.01) -> None:
        self.contamination = contamination

    def detect(
        self,
        current: LogWindowFeatures,
        history: Sequence[LogWindowFeatures],
    ) -> DetectionResult:
        """Fit Isolation Forest on historical feature vectors and score the current window."""
        vector_dict = current.to_dict()
        if len(history) < 5:
            return DetectionResult(
                is_anomaly=False,
                confidence_score=0.0,
                detector_name="isolation_forest",
                feature_vector=vector_dict,
                details={"reason": "insufficient_history", "history_len": len(history)},
            )

        # Build feature matrix incorporating current window into reference population
        x_hist = np.array([h.to_vector() for h in history], dtype=float)
        x_curr = np.array([current.to_vector()], dtype=float)
        x_all = np.vstack([x_hist, x_curr])

        try:
            clf = IsolationForest(
                contamination=self.contamination,
                random_state=42,
                n_estimators=100,
            )
            clf.fit(x_all)
            pred = clf.predict(x_curr)[0]  # -1 for anomaly, 1 for inlier
            raw_score = float(clf.score_samples(x_curr)[0])
            threshold_score = float(clf.offset_)
            is_anomaly = bool(pred == -1)

            # Map raw score to normalized confidence score in [0.0, 1.0]
            if is_anomaly:
                # Distance below threshold
                diff = threshold_score - raw_score
                conf = 0.70 + 0.28 * (1.0 - math.exp(-max(0.0, diff) * 10.0))
            else:
                conf = max(0.0, min(0.69, 0.5 + raw_score))

            conf = min(1.0, max(0.0, round(conf, 4)))

            atype = AnomalyType.BURST_DEVIATION
            if current.error_rate > 0.15:
                atype = AnomalyType.ERROR_RATE_SPIKE
            elif current.event_rate_per_sec > 10.0:
                atype = AnomalyType.FREQUENCY_SPIKE

            return DetectionResult(
                is_anomaly=is_anomaly,
                anomaly_type=atype if is_anomaly else None,
                confidence_score=conf,
                detector_name="isolation_forest",
                feature_vector=vector_dict,
                details={
                    "raw_score": round(raw_score, 4),
                    "threshold_score": round(threshold_score, 4),
                    "prediction": int(pred),
                },
            )
        except Exception as exc:
            return DetectionResult(
                is_anomaly=False,
                confidence_score=0.0,
                detector_name="isolation_forest",
                feature_vector=vector_dict,
                details={"error": str(exc)},
            )


class HybridAnomalyDetector:
    """Hybrid detector managing cold-start warm-up rules and model ensemble."""

    def __init__(
        self,
        warmup_windows: int = 10,
        z_threshold: float = 3.0,
        isolation_forest_contamination: float = 0.01,
    ) -> None:
        self.warmup_windows = warmup_windows
        self.statistical_detector = StatisticalBaselineDetector(z_threshold=z_threshold)
        self.iforest_detector = IsolationForestDetector(
            contamination=isolation_forest_contamination
        )

    def detect(
        self,
        current: LogWindowFeatures,
        history: Sequence[LogWindowFeatures],
    ) -> DetectionResult:
        """Run hybrid detection: static rules during warm-up; statistical & ML after."""
        vector_dict = current.to_dict()

        # Check warm-up condition
        if len(history) < self.warmup_windows:
            return self._detect_warmup_rules(current, len(history), vector_dict)

        # Beyond warm-up: run statistical baseline
        stat_result = self.statistical_detector.detect(current, history)
        if stat_result.is_anomaly:
            return stat_result

        # Run Isolation Forest detector as secondary evaluation
        iforest_result = self.iforest_detector.detect(current, history)
        if iforest_result.is_anomaly:
            return iforest_result

        # Normal window
        return DetectionResult(
            is_anomaly=False,
            confidence_score=max(stat_result.confidence_score, iforest_result.confidence_score),
            detector_name="hybrid_ensemble",
            feature_vector=vector_dict,
            details={
                "stat_score": stat_result.confidence_score,
                "iforest_score": iforest_result.confidence_score,
                "warmup_complete": True,
            },
        )

    def _detect_warmup_rules(
        self,
        current: LogWindowFeatures,
        history_len: int,
        vector_dict: dict[str, Any],
    ) -> DetectionResult:
        """Static rule-based evaluation used during warm-up cold-start."""
        # 1. Critical event occurrence
        if current.critical_count > 0:
            return DetectionResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.ERROR_RATE_SPIKE,
                confidence_score=0.85,
                detector_name="warmup_static_rules",
                feature_vector=vector_dict,
                details={"reason": "critical_event_observed", "history_windows": history_len},
            )

        # 2. Elevated error burst during cold start
        if current.error_rate >= 0.20 and current.error_count >= 3:
            conf = min(1.0, 0.70 + 0.25 * current.error_rate)
            return DetectionResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.ERROR_RATE_SPIKE,
                confidence_score=round(conf, 4),
                detector_name="warmup_static_rules",
                feature_vector=vector_dict,
                details={"reason": "error_burst_above_20_pct", "history_windows": history_len},
            )

        # 3. High volume burst during cold start
        if current.total_events >= 500:
            return DetectionResult(
                is_anomaly=True,
                anomaly_type=AnomalyType.FREQUENCY_SPIKE,
                confidence_score=0.75,
                detector_name="warmup_static_rules",
                feature_vector=vector_dict,
                details={"reason": "high_volume_spike", "history_windows": history_len},
            )

        return DetectionResult(
            is_anomaly=False,
            confidence_score=0.0,
            detector_name="warmup_static_rules",
            feature_vector=vector_dict,
            details={"reason": "within_warmup_limits", "history_windows": history_len},
        )
