"""
Génère le rapport narratif du stress-test via Claude (streaming + thinking adaptatif).
Suit le même pattern que m6_graphrag.rag_engine._synthesize().
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from .schema import IndicateursStress, ScenarioParams

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

_SYSTEM = """
Tu es le chef économiste de CreditMind, expert en risque de crédit commercial tunisien.
Tu analyses les résultats d'un stress-test Monte Carlo (N=500 simulations) sur un portefeuille
de 21 637 clients d'entreprise, scorés par un GNN GraphSAGE (module M2).

Règles de scoring :
  VERT   = score_final_m2 < 30  → faible risque
  ORANGE = score_final_m2 30–70 → surveillance
  ROUGE  = score_final_m2 > 70  → action requise

EaRS = Encours à Risque Stressé : somme des encours (montant_ttc_total) des clients
qui basculent de non-ROUGE à ROUGE sous l'effet du scénario.

Rédige en français. Vocabulaire financier précis. Conclusions actionnables.
"""

_PROMPT_TEMPLATE = """\
Résultats du stress-test CreditMind :
```json
{payload}
```

Rédige le rapport complet avec les sections suivantes :
1. **Résumé exécutif** (3–4 lignes, pour la direction des risques)
2. **Paramètres du scénario** (nature, durée, intensité, périmètre géographique et sectoriel)
3. **Impact quantitatif** (EaRS, provision, bascule ROUGE, Δ score moyen, Δ délai de paiement)
4. **Distribution des alertes avant / après** (tableau comparatif)
5. **Clients les plus exposés** (tableau top 5 avec gouvernorat, segment, scores)
6. **Intervalles de confiance** (IC 95 % EaRS — amplitude et interprétation)
7. **Actions recommandées** (provisionnement, surveillance renforcée, covenants, limites d'exposition)
"""


def generate_report(
    params: ScenarioParams,
    indicators: IndicateursStress,
    contagion: dict[str, Any] | None = None,
    model: str = MODEL,
) -> str:
    """Synthèse narrative du stress-test via Claude streaming + thinking adaptatif."""
    anth = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    payload: dict[str, Any] = {
        "scenario": {
            "description":    params["description_originale"],
            "categorie":      params["categorie"],
            "duree_mois":     params["duree_mois"],
            "intensite":      params["intensite"],
            "gouvernorats":   params["gouvernorats_cibles"],
            "segments":       params["segments_cibles"],
            "perturbations":  params["feature_deltas"],
        },
        "indicateurs": indicators,
    }
    if contagion:
        payload["contagion"] = contagion

    prompt = _PROMPT_TEMPLATE.format(
        payload=json.dumps(payload, ensure_ascii=False, indent=2)
    )

    chunks: list[str] = []
    with anth.messages.stream(
        model=model,
        max_tokens=10000,
        thinking={"type": "enabled", "budget_tokens": 5000},
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)

    return "".join(chunks)
