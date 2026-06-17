from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).parent.parent

# Features the client can realistically improve
ACTIONABLE: dict[str, dict[str, Any]] = {
    "retard_moyen_jours":   {"dir": "decrease", "label": "Réduire le retard moyen de paiement"},
    "retard_max_jours":     {"dir": "decrease", "label": "Réduire le retard maximal"},
    "taux_retard":          {"dir": "decrease", "label": "Réduire le taux de retard"},
    "ratio_encaissement":   {"dir": "decrease", "label": "Améliorer le ratio d'encaissement"},
    "nb_reglements":        {"dir": "increase", "label": "Augmenter le nombre de règlements"},
    "montant_reg_moyen":    {"dir": "increase", "label": "Augmenter le montant moyen des règlements"},
    "retard_acceleration":  {"dir": "decrease", "label": "Stopper l'accélération des retards"},
}

_STEPS = [0.10, 0.20, 0.30, 0.50, 0.70]


def generate_counterfactuals(client_id: int, target_prob: float = 0.30) -> dict:
    """
    Return actionable feature changes that would bring prob_defaut below target_prob.
    Falls back to a manual gradient search when dice-ml is not installed.
    """
    try:
        import dice_ml  # noqa: F401
        return _dice_cf(client_id, target_prob)
    except ImportError:
        return _manual_cf(client_id, target_prob)


def _manual_cf(client_id: int, target_prob: float) -> dict:
    from . import shap_explainer as se

    se._load_artifacts()
    data = se._get_data_index()

    if client_id not in data:
        return {"error": f"client {client_id} absent du dataset"}

    x_scaled = data[client_id].copy()
    x_orig   = se._scaler.inverse_transform(x_scaled.reshape(1, -1))[0]

    current_prob = float(se._xgb_model.predict_proba(x_scaled.reshape(1, -1))[0][1])

    if current_prob <= target_prob:
        return {
            "client_id":    client_id,
            "current_prob": round(current_prob, 3),
            "target_prob":  target_prob,
            "message":      "Client déjà sous le seuil cible — aucune action requise",
            "suggestions":  [],
            "method":       "manual",
        }

    suggestions = []
    feat_cols = se._feature_cols

    for feat, meta in ACTIONABLE.items():
        if feat not in feat_cols:
            continue
        idx = feat_cols.index(feat)
        orig_val = float(x_orig[idx])

        best_prob = current_prob
        best_pct  = None
        best_new_val = orig_val

        for pct in _STEPS:
            x_mod = x_orig.copy()
            if meta["dir"] == "decrease":
                new_val = orig_val * (1 - pct)
            else:
                new_val = orig_val * (1 + pct) if orig_val > 0 else pct * 10

            x_mod[idx] = new_val
            x_scaled_mod = se._scaler.transform(x_mod.reshape(1, -1))
            prob = float(se._xgb_model.predict_proba(x_scaled_mod)[0][1])

            if prob < best_prob:
                best_prob    = prob
                best_pct     = pct
                best_new_val = new_val

        if best_pct is not None:
            suggestions.append({
                "feature":          feat,
                "label":            meta["label"],
                "valeur_actuelle":  round(orig_val, 3),
                "valeur_cible":     round(best_new_val, 3),
                "effort_pct":       int(best_pct * 100),
                "reduction_prob":   round(current_prob - best_prob, 3),
                "nouvelle_prob":    round(best_prob, 3),
                "atteint_seuil":    best_prob <= target_prob,
            })

    suggestions.sort(key=lambda s: s["reduction_prob"], reverse=True)
    seuil_atteint = any(s["atteint_seuil"] for s in suggestions)

    return {
        "client_id":     client_id,
        "current_prob":  round(current_prob, 3),
        "target_prob":   target_prob,
        "suggestions":   suggestions[:5],
        "seuil_atteignable": seuil_atteint,
        "note":          None if seuil_atteint else
                         "Le risque est principalement porté par des facteurs non actionnables (réseau/label).",
        "method":        "manual",
    }


def _dice_cf(client_id: int, target_prob: float) -> dict:
    # Placeholder — implement when dice-ml is installed (pip install dice-ml)
    return {
        "client_id":  client_id,
        "target_prob": target_prob,
        "method":      "dice",
        "message":     "dice-ml disponible mais non configuré — utiliser method='manual'",
    }
