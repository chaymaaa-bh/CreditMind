from __future__ import annotations

import math

from m7_agents.state import CreditMindState, SortieForecast


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "forecast":         None,
            "agents_completes": ["forecast"],
            "erreurs":          [f"agent_forecast: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p  = state["profil_brut"]
    s0 = p["score_final_m2"]

    # Stub: trend inferred from behavioral signals
    if p["taux_retard"] > 0.5 or p["nb_reglements"] == 0:
        tendance = "HAUSSE"
        rate     = 1.06
    elif p["taux_retard"] < 0.1 and p["ratio_encaissement"] > 0.8:
        tendance = "BAISSE"
        rate     = 0.95
    else:
        tendance = "STABLE"
        rate     = 1.01

    predictions: dict[str, float] = {}
    mois_alerte: int | None = None
    for m in range(1, 7):
        s = min(s0 * (rate ** m), 100.0)
        predictions[f"m{m}"] = round(s, 2)
        if mois_alerte is None and s >= 70:
            mois_alerte = m

    # Probability of default via sigmoid centred on 50
    s6   = predictions["m6"]
    prob = round(1 / (1 + math.exp(-0.1 * (s6 - 50))), 3)

    sortie: SortieForecast = {
        "predictions_score":     predictions,
        "tendance":              tendance,
        "probabilite_defaut_6m": prob,
        "mois_alerte_prevu":     mois_alerte,
        "is_mock":               True,
    }
    return {"forecast": sortie, "agents_completes": ["forecast"]}
