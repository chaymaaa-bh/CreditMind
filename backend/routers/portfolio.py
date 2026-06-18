from __future__ import annotations

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

from backend.schemas import (
    ClientListItem,
    ClientListResponse,
    GovernorateStats,
    PortfolioSummary,
    RiskDistribution,
)
from backend.services.data_store import get_df

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
def get_summary() -> PortfolioSummary:
    df = get_df()
    dist = df["alerte"].value_counts().to_dict()
    return PortfolioSummary(
        total=len(df),
        distribution=RiskDistribution(
            VERT=int(dist.get("VERT", 0)),
            JAUNE=int(dist.get("JAUNE", 0)),
            ORANGE=int(dist.get("ORANGE", 0)),
            ROUGE=int(dist.get("ROUGE", 0)),
        ),
        pct_rouge=round(dist.get("ROUGE", 0) / len(df) * 100, 2),
        pct_defaut=round(df["label_risque"].mean() * 100, 2),
        score_moyen=round(float(df["score_solvabilite"].mean()), 2),
        encours_rouge=int(dist.get("ROUGE", 0)),
    )


@router.get("/by-governorate", response_model=list[GovernorateStats])
def get_by_governorate() -> list[GovernorateStats]:
    df = get_df()
    if "gouvernorat" not in df.columns or df["gouvernorat"].isna().all():
        return []

    result: list[GovernorateStats] = []
    for gov, grp in df.groupby("gouvernorat", dropna=True):
        counts = grp["alerte"].value_counts().to_dict()
        total = len(grp)
        nb_rouge = int(counts.get("ROUGE", 0))
        result.append(
            GovernorateStats(
                gouvernorat=str(gov),
                total=total,
                nb_rouge=nb_rouge,
                nb_orange=int(counts.get("ORANGE", 0)),
                nb_jaune=int(counts.get("JAUNE", 0)),
                nb_vert=int(counts.get("VERT", 0)),
                pct_rouge=round(nb_rouge / total * 100, 2) if total else 0.0,
                avg_score=round(float(grp["score_solvabilite"].mean()), 2),
            )
        )
    result.sort(key=lambda x: x.pct_rouge, reverse=True)
    return result


@router.get("/clients", response_model=ClientListResponse)
def get_clients(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    alert: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    gouvernorat: Optional[str] = Query(None),
    sort_by: str = Query("prob_defaut"),
    sort_dir: str = Query("desc"),
) -> ClientListResponse:
    df = get_df()

    if alert:
        df = df[df["alerte"] == alert.upper()]
    if gouvernorat:
        df = df[df["gouvernorat"] == gouvernorat.upper()]
    if q:
        mask = (
            df["client_id"].astype(str).str.contains(q, case=False)
            | df["neo4j_id"].astype(str).str.contains(q, case=False)
        )
        df = df[mask]

    valid_sorts = {"prob_defaut", "score_solvabilite", "score_anomalie", "gnn_risk_score", "client_id"}
    if sort_by not in valid_sorts:
        sort_by = "prob_defaut"
    ascending = sort_dir.lower() == "asc"
    df = df.sort_values(sort_by, ascending=ascending)

    total = len(df)
    pages = max(1, math.ceil(total / limit))
    offset = (page - 1) * limit
    page_df = df.iloc[offset : offset + limit]

    items = [
        ClientListItem(
            client_id=int(row["client_id"]),
            neo4j_id=str(row.get("neo4j_id", f"R_{row['client_id']}")),
            alerte=str(row["alerte"]),
            prob_defaut=round(float(row["prob_defaut"]), 4),
            score_solvabilite=round(float(row["score_solvabilite"]), 1),
            classe_risque=str(row["classe_risque"]),
            score_anomalie=round(float(row["score_anomalie"]), 4),
            gnn_risk_score=round(float(row["gnn_risk_score"]), 4),
            gouvernorat=row.get("gouvernorat") or None,
            segment=row.get("segment") or None,
        )
        for _, row in page_df.iterrows()
    ]

    return ClientListResponse(total=total, page=page, limit=limit, pages=pages, items=items)
