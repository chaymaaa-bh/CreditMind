from __future__ import annotations

import json
import os

import anthropic
from dotenv import load_dotenv

from m7_agents.state import CreditMindState, RapportFinal

load_dotenv()
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"


def _decision(score: float) -> tuple[str, str]:
    if score < 30:
        return "APPROUVER", "VERT"
    elif score < 70:
        return "SURVEILLER", "ORANGE"
    else:
        return "REFUSER", "ROUGE"


def _horizon(decision: str) -> str:
    return {"APPROUVER": "6 mois", "SURVEILLER": "3 mois", "REFUSER": "1 mois"}[decision]


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "rapport_final":    None,
            "agents_completes": ["rapport"],
            "erreurs":          [f"agent_rapport: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p    = state["profil_brut"]
    r    = state["raisonnement"]
    cpl  = state.get("compliance") or {}

    score    = r["score_consensus"]
    decision, alerte = _decision(score)
    horizon  = _horizon(decision)

    facteurs_txt = "\n".join(
        f"  - {f['facteur']} (impact {float(f['score_impact']):.0%}, source: {f['source_agent']})"
        for f in r["facteurs_risque"]
    ) or "  Aucun facteur identifié"

    mock_note = (
        f"\nNOTE ANALYSE : {len(r['agents_mock'])} agent(s) en mode stub "
        f"({', '.join(r['agents_mock'])}) — confiance {r['niveau_confiance']}."
        if r["agents_mock"] else ""
    )

    extrait_m6 = (cpl.get("rapport_client") or "Non disponible")[:600]

    prompt = (
        "Tu rédiges le rapport final de risque crédit pour le chargé de compte.\n\n"
        f"CLIENT          : {state['client_id']} | {p['gouvernorat']} | {p['segment']} | {p['source']}\n"
        f"DÉCISION        : {decision} | Score global : {score:.1f}/100 | Alerte : {alerte}\n"
        f"RÉÉVALUATION    : dans {horizon}\n"
        f"{mock_note}\n\n"
        f"RAISONNEMENT :\n{r['chaine_de_pensee']}\n\n"
        f"FACTEURS DE RISQUE :\n{facteurs_txt}\n\n"
        f"RAPPORT M6 (extrait) :\n{extrait_m6}\n\n"
        "Génère UNIQUEMENT un JSON valide (sans markdown) :\n"
        "{\n"
        '  "rapport_narratif": "rapport complet en 3-4 paragraphes pour le chargé de compte",\n'
        '  "actions_recommandees": ["action 1", "action 2", "action 3"]\n'
        "}"
    )

    resp = _client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("```")).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"rapport_narratif": raw, "actions_recommandees": []}

    actions = data.get("actions_recommandees", [])
    if not isinstance(actions, list):
        actions = [str(actions)]

    sortie: RapportFinal = {
        "decision":             decision,
        "score_global":         score,
        "alerte_finale":        alerte,
        "rapport_narratif":     data.get("rapport_narratif", ""),
        "actions_recommandees": actions,
        "horizon_reevaluation": horizon,
    }
    return {"rapport_final": sortie, "agents_completes": ["rapport"]}
