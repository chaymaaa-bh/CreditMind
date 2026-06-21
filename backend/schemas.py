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


# ── Client Detail (M8) ────────────────────────────────────────────────────────

class ShapFeature(BaseModel):
    feature: str
    label: str
    shap_value: float
    feature_value: float
    direction: str  # "aggrave" | "ameliore"


class ShapResult(BaseModel):
    base_value: float
    top_features: list[ShapFeature]


class CfSuggestion(BaseModel):
    feature: str
    label: str
    valeur_actuelle: float
    valeur_cible: float
    effort_pct: float
    reduction_prob: float
    nouvelle_prob: float
    atteint_seuil: bool


class CounterfactualResult(BaseModel):
    current_prob: float
    target_prob: float
    suggestions: list[CfSuggestion]
    seuil_atteignable: bool
    note: Optional[str] = None
    message: Optional[str] = None
    method: str = "manual"


class AlertResult(BaseModel):
    niveau_alerte: str
    triggers: list[str]
    score_solvabilite: float
    prob_defaut: float
    score_anomalie: float
    gnn_risk_score: float
    tendance_m3: float
    alerte_m5: str


class ClientDetail(BaseModel):
    client_id: int
    neo4j_id: str
    gouvernorat: Optional[str] = None
    segment: Optional[str] = None
    alert: AlertResult
    shap: ShapResult
    counterfactual: CounterfactualResult
    narrative: Optional[str] = None


# ── M7 Agents ────────────────────────────────────────────────────────────────

class AgentsResult(BaseModel):
    client_id: str
    decision: str
    score_global: float
    alerte_finale: str
    rapport_narratif: str
    actions_recommandees: list[str]
    horizon_reevaluation: str
    score_consensus: float
    niveau_confiance: str
    agents_mock: list[str]
    agents_completes: list[str]
    erreurs: list[str]
    comportement: dict
    reseau: dict
    forecast: dict
    anomalies: dict
    compliance: dict


# ── M9 Stress Testing ─────────────────────────────────────────────────────────
# (response_model=dict — le schéma complet est dans StressRequest/StressResponse)


# ── M2 Network ───────────────────────────────────────────────────────────────

class NetworkNode(BaseModel):
    client_id: int
    neo4j_id: str
    alerte: str
    score_m2: float
    prob_defaut: float
    gouvernorat: Optional[str] = None
    segment: Optional[str] = None
    is_center: bool = False


class NetworkGraph(BaseModel):
    center: NetworkNode
    neighbors: list[NetworkNode]
    total_gouvernorat: int
    lien_type: str
