"""
Anomaly Detector

Statistical anomaly detection for cost data using multiple methods:
- Z-Score:          flags data points > N standard deviations from mean
- IQR (Interquartile Range): flags outliers beyond 1.5× IQR
- Isolation Forest:  sklearn-based unsupervised outlier detection
- Moving Average:    flags deviations from rolling average

Results are persisted as ``Anomaly`` rows and can trigger alerts via
the Rules Engine.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from src.models import Anomaly, CostRecord

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detect cost anomalies using configurable statistical methods.

    Usage::

        detector = AnomalyDetector(db_session)
        anomalies = detector.detect_all()
    """

    # Default thresholds
    DEFAULT_ZSCORE_THRESHOLD = 2.5
    DEFAULT_IQR_MULTIPLIER = 1.5
    DEFAULT_MOVING_AVG_WINDOW = 7
    DEFAULT_MOVING_AVG_THRESHOLD = 2.0  # std-devs from rolling avg
    DEFAULT_LOOKBACK_DAYS = 90
    DEFAULT_MIN_DATA_POINTS = 14  # need ≥ 2 weeks to detect anomalies

    def __init__(
        self,
        db: Session,
        zscore_threshold: float = DEFAULT_ZSCORE_THRESHOLD,
        iqr_multiplier: float = DEFAULT_IQR_MULTIPLIER,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_data_points: int = DEFAULT_MIN_DATA_POINTS,
    ):
        self.db = db
        self.zscore_threshold = zscore_threshold
        self.iqr_multiplier = iqr_multiplier
        self.lookback_days = lookback_days
        self.min_data_points = min_data_points

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_all(
        self,
        subscription_id: Optional[str] = None,
        methods: Optional[List[str]] = None,
    ) -> List[Anomaly]:
        """
        Run all (or selected) detection methods and return new anomalies.

        Args:
            subscription_id: Scope detection to a single subscription.
            methods: List of method names to run.  Defaults to all.
                     Valid: 'zscore', 'iqr', 'moving_average', 'isolation_forest'.

        Returns:
            List of newly created Anomaly instances (already added to session).
        """
        if methods is None:
            methods = ["zscore", "iqr", "moving_average"]

        all_anomalies: List[Anomaly] = []

        # Detect per subscription × service combination
        combos = self._get_detection_groups(subscription_id)

        for sub_id, service in combos:
            daily = self._daily_series(sub_id, service)
            if len(daily) < self.min_data_points:
                continue

            dates = [d[0] for d in daily]
            values = np.array([float(d[1]) for d in daily])

            for method in methods:
                if method == "zscore":
                    anomalies = self._detect_zscore(dates, values, sub_id, service)
                elif method == "iqr":
                    anomalies = self._detect_iqr(dates, values, sub_id, service)
                elif method == "moving_average":
                    anomalies = self._detect_moving_average(dates, values, sub_id, service)
                elif method == "isolation_forest":
                    anomalies = self._detect_isolation_forest(dates, values, sub_id, service)
                else:
                    logger.warning("Unknown detection method: %s", method)
                    continue
                all_anomalies.extend(anomalies)

        if all_anomalies:
            self.db.add_all(all_anomalies)
            self.db.commit()
            logger.info("Detected %d anomalies across %d groups", len(all_anomalies), len(combos))

        return all_anomalies

    def detect_for_resource(
        self,
        resource_id: str,
        method: str = "zscore",
    ) -> List[Anomaly]:
        """Detect anomalies for a single resource."""
        daily = self._daily_series_for_resource(resource_id)
        if len(daily) < self.min_data_points:
            return []

        dates = [d[0] for d in daily]
        values = np.array([float(d[1]) for d in daily])

        # Need subscription_id from data
        sub_id = self._subscription_for_resource(resource_id)

        if method == "zscore":
            anomalies = self._detect_zscore(dates, values, sub_id, None, resource_id)
        elif method == "iqr":
            anomalies = self._detect_iqr(dates, values, sub_id, None, resource_id)
        else:
            anomalies = self._detect_moving_average(dates, values, sub_id, None, resource_id)

        if anomalies:
            self.db.add_all(anomalies)
            self.db.commit()

        return anomalies

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_zscore(
        self,
        dates: List[datetime],
        values: np.ndarray,
        subscription_id: str,
        service_name: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> List[Anomaly]:
        """Flag points where |z-score| > threshold."""
        mean = np.mean(values)
        std = np.std(values)
        if std == 0:
            return []

        anomalies: List[Anomaly] = []
        zscores = (values - mean) / std

        for i, (date, cost, z) in enumerate(zip(dates, values, zscores)):
            if abs(z) > self.zscore_threshold:
                severity = self._classify_severity(abs(z), [2.5, 3.0, 4.0])
                deviation_pct = ((cost - mean) / mean) * 100 if mean else 0

                anomaly = Anomaly(
                    detected_at=datetime.now(timezone.utc),
                    subscription_id=subscription_id,
                    resource_id=resource_id or "",
                    service_name=service_name or "Unknown",
                    anomaly_type="cost_spike" if cost > mean else "cost_drop",
                    detection_method="zscore",
                    expected_cost=Decimal(str(round(mean, 6))),
                    actual_cost=Decimal(str(round(cost, 6))),
                    deviation_percentage=round(deviation_pct, 2),
                    deviation_amount=Decimal(str(round(abs(cost - mean), 6))),
                    confidence_score=min(abs(z) / 5.0, 1.0),
                    severity=severity,
                    context={
                        "date": date.isoformat() if isinstance(date, datetime) else str(date),
                        "z_score": round(float(z), 4),
                        "mean": round(mean, 2),
                        "std_dev": round(std, 2),
                        "threshold": self.zscore_threshold,
                    },
                    baseline_data={
                        "window_days": self.lookback_days,
                        "data_points": len(values),
                        "mean": round(mean, 2),
                        "std": round(std, 2),
                        "min": round(float(np.min(values)), 2),
                        "max": round(float(np.max(values)), 2),
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_iqr(
        self,
        dates: List[datetime],
        values: np.ndarray,
        subscription_id: str,
        service_name: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> List[Anomaly]:
        """Flag points outside [Q1 - k×IQR, Q3 + k×IQR]."""
        q1 = float(np.percentile(values, 25))
        q3 = float(np.percentile(values, 75))
        iqr = q3 - q1
        if iqr == 0:
            return []

        lower_fence = q1 - self.iqr_multiplier * iqr
        upper_fence = q3 + self.iqr_multiplier * iqr
        median = float(np.median(values))

        anomalies: List[Anomaly] = []
        for date, cost in zip(dates, values):
            if cost < lower_fence or cost > upper_fence:
                distance = max(cost - upper_fence, lower_fence - cost)
                severity = self._classify_severity(distance / iqr, [1.5, 2.5, 4.0])
                deviation_pct = ((cost - median) / median) * 100 if median else 0

                anomaly = Anomaly(
                    detected_at=datetime.now(timezone.utc),
                    subscription_id=subscription_id,
                    resource_id=resource_id or "",
                    service_name=service_name or "Unknown",
                    anomaly_type="cost_spike" if cost > upper_fence else "cost_drop",
                    detection_method="iqr",
                    expected_cost=Decimal(str(round(median, 6))),
                    actual_cost=Decimal(str(round(float(cost), 6))),
                    deviation_percentage=round(deviation_pct, 2),
                    deviation_amount=Decimal(str(round(abs(float(cost) - median), 6))),
                    confidence_score=round(min(distance / (3 * iqr), 1.0), 4),
                    severity=severity,
                    context={
                        "date": date.isoformat() if isinstance(date, datetime) else str(date),
                        "q1": round(q1, 2),
                        "q3": round(q3, 2),
                        "iqr": round(iqr, 2),
                        "lower_fence": round(lower_fence, 2),
                        "upper_fence": round(upper_fence, 2),
                    },
                    baseline_data={
                        "window_days": self.lookback_days,
                        "data_points": len(values),
                        "median": round(median, 2),
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_moving_average(
        self,
        dates: List[datetime],
        values: np.ndarray,
        subscription_id: str,
        service_name: Optional[str] = None,
        resource_id: Optional[str] = None,
        window: int = DEFAULT_MOVING_AVG_WINDOW,
        threshold: float = DEFAULT_MOVING_AVG_THRESHOLD,
    ) -> List[Anomaly]:
        """Flag points that deviate from their rolling average by > threshold std-devs."""
        if len(values) <= window:
            return []

        anomalies: List[Anomaly] = []

        for i in range(window, len(values)):
            window_vals = values[i - window : i]
            rolling_mean = float(np.mean(window_vals))
            rolling_std = float(np.std(window_vals))
            if rolling_std == 0:
                continue

            current = float(values[i])
            z = (current - rolling_mean) / rolling_std

            if abs(z) > threshold:
                severity = self._classify_severity(abs(z), [2.0, 3.0, 4.0])
                deviation_pct = ((current - rolling_mean) / rolling_mean) * 100 if rolling_mean else 0

                anomaly = Anomaly(
                    detected_at=datetime.now(timezone.utc),
                    subscription_id=subscription_id,
                    resource_id=resource_id or "",
                    service_name=service_name or "Unknown",
                    anomaly_type="cost_spike" if current > rolling_mean else "cost_drop",
                    detection_method="moving_average",
                    expected_cost=Decimal(str(round(rolling_mean, 6))),
                    actual_cost=Decimal(str(round(current, 6))),
                    deviation_percentage=round(deviation_pct, 2),
                    deviation_amount=Decimal(str(round(abs(current - rolling_mean), 6))),
                    confidence_score=round(min(abs(z) / 5.0, 1.0), 4),
                    severity=severity,
                    context={
                        "date": dates[i].isoformat() if isinstance(dates[i], datetime) else str(dates[i]),
                        "rolling_mean": round(rolling_mean, 2),
                        "rolling_std": round(rolling_std, 2),
                        "z_from_rolling": round(z, 4),
                        "window_size": window,
                    },
                    baseline_data={
                        "window_days": window,
                        "data_points": len(values),
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    def _detect_isolation_forest(
        self,
        dates: List[datetime],
        values: np.ndarray,
        subscription_id: str,
        service_name: Optional[str] = None,
        resource_id: Optional[str] = None,
        contamination: float = 0.05,
    ) -> List[Anomaly]:
        """Use sklearn's IsolationForest for outlier detection."""
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning("scikit-learn not installed; skipping isolation_forest detection")
            return []

        if len(values) < 20:
            return []

        X = values.reshape(-1, 1)
        model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        predictions = model.fit_predict(X)
        scores = model.decision_function(X)

        mean = float(np.mean(values))
        anomalies: List[Anomaly] = []

        for i, (date, cost, pred, score) in enumerate(zip(dates, values, predictions, scores)):
            if pred == -1:  # Anomaly
                deviation_pct = ((cost - mean) / mean) * 100 if mean else 0
                severity = self._classify_severity(abs(score), [0.1, 0.2, 0.3])

                anomaly = Anomaly(
                    detected_at=datetime.now(timezone.utc),
                    subscription_id=subscription_id,
                    resource_id=resource_id or "",
                    service_name=service_name or "Unknown",
                    anomaly_type="cost_spike" if cost > mean else "unusual_usage",
                    detection_method="isolation_forest",
                    expected_cost=Decimal(str(round(mean, 6))),
                    actual_cost=Decimal(str(round(float(cost), 6))),
                    deviation_percentage=round(deviation_pct, 2),
                    deviation_amount=Decimal(str(round(abs(float(cost) - mean), 6))),
                    confidence_score=round(1.0 - min(abs(float(score)), 1.0), 4),
                    severity=severity,
                    context={
                        "date": date.isoformat() if isinstance(date, datetime) else str(date),
                        "isolation_score": round(float(score), 6),
                        "contamination": contamination,
                    },
                    baseline_data={
                        "data_points": len(values),
                        "mean": round(mean, 2),
                    },
                )
                anomalies.append(anomaly)

        return anomalies

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def _get_detection_groups(
        self, subscription_id: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Return distinct (subscription_id, service_name) combinations."""
        query = self.db.query(
            CostRecord.subscription_id, CostRecord.service_name
        ).distinct()
        if subscription_id:
            query = query.filter(CostRecord.subscription_id == subscription_id)
        return query.all()

    def _daily_series(
        self, subscription_id: str, service_name: str
    ) -> List[Tuple[datetime, float]]:
        """Return daily cost time series for a subscription/service combo."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        rows = (
            self.db.query(
                sqla_func.date(CostRecord.date).label("day"),
                sqla_func.sum(CostRecord.cost).label("total"),
            )
            .filter(
                CostRecord.subscription_id == subscription_id,
                CostRecord.service_name == service_name,
                CostRecord.date >= cutoff,
            )
            .group_by(sqla_func.date(CostRecord.date))
            .order_by(sqla_func.date(CostRecord.date))
            .all()
        )
        return [(row.day, float(row.total)) for row in rows]

    def _daily_series_for_resource(
        self, resource_id: str
    ) -> List[Tuple[datetime, float]]:
        """Return daily cost series for a single resource."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
        rows = (
            self.db.query(
                sqla_func.date(CostRecord.date).label("day"),
                sqla_func.sum(CostRecord.cost).label("total"),
            )
            .filter(
                CostRecord.resource_id == resource_id,
                CostRecord.date >= cutoff,
            )
            .group_by(sqla_func.date(CostRecord.date))
            .order_by(sqla_func.date(CostRecord.date))
            .all()
        )
        return [(row.day, float(row.total)) for row in rows]

    def _subscription_for_resource(self, resource_id: str) -> str:
        """Look up subscription_id for a resource."""
        row = (
            self.db.query(CostRecord.subscription_id)
            .filter(CostRecord.resource_id == resource_id)
            .first()
        )
        return row[0] if row else "unknown"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(value: float, thresholds: List[float]) -> str:
        """
        Classify severity based on thresholds.

        Args:
            value: The metric value to classify.
            thresholds: [medium, high, critical] cutoffs.

        Returns:
            Severity string: low, medium, high, or critical.
        """
        if len(thresholds) != 3:
            return "medium"
        if value >= thresholds[2]:
            return "critical"
        elif value >= thresholds[1]:
            return "high"
        elif value >= thresholds[0]:
            return "medium"
        else:
            return "low"
