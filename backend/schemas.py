from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class RiskDistribution(BaseModel):
    VERT: int
    JAUNE: int
    ORANGE: int
    ROUGE: int


class PortfolioSummary(BaseModel):
    total: int
    distribution: RiskDistribution
    pct_rouge: float
    pct_defaut: float
    score_moyen: float
    encours_rouge: int  # nombre de clients ROUGE


class GovernorateStats(BaseModel):
    gouvernorat: str
    total: int
    nb_rouge: int
    nb_orange: int
    nb_jaune: int
    nb_vert: int
    pct_rouge: float
    avg_score: float


class ClientListItem(BaseModel):
    client_id: int
    neo4j_id: str
    alerte: str
    prob_defaut: float
    score_solvabilite: float
    classe_risque: str
    score_anomalie: float
    gnn_risk_score: float
    gouvernorat: Optional[str] = None
    segment: Optional[str] = None


class ClientListResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    items: list[ClientListItem]
