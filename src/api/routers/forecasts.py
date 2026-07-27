"""
Forecasting API Endpoints

  - /api/v1/forecasts           – latest forecasts
  - /api/v1/forecasts/run       – trigger forecasting
  - /api/v1/forecasts/accuracy  – backfill actuals & report accuracy
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.common.database import get_session
from src.forecasting.engine import ForecastingEngine
from src.models import CostForecast

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/forecasts", tags=["Forecasting"])


class ForecastItem(BaseModel):
    target_date: datetime
    forecasted_cost: float
    lower_bound: Optional[float]
    upper_bound: Optional[float]
    grain: str
    grain_value: Optional[str]
    model_used: Optional[str]
    actual_cost: Optional[float]
    accuracy: Optional[float]

    class Config:
        from_attributes = True


@router.get("", response_model=List[ForecastItem])
def get_forecasts(
    subscription_id: str = Query(..., description="Subscription ID"),
    grain: Optional[str] = Query(None, pattern="^(subscription|service|resource_type)$"),
    grain_value: Optional[str] = None,
    limit: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_session),
):
    """Retrieve the latest cost forecasts."""
    engine = ForecastingEngine(db)
    forecasts = engine.get_latest_forecasts(
        subscription_id=subscription_id,
        grain=grain,
        grain_value=grain_value,
        limit=limit,
    )
    return [
        ForecastItem(
            target_date=f.target_date,
            forecasted_cost=float(f.forecasted_cost),
            lower_bound=float(f.lower_bound) if f.lower_bound else None,
            upper_bound=float(f.upper_bound) if f.upper_bound else None,
            grain=f.grain,
            grain_value=f.grain_value,
            model_used=f.model_used,
            actual_cost=float(f.actual_cost) if f.actual_cost else None,
            accuracy=float(f.forecast_accuracy) if f.forecast_accuracy else None,
        )
        for f in forecasts
    ]


@router.post("/run")
def run_forecasting(
    subscription_id: Optional[str] = None,
    horizon_days: int = Query(90, ge=7, le=365),
    grains: Optional[str] = Query(None, description="Comma-separated grains: subscription,service,resource_type"),
    db: Session = Depends(get_session),
):
    """Trigger the forecasting engine."""
    grain_list = grains.split(",") if grains else None
    sub_list = [subscription_id] if subscription_id else None

    engine = ForecastingEngine(db, horizon_days=horizon_days)
    count = engine.forecast_all(subscription_ids=sub_list, grains=grain_list)

    return {
        "message": f"Forecasting complete. {count} forecast rows generated.",
        "horizon_days": horizon_days,
        "grains": grain_list or ["subscription", "service", "resource_type"],
    }


@router.post("/backfill-actuals")
def backfill_actuals(db: Session = Depends(get_session)):
    """Backfill actual costs on past forecasts and compute accuracy."""
    engine = ForecastingEngine(db)
    updated = engine.backfill_actuals()
    return {"message": f"Backfilled actuals for {updated} forecast rows."}
