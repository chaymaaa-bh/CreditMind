from __future__ import annotations

import math
import os
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

from backend.schemas import AnomalyAlert, AnomalyListResponse, AnomalySummary

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_ALERTS_CSV = os.path.join(_ROOT, "m4_anomaly_alerts.csv")

_df_alerts: Optional[pd.DataFrame] = None


def _get_alerts() -> pd.DataFrame:
    global _df_alerts
    if _df_alerts is None:
        _df_alerts = pd.read_csv(_ALERTS_CSV)
    return _df_alerts


@router.get("/summary", response_model=AnomalySummary)
def get_anomaly_summary() -> AnomalySummary:
    df = _get_alerts()
    dist = df["alerte"].value_counts().to_dict()
    return AnomalySummary(
        total=len(df),
        nb_rouge=int(dist.get("ROUGE", 0)),
        nb_orange=int(dist.get("ORANGE", 0)),
        nb_jaune=int(dist.get("JAUNE", 0)),
        avg_score_final=round(float(df["score_anomalie_final"].mean()), 4),
        avg_score_if=round(float(df["score_anomalie_if"].mean()), 4),
        avg_score_lstm=round(float(df["score_anomalie_lstm"].mean()), 4),
    )


@router.get("/list", response_model=AnomalyListResponse)
def list_anomalies(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    alerte: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort_by: str = Query("score_anomalie_final"),
    sort_dir: str = Query("desc"),
) -> AnomalyListResponse:
    df = _get_alerts()

    if alerte:
        df = df[df["alerte"] == alerte.upper()]
    if q:
        df = df[df["client_id"].astype(str).str.contains(q)]

    valid_sorts = {"score_anomalie_final", "score_anomalie_if", "score_anomalie_lstm", "client_id", "retard_moyen_jours"}
    if sort_by not in valid_sorts:
        sort_by = "score_anomalie_final"
    ascending = sort_dir.lower() == "asc"
    df = df.sort_values(sort_by, ascending=ascending)

    total = len(df)
    pages = max(1, math.ceil(total / limit))
    offset = (page - 1) * limit
    page_df = df.iloc[offset: offset + limit]

    items = [
        AnomalyAlert(
            client_id=int(row["client_id"]),
            alerte=str(row["alerte"]),
            score_anomalie_final=round(float(row["score_anomalie_final"]), 4),
            score_anomalie_if=round(float(row["score_anomalie_if"]), 4),
            score_anomalie_lstm=round(float(row["score_anomalie_lstm"]), 4),
            score_anomalie_river=round(float(row["score_anomalie_river"]), 4),
            nb_votes=int(row["nb_votes"]),
            raison_principale=str(row["raison_principale"]),
            retard_moyen_jours=round(float(row["retard_moyen_jours"]), 3),
            taux_retard=round(float(row["taux_retard"]), 4),
            ratio_encaissement=round(float(row["ratio_encaissement"]), 4),
            montant_ttc_moyen=round(float(row["montant_ttc_moyen"]), 2),
        )
        for _, row in page_df.iterrows()
    ]

    return AnomalyListResponse(total=total, page=page, limit=limit, pages=pages, items=items)
