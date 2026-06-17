from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_CLIENT = None


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        import anthropic
        _CLIENT = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _CLIENT


def generate_narrative(
    client_id: int,
    score_solvabilite: float,
    prob_defaut: float,
    niveau_alerte: str,
    shap_top_features: list[dict],
    counterfactual_top: list[dict],
) -> dict:
    """
    Generate a concise natural-language explanation for an analyst.
    Returns {"text": str, "model": str} or {"error": str}.
    """
    try:
        return _call_claude(client_id, score_solvabilite, prob_defaut,
                            niveau_alerte, shap_top_features, counterfactual_top)
    except Exception as exc:
        return {"error": str(exc)}


def _call_claude(
    client_id: int,
    score: float,
    prob: float,
    alerte: str,
    top_features: list[dict],
    suggestions: list[dict],
) -> dict:
    aggravants  = [f for f in top_features if f["direction"] == "aggrave"][:3]
    ameliorants = [f for f in top_features if f["direction"] == "ameliore"][:2]

    def fmt_feat(f: dict) -> str:
        return f"  • {f['label']} : impact {f['shap_value']:+.3f} (valeur = {f['feature_value']:.2f})"

    aggr_lines = "\n".join(fmt_feat(f) for f in aggravants)  or "  aucun"
    amel_lines = "\n".join(fmt_feat(f) for f in ameliorants) or "  aucun"

    sugg_lines = "\n".join(
        f"  • {s['label']} : réduire la prob. défaut de {s['reduction_prob']:.3f} "
        f"(effort ~{s['effort_pct']}%)"
        for s in suggestions[:3]
    ) or "  aucune suggestion disponible"

    prompt = f"""Tu es un analyste crédit senior. Explique en 4 à 6 phrases claires, en français, pourquoi le client {client_id} a ce profil de risque et quelles actions sont prioritaires.

Données :
- Score solvabilité : {score:.1f}/100
- Probabilité de défaut : {prob:.1%}
- Niveau d'alerte : {alerte}

Facteurs aggravants (SHAP) :
{aggr_lines}

Facteurs protecteurs (SHAP) :
{amel_lines}

Actions recommandées :
{sugg_lines}

Réponds uniquement avec l'explication en langage naturel, sans titre ni liste à puces. Sois précis et actionnable."""

    client = _get_client()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return {
        "text":  resp.content[0].text.strip(),
        "model": resp.model,
    }
