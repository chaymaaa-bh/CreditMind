from __future__ import annotations

import json
import os

import anthropic
from dotenv import load_dotenv

from m7_agents.state import CreditMindState, SortieRaisonnement

load_dotenv()
_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"

# Weights for consensus score: reseau (real) > compliance (real) > comportement > forecast > anomalies
_WEIGHTS = {
    "reseau":      0.35,
    "compliance":  0.25,
    "comportement": 0.20,
    "forecast":    0.12,
    "anomalies":   0.08,
}


def _consensus_score(state: CreditMindState) -> tuple[float, list[str]]:
    scores: list[tuple[float, float]] = []  # (score, weight)
    agents_mock: list[str] = []

    comp = state.get("comportement")
    if comp is not None:
        scores.append((comp["score"], _WEIGHTS["comportement"]))
        if comp["is_mock"]:
            agents_mock.append("comportement")

    res = state.get("reseau")
    if res is not None:
        scores.append((res["score_final_m2"], _WEIGHTS["reseau"]))

    fc = state.get("forecast")
    if fc is not None:
        scores.append((fc["probabilite_defaut_6m"] * 100, _WEIGHTS["forecast"]))
        if fc["is_mock"]:
            agents_mock.append("forecast")

    an = state.get("anomalies")
    if an is not None:
        scores.append((an["score_anomalie"], _WEIGHTS["anomalies"]))
        if an["is_mock"]:
            agents_mock.append("anomalies")

    cpl = state.get("compliance")
    if cpl is not None:
        # Pas de score numérique direct en M6 : on part du score M2 + majoration par concept
        base = state["profil_brut"]["score_final_m2"]
        adj  = min(len(cpl["concepts_declenches"]) * 5, 20)
        scores.append((min(base + adj, 100.0), _WEIGHTS["compliance"]))

    if not scores:
        return float(state["profil_brut"]["score_final_m2"]), agents_mock

    total_w   = sum(w for _, w in scores)
    consensus = sum(s * w / total_w for s, w in scores)
    return round(consensus, 2), agents_mock


def _build_context(state: CreditMindState) -> str:
    p    = state["profil_brut"]
    lines = [
        f"CLIENT : {state['client_id']} ({p['source']}) — {p['gouvernorat']} / {p['segment']}",
        f"Score M2 initial : {p['score_final_m2']:.1f} ({p['alerte_m2']})",
        "",
    ]

    comp = state.get("comportement")
    if comp:
        mock_tag = "—MOCK" if comp["is_mock"] else ""
        lines += [
            f"AGENT COMPORTEMENT (M5{mock_tag}) :",
            f"  Score : {comp['score']:.1f}  Niveau : {comp['niveau']}",
            f"  Signaux : {', '.join(comp['signaux'])}",
        ]
    else:
        lines.append("AGENT COMPORTEMENT : indisponible")

    res = state.get("reseau")
    if res:
        lines += [
            "AGENT RÉSEAU (M2—RÉEL) :",
            f"  GNN : {res['score_gnn']:.1f}  Contagion : {res['score_contagion']:.1f}  Final : {res['score_final_m2']:.1f}",
            f"  Voisins ROUGE : {res['nb_voisins_rouge']} / {res['nb_voisins_total']}",
        ]
    else:
        lines.append("AGENT RÉSEAU : indisponible")

    fc = state.get("forecast")
    if fc:
        mock_tag = "—MOCK" if fc["is_mock"] else ""
        lines += [
            f"AGENT FORECAST (M3{mock_tag}) :",
            f"  Tendance : {fc['tendance']}  Prob. défaut 6m : {fc['probabilite_defaut_6m']:.1%}",
            f"  Alerte prévue au mois : {fc['mois_alerte_prevu'] or 'aucune'}",
        ]
    else:
        lines.append("AGENT FORECAST : indisponible")

    an = state.get("anomalies")
    if an:
        mock_tag = "—MOCK" if an["is_mock"] else ""
        lines += [
            f"AGENT ANOMALIES (M4{mock_tag}) :",
            f"  Score anomalie : {an['score_anomalie']:.1f}  Outlier : {an['est_outlier']}",
            f"  Features aberrantes : {', '.join(an['features_aberrantes']) or 'aucune'}",
        ]
    else:
        lines.append("AGENT ANOMALIES : indisponible")

    cpl = state.get("compliance")
    if cpl:
        lines += [
            "AGENT COMPLIANCE (M6—RÉEL) :",
            f"  Concepts déclenchés : {', '.join(cpl['concepts_declenches']) or 'aucun'}",
            f"  Règles applicables  : {', '.join(cpl['regles_applicables']) or 'aucune'}",
        ]
    else:
        lines.append("AGENT COMPLIANCE : indisponible")

    return "\n".join(lines)


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "raisonnement":     None,
            "agents_completes": ["raisonnement"],
            "erreurs":          [f"agent_raisonnement: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    context = _build_context(state)
    score_consensus, agents_mock = _consensus_score(state)

    prompt = (
        f"{context}\n\n"
        "En tant qu'analyste de risque senior, produis une synthèse multi-agents.\n"
        "Réponds UNIQUEMENT en JSON valide (sans markdown) selon ce format :\n"
        "{\n"
        '  "chaine_de_pensee": "raisonnement structuré étape par étape (3-5 phrases)",\n'
        '  "facteurs_risque": [\n'
        '    {"facteur": "...", "score_impact": 0.0, "source_agent": "..."}\n'
        "  ],\n"
        '  "contradictions": ["divergence éventuelle entre agents, ou liste vide"]\n'
        "}"
    )

    resp = _client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("```")).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {
            "chaine_de_pensee": raw,
            "facteurs_risque":  [],
            "contradictions":   [],
        }

    n_mock = len(agents_mock)
    if n_mock == 0:
        niveau_confiance = "HAUTE"
    elif n_mock <= 2:
        niveau_confiance = "MOYENNE"
    else:
        niveau_confiance = "FAIBLE"

    sortie: SortieRaisonnement = {
        "chaine_de_pensee": data.get("chaine_de_pensee", ""),
        "facteurs_risque":  data.get("facteurs_risque", []),
        "score_consensus":  score_consensus,
        "niveau_confiance": niveau_confiance,
        "agents_mock":      agents_mock,
        "contradictions":   data.get("contradictions", []),
    }
    return {"raisonnement": sortie, "agents_completes": ["raisonnement"]}
