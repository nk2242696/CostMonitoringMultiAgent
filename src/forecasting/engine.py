"""
Cost Forecasting Engine

Uses Facebook Prophet to generate cost forecasts at multiple grains:
  - subscription level
  - service level
  - resource_type level

Populates the cost_forecasts table with predictions and confidence intervals.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import func as sqla_func, cast, Date
from sqlalchemy.orm import Session

from src.models import CostForecast, CostRecord

logger = logging.getLogger(__name__)


class ForecastingEngine:
    """
    Time-series forecasting on Azure cost data.

    Steps:
      1. Pull historical daily costs from cost_records
      2. Prepare Prophet-compatible DataFrame (ds, y)
      3. Fit model, predict N periods ahead
      4. Store forecasts in cost_forecasts table
    """

    def __init__(self, db: Session, horizon_days: int = 90, confidence: float = 0.95):
        self.db = db
        self.horizon_days = horizon_days
        self.confidence = confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def forecast_all(
        self,
        subscription_ids: Optional[List[str]] = None,
        grains: Optional[List[str]] = None,
    ) -> int:
        """
        Run forecasting for given subscriptions and grains.

        Args:
            subscription_ids: List of subscription IDs (None = all found in DB).
            grains:           List of grains to forecast. Options:
                              "subscription", "service", "resource_type".
                              None = all three.

        Returns:
            Number of forecast rows inserted.
        """
        grains = grains or ["subscription", "service", "resource_type"]

        if not subscription_ids:
            subscription_ids = [
                row[0]
                for row in self.db.query(CostRecord.subscription_id).distinct().all()
            ]

        total = 0
        for sub_id in subscription_ids:
            for grain in grains:
                try:
                    n = self._forecast_grain(sub_id, grain)
                    total += n
                except Exception:
                    logger.exception(
                        "Forecast failed for sub=%s grain=%s", sub_id, grain
                    )
        return total

    # ------------------------------------------------------------------
    # Grain-level forecasting
    # ------------------------------------------------------------------

    def _forecast_grain(self, subscription_id: str, grain: str) -> int:
        """Forecast a single grain for one subscription."""
        if grain == "subscription":
            return self._forecast_series(
                subscription_id=subscription_id,
                grain="subscription",
                grain_value=subscription_id,
            )

        # For service / resource_type, iterate over distinct values
        if grain == "service":
            col = CostRecord.service_name
        elif grain == "resource_type":
            col = CostRecord.resource_type
        else:
            raise ValueError(f"Unknown grain: {grain}")

        values = (
            self.db.query(col)
            .filter(CostRecord.subscription_id == subscription_id)
            .distinct()
            .all()
        )

        total = 0
        for (val,) in values:
            try:
                total += self._forecast_series(
                    subscription_id=subscription_id,
                    grain=grain,
                    grain_value=val,
                )
            except Exception:
                logger.warning("Skipped forecast for %s=%s", grain, val)
        return total

    def _forecast_series(
        self,
        subscription_id: str,
        grain: str,
        grain_value: str,
    ) -> int:
        """Fit Prophet on one time-series and persist forecasts."""
        df = self._load_history(subscription_id, grain, grain_value)

        if df.empty or len(df) < 14:
            logger.info(
                "Not enough data to forecast %s=%s (rows=%d)",
                grain,
                grain_value,
                len(df),
            )
            return 0

        # Lazy import Prophet — it's heavy
        try:
            from prophet import Prophet
        except ImportError:
            logger.error("prophet not installed — pip install prophet")
            return self._fallback_linear_forecast(
                df, subscription_id, grain, grain_value
            )

        model = Prophet(
            interval_width=self.confidence,
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True if len(df) > 365 else False,
            changepoint_prior_scale=0.05,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=self.horizon_days)
        forecast = model.predict(future)

        # Only take *future* rows
        last_actual = df["ds"].max()
        future_rows = forecast[forecast["ds"] > last_actual]

        count = 0
        now = datetime.utcnow()
        for _, row in future_rows.iterrows():
            fc = CostForecast(
                forecast_date=now,
                target_date=row["ds"].to_pydatetime(),
                subscription_id=subscription_id,
                grain=grain,
                grain_value=grain_value,
                forecast_period="daily",
                forecasted_cost=max(float(row["yhat"]), 0),
                lower_bound=max(float(row["yhat_lower"]), 0),
                upper_bound=max(float(row["yhat_upper"]), 0),
                confidence_level=self.confidence,
                model_used="prophet",
                model_parameters={
                    "changepoint_prior_scale": 0.05,
                    "history_days": len(df),
                },
            )
            self.db.add(fc)
            count += 1

        self.db.commit()
        logger.info(
            "Forecasted %d days for %s=%s (sub=%s)",
            count,
            grain,
            grain_value,
            subscription_id,
        )
        return count

    # ------------------------------------------------------------------
    # Fallback: simple linear projection
    # ------------------------------------------------------------------

    def _fallback_linear_forecast(
        self,
        df: pd.DataFrame,
        subscription_id: str,
        grain: str,
        grain_value: str,
    ) -> int:
        """Simple linear regression fallback when Prophet is unavailable."""
        from sklearn.linear_model import LinearRegression

        df = df.copy()
        df["x"] = (df["ds"] - df["ds"].min()).dt.days.astype(float)
        X = df[["x"]].values
        y = df["y"].values

        model = LinearRegression()
        model.fit(X, y)

        residuals = y - model.predict(X)
        std = float(np.std(residuals))

        last_day = df["ds"].max()
        now = datetime.utcnow()
        count = 0

        for d in range(1, self.horizon_days + 1):
            target_date = last_day + timedelta(days=d)
            x_val = (target_date - df["ds"].min()).days
            yhat = float(model.predict([[x_val]])[0])

            fc = CostForecast(
                forecast_date=now,
                target_date=target_date,
                subscription_id=subscription_id,
                grain=grain,
                grain_value=grain_value,
                forecast_period="daily",
                forecasted_cost=max(yhat, 0),
                lower_bound=max(yhat - 1.96 * std, 0),
                upper_bound=max(yhat + 1.96 * std, 0),
                confidence_level=self.confidence,
                model_used="linear_regression",
                model_parameters={"coef": float(model.coef_[0]), "intercept": float(model.intercept_)},
            )
            self.db.add(fc)
            count += 1

        self.db.commit()
        logger.info("Linear forecast: %d days for %s=%s", count, grain, grain_value)
        return count

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_history(
        self,
        subscription_id: str,
        grain: str,
        grain_value: str,
    ) -> pd.DataFrame:
        """Load historical daily cost as Prophet-compatible DataFrame."""
        query = self.db.query(
            cast(CostRecord.date, Date).label("ds"),
            sqla_func.sum(CostRecord.cost).label("y"),
        ).filter(CostRecord.subscription_id == subscription_id)

        if grain == "service":
            query = query.filter(CostRecord.service_name == grain_value)
        elif grain == "resource_type":
            query = query.filter(CostRecord.resource_type == grain_value)

        query = query.group_by("ds").order_by("ds")
        rows = query.all()

        if not rows:
            return pd.DataFrame(columns=["ds", "y"])

        df = pd.DataFrame(rows, columns=["ds", "y"])
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = df["y"].astype(float)
        return df

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_latest_forecasts(
        self,
        subscription_id: str,
        grain: Optional[str] = None,
        grain_value: Optional[str] = None,
        limit: int = 90,
    ) -> List[CostForecast]:
        """Retrieve the latest forecasts for display / API."""
        query = (
            self.db.query(CostForecast)
            .filter(CostForecast.subscription_id == subscription_id)
            .order_by(CostForecast.target_date.asc())
        )
        if grain:
            query = query.filter(CostForecast.grain == grain)
        if grain_value:
            query = query.filter(CostForecast.grain_value == grain_value)

        return query.limit(limit).all()

    def backfill_actuals(self) -> int:
        """
        For past forecast rows whose target_date has passed, fill in
        actual_cost from cost_records and compute accuracy.
        """
        pending = (
            self.db.query(CostForecast)
            .filter(
                CostForecast.actual_cost.is_(None),
                CostForecast.target_date < datetime.utcnow(),
            )
            .all()
        )

        updated = 0
        for fc in pending:
            actual = self._get_actual_cost(
                fc.subscription_id,
                fc.grain,
                fc.grain_value,
                fc.target_date,
            )
            if actual is not None:
                fc.actual_cost = actual
                predicted = float(fc.forecasted_cost)
                if predicted > 0:
                    fc.forecast_accuracy = 1 - abs(actual - predicted) / predicted
                updated += 1

        self.db.commit()
        logger.info("Backfilled actuals for %d forecast rows", updated)
        return updated

    def _get_actual_cost(
        self,
        subscription_id: str,
        grain: str,
        grain_value: str,
        target_date: datetime,
    ) -> Optional[float]:
        query = self.db.query(sqla_func.sum(CostRecord.cost)).filter(
            CostRecord.subscription_id == subscription_id,
            cast(CostRecord.date, Date) == target_date.date(),
        )
        if grain == "service":
            query = query.filter(CostRecord.service_name == grain_value)
        elif grain == "resource_type":
            query = query.filter(CostRecord.resource_type == grain_value)

        val = query.scalar()
        return float(val) if val is not None else None
