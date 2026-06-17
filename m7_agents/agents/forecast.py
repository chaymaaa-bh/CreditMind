from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from m7_agents.state import CreditMindState, SortieForecast

_M3_PATH = Path(__file__).parent.parent.parent / "m3_forecasts_individual.csv"

# { client_id: { horizon_mois: row_dict } }
_m3_index: dict[int, dict[int, dict]] | None = None


def _get_m3_index() -> dict[int, dict[int, dict]]:
    global _m3_index
    if _m3_index is None:
        if _M3_PATH.exists():
            df = pd.read_csv(_M3_PATH)
            idx: dict[int, dict[int, dict]] = {}
            for row in df.itertuples(index=False):
                cid = int(row.client_id)
                h   = int(row.horizon_mois)
                idx.setdefault(cid, {})[h] = row._asdict()
            _m3_index = idx
        else:
            _m3_index = {}
    return _m3_index


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
    p   = state["profil_brut"]
    raw = p["client_id"]
    cid = int(raw.split("_")[-1]) if "_" in raw else int(raw)
    m3  = _get_m3_index().get(cid)

    if m3 is not None:
        # ── Chemin M3 : prévisions réelles N-HiTS ──────────────────────────────
        s0 = float(p["score_final_m2"])

        predictions: dict[str, float] = {}
        mois_alerte: int | None       = None

        for h in range(1, 7):
            if h in m3:
                # risque_tendance : delta de risque prévu depuis le score M2 de base
                delta   = float(m3[h]["risque_tendance"])
                score_h = max(0.0, min(100.0, s0 + delta))
            else:
                score_h = s0
            predictions[f"m{h}"] = round(score_h, 2)
            if mois_alerte is None and score_h >= 70:
                mois_alerte = h

        # tendance : direction moyenne de risque_tendance sur les 6 mois
        deltas = [float(m3[h]["risque_tendance"]) for h in range(1, 7) if h in m3]
        avg    = sum(deltas) / len(deltas) if deltas else 0.0
        if avg > 2.0:
            tendance = "HAUSSE"
        elif avg < -2.0:
            tendance = "BAISSE"
        else:
            tendance = "STABLE"

        # mois_alerte_prevu : premier mois où alerte_prev != VERT (si pas déjà trouvé via score)
        if mois_alerte is None:
            for h in range(1, 7):
                if h in m3 and str(m3[h].get("alerte_prev", "VERT")) != "VERT":
                    mois_alerte = h
                    break

        # prob_defaut_6m : sigmoid centré sur 50 appliqué au score projeté à 6 mois
        s6   = predictions.get("m6", s0)
        prob = round(1 / (1 + math.exp(-0.1 * (s6 - 50))), 3)

        is_mock = False

    else:
        # ── Fallback stub : client absent du CSV M3 ────────────────────────────
        s0 = p["score_final_m2"]

        if p["taux_retard"] > 0.5 or p["nb_reglements"] == 0:
            tendance = "HAUSSE"
            rate     = 1.06
        elif p["taux_retard"] < 0.1 and p["ratio_encaissement"] > 0.8:
            tendance = "BAISSE"
            rate     = 0.95
        else:
            tendance = "STABLE"
            rate     = 1.01

        predictions = {}
        mois_alerte = None
        for m in range(1, 7):
            s = min(s0 * (rate ** m), 100.0)
            predictions[f"m{m}"] = round(s, 2)
            if mois_alerte is None and s >= 70:
                mois_alerte = m

        s6   = predictions["m6"]
        prob = round(1 / (1 + math.exp(-0.1 * (s6 - 50))), 3)
        is_mock = True

    sortie: SortieForecast = {
        "predictions_score":     predictions,
        "tendance":              tendance,
        "probabilite_defaut_6m": prob,
        "mois_alerte_prevu":     mois_alerte,
        "is_mock":               is_mock,
    }
    return {"forecast": sortie, "agents_completes": ["forecast"]}
