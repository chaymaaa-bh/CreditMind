from __future__ import annotations

from typing import Any

from . import early_warning, counterfactual, shap_explainer, narrative


def explain(client_id: int, with_narrative: bool = False, target_prob: float = 0.30) -> dict:
    """
    Full XAI pipeline for a single client.

    Returns a dict with:
      - alert        : early warning (niveau, triggers, scores)
      - shap         : local SHAP contributions (top-8 features)
      - counterfactual: actionable changes to reach target_prob
      - narrative    : natural-language explanation (only if with_narrative=True and ANTHROPIC_API_KEY set)
    """
    result: dict[str, Any] = {"client_id": client_id}

    # ── 1. Early warning ──────────────────────────────────────────────
    result["alert"] = early_warning.compute_alert(client_id)

    # ── 2. SHAP local ────────────────────────────────────────────────
    result["shap"] = shap_explainer.explain_local(client_id)

    # ── 3. Counterfactuals ───────────────────────────────────────────
    result["counterfactual"] = counterfactual.generate_counterfactuals(
        client_id, target_prob=target_prob
    )

    # ── 4. Narrative (optional) ──────────────────────────────────────
    if with_narrative and "error" not in result["alert"] and "error" not in result["shap"]:
        a = result["alert"]
        s = result["shap"]
        cf = result["counterfactual"]
        result["narrative"] = narrative.generate_narrative(
            client_id=client_id,
            score_solvabilite=a["score_solvabilite"],
            prob_defaut=a["prob_defaut"],
            niveau_alerte=a["niveau_alerte"],
            shap_top_features=s.get("top_features", []),
            counterfactual_top=cf.get("suggestions", []),
        )

    return result
