from __future__ import annotations

import math
import os
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from backend.schemas import (
    ClientForecastPoint,
    ClientForecastResponse,
    PortfolioForecastPoint,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_PORTFOLIO_CSV = os.path.join(_ROOT, "m3_portfolio_forecast.csv")
_INDIVIDUAL_CSV = os.path.join(_ROOT, "m3_forecasts_individual.csv")

_df_portfolio: Optional[pd.DataFrame] = None
_df_individual: Optional[pd.DataFrame] = None


def _get_portfolio() -> pd.DataFrame:
    global _df_portfolio
    if _df_portfolio is None:
        _df_portfolio = pd.read_csv(_PORTFOLIO_CSV)
    return _df_portfolio


def _get_individual() -> pd.DataFrame:
    global _df_individual
    if _df_individual is None:
        _df_individual = pd.read_csv(_INDIVIDUAL_CSV)
    return _df_individual


@router.get("/portfolio", response_model=list[PortfolioForecastPoint])
def get_portfolio_forecast() -> list[PortfolioForecastPoint]:
    df = _get_portfolio()
    result = []
    for _, row in df.iterrows():
        result.append(
            PortfolioForecastPoint(
                horizon_mois=int(row["horizon_mois"]),
                retard_moyen_prevu=round(float(row["retard_moyen_prevu"]), 3),
                retard_lower_80=round(float(row["retard_lower_80"]), 3),
                retard_upper_80=round(float(row["retard_upper_80"]), 3),
                montant_regle_total_prevu=round(float(row["montant_regle_total_prevu"]), 0),
                ratio_regle_portf_prevu=round(float(row["ratio_regle_portf_prevu"]), 4),
                encours_total_prevu=round(float(row["encours_total_prevu"]), 0),
            )
        )
    return result


@router.get("/client/{client_id}", response_model=ClientForecastResponse)
def get_client_forecast(client_id: int) -> ClientForecastResponse:
    df = _get_individual()
    sub = df[df["client_id"] == client_id]
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"Client {client_id} non trouvé dans les prévisions")

    points = []
    for _, row in sub.sort_values("horizon_mois").iterrows():
        points.append(
            ClientForecastPoint(
                horizon_mois=int(row["horizon_mois"]),
                montant_regle_pred=round(float(row["montant_regle_pred"]), 6),
                lower_80=round(float(row["lower_80"]), 6),
                upper_80=round(float(row["upper_80"]), 6),
                retard_pred=round(float(row["retard_pred"]), 3),
                risque_tendance=round(float(row["risque_tendance"]), 4),
                alerte_prev=str(row["alerte_prev"]),
            )
        )

    return ClientForecastResponse(
        client_id=client_id,
        model=str(sub.iloc[0]["model"]),
        points=points,
    )


@router.get("/alerts/top", response_model=list[dict])
def get_top_forecast_alerts(limit: int = Query(20, ge=5, le=100)) -> list[dict]:
    """Clients avec la pire tendance de risque prévue."""
    df = _get_individual()
    worst = (
        df.groupby("client_id")["risque_tendance"]
        .max()
        .reset_index()
        .rename(columns={"risque_tendance": "max_risque_tendance"})
        .sort_values("max_risque_tendance", ascending=False)
        .head(limit)
    )
    # Join alerte_prev for horizon 1
    h1 = df[df["horizon_mois"] == 1][["client_id", "alerte_prev"]].set_index("client_id")
    worst = worst.set_index("client_id").join(h1, how="left").reset_index()
    return worst.fillna("VERT").to_dict(orient="records")
