from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.schemas import ClientDetail, AlertResult, ShapResult, ShapFeature, CounterfactualResult, CfSuggestion
from backend.services.data_store import get_df

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

router = APIRouter(prefix="/client", tags=["client"])


def _parse_id(raw: str) -> int:
    """Accept 'R_42', 'S_1637', or '42'."""
    if "_" in raw:
        return int(raw.split("_")[-1])
    return int(raw)


def _get_client_row(int_id: int) -> dict:
    df = get_df()
    row = df[df["client_id"] == int_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Client {int_id} introuvable")
    return row.iloc[0].to_dict()


def _build_detail(int_id: int, row: dict, m8_result: dict) -> ClientDetail:
    alert_raw = m8_result.get("alert", {})
    shap_raw  = m8_result.get("shap", {})
    cf_raw    = m8_result.get("counterfactual", {})

    alert = AlertResult(
        niveau_alerte   = alert_raw.get("niveau_alerte", str(row.get("alerte", "?"))),
        triggers        = alert_raw.get("triggers", []),
        score_solvabilite = float(alert_raw.get("score_solvabilite", row.get("score_solvabilite", 0))),
        prob_defaut     = float(alert_raw.get("prob_defaut", row.get("prob_defaut", 0))),
        score_anomalie  = float(alert_raw.get("score_anomalie", row.get("score_anomalie", 0) * 100)),
        gnn_risk_score  = float(alert_raw.get("gnn_risk_score", row.get("gnn_risk_score", 0))),
        tendance_m3     = float(alert_raw.get("tendance_m3", row.get("tendance_m3", 0))),
        alerte_m5       = str(alert_raw.get("alerte_m5", row.get("alerte", "?"))),
    )

    features = [
        ShapFeature(
            feature       = f["feature"],
            label         = f["label"],
            shap_value    = float(f["shap_value"]),
            feature_value = float(f["feature_value"]),
            direction     = f["direction"],
        )
        for f in shap_raw.get("top_features", [])
    ]
    shap = ShapResult(
        base_value   = float(shap_raw.get("base_value", 0)),
        top_features = features,
    )

    suggestions = [
        CfSuggestion(
            feature        = s["feature"],
            label          = s["label"],
            valeur_actuelle= float(s["valeur_actuelle"]),
            valeur_cible   = float(s["valeur_cible"]),
            effort_pct     = float(s["effort_pct"]),
            reduction_prob = float(s["reduction_prob"]),
            nouvelle_prob  = float(s["nouvelle_prob"]),
            atteint_seuil  = bool(s["atteint_seuil"]),
        )
        for s in cf_raw.get("suggestions", [])
    ]
    cf = CounterfactualResult(
        current_prob      = float(cf_raw.get("current_prob", alert.prob_defaut)),
        target_prob       = float(cf_raw.get("target_prob", 0.30)),
        suggestions       = suggestions,
        seuil_atteignable = bool(cf_raw.get("seuil_atteignable", False)),
        note              = cf_raw.get("note"),
        message           = cf_raw.get("message"),
        method            = str(cf_raw.get("method", "manual")),
    )

    return ClientDetail(
        client_id   = int_id,
        neo4j_id    = str(row.get("neo4j_id", f"R_{int_id}")),
        gouvernorat = row.get("gouvernorat") or None,
        segment     = row.get("segment") or None,
        alert       = alert,
        shap        = shap,
        counterfactual = cf,
        narrative   = m8_result.get("narrative"),
    )


@router.get("/{raw_id}", response_model=ClientDetail)
def get_client(raw_id: str, with_narrative: bool = Query(False)) -> ClientDetail:
    try:
        int_id = _parse_id(raw_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"ID invalide : {raw_id}")

    row = _get_client_row(int_id)

    from m8_xai.api import explain
    m8_result = explain(int_id, with_narrative=with_narrative)

    if "error" in m8_result.get("alert", {}):
        raise HTTPException(status_code=404, detail=m8_result["alert"]["error"])

    return _build_detail(int_id, row, m8_result)
