"""
Traduit une description en langage naturel en ScenarioParams structurés
via Claude tool_use (structured output).
"""
from __future__ import annotations

import logging
import os

import anthropic
from dotenv import load_dotenv

from .schema import FeatureDelta, ScenarioParams

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

_TOOL: dict = {
    "name": "definir_scenario_stress",
    "description": (
        "Traduit un scénario de crise macroéconomique ou sectorielle en paramètres "
        "structurés pour la simulation Monte Carlo de stress-test crédit."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "categorie": {
                "type": "string",
                "enum": [
                    "inflation_couts",
                    "contraction_credit",
                    "risque_regional",
                    "choc_change",
                    "contagion",
                ],
                "description": "Catégorie principale du choc.",
            },
            "duree_mois": {
                "type": "integer",
                "minimum": 1,
                "maximum": 24,
                "description": "Durée estimée du choc en mois.",
            },
            "intensite": {
                "type": "string",
                "enum": ["FAIBLE", "MODERE", "SEVERE"],
                "description": "Intensité globale : FAIBLE (<15 % choc), MODERE (15–35 %), SEVERE (>35 %).",
            },
            "gouvernorats_cibles": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Gouvernorats tunisiens ciblés, en MAJUSCULES tels que stockés en Neo4j. "
                    "Valeurs possibles : SFAX, TUNIS, SOUSSE, MONASTIR, ARIANA, BIZERTE, NABEUL, "
                    "GABES, GAFSA, KASSERINE, KAIROUAN, MAHDIA, MEDENINE, TATAOUINE, SIDI_BOUZID, "
                    "SILIANA, JENDOUBA, BEN_AROUS, MANOUBA, BEJA, KEF, ZAGHOUAN, KEBILI, TOZEUR, EXPORT. "
                    "Tableau vide = tout le portefeuille."
                ),
            },
            "segments_cibles": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Segments clients ciblés (ex: GRN, OUTSIDER, CHALLENGERA, EXPORT). "
                    "Tableau vide = tous les segments."
                ),
            },
            "feature_deltas": {
                "type": "array",
                "description": (
                    "Perturbations appliquées aux features de chaque client. "
                    "delta_type='multiplicatif' : feature_stressée = feature × (1 + delta_value). "
                    "delta_type='additif'       : feature_stressée = feature + delta_value. "
                    "std_pct : incertitude relative du delta pour Monte Carlo (0.10–0.30 typiquement)."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "feature": {
                            "type": "string",
                            "enum": [
                                "retard_moyen_jours",
                                "retard_max_jours",
                                "taux_retard",
                                "ratio_encaissement",
                                "nb_retards_graves",
                                "montant_ttc_moyen",
                                "montant_ttc_total",
                                "ratio_avoirs",
                            ],
                        },
                        "delta_type": {"type": "string", "enum": ["multiplicatif", "additif"]},
                        "delta_value": {"type": "number"},
                        "std_pct": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                    "required": ["feature", "delta_type", "delta_value", "std_pct"],
                },
            },
        },
        "required": [
            "categorie",
            "duree_mois",
            "intensite",
            "gouvernorats_cibles",
            "segments_cibles",
            "feature_deltas",
        ],
    },
}

_SYSTEM = """
Tu es expert en risque de crédit commercial tunisien pour CreditMind.
Traduis des descriptions de scénarios de crise en paramètres structurés pour simulation Monte Carlo.

Portefeuille : 21 637 clients d'entreprise, scorés GraphSAGE M2.
  VERT   = score_final_m2 < 30  → faible risque
  ORANGE = score_final_m2 30–70 → surveillance
  ROUGE  = score_final_m2 > 70  → risque élevé

Features perturbables (nœud :Client Neo4j) :
  retard_moyen_jours  (float, jours) — délai moyen de paiement
  retard_max_jours    (float, jours) — retard maximal observé
  taux_retard         (float, 0–1)   — fraction de paiements en retard
  ratio_encaissement  (float, 0–1)   — montant réglé / facturé (inverse du risque)
  nb_retards_graves   (int)          — nombre de retards > 30 jours
  montant_ttc_moyen   (float, TND)   — montant moyen des factures
  montant_ttc_total   (float, TND)   — encours total client
  ratio_avoirs        (float, 0–1)   — ratio avoirs/factures

Mappings standards (à adapter à l'intensité) :
  inflation_couts    → retard_moyen_jours ×(1+0.30–0.60), taux_retard +(0.10–0.20),
                       ratio_encaissement ×(1−0.15–0.30)
  contraction_credit → ratio_encaissement ×(1−0.20–0.40), montant_ttc_moyen ×(1−0.10–0.20)
  risque_regional    → [cibler gouvernorats] retard_moyen_jours ×(1+0.30–0.80),
                       ratio_encaissement ×(1−0.20–0.50), taux_retard +(0.10–0.30)
  choc_change        → montant_ttc_moyen ×(1+0.10–0.30), retard_moyen_jours ×(1+0.20–0.40)
  contagion          → taux_retard +(0.20–0.40), ratio_encaissement ×(1−0.30–0.50)
"""


def parse_scenario(description: str, model: str = MODEL) -> ScenarioParams:
    """Traduit une description en langage naturel en ScenarioParams via Claude tool_use."""
    anth = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = anth.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "definir_scenario_stress"},
        messages=[{"role": "user", "content": description}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "definir_scenario_stress":
            raw = block.input
            return ScenarioParams(
                description_originale=description,
                categorie=raw["categorie"],
                duree_mois=raw["duree_mois"],
                gouvernorats_cibles=raw["gouvernorats_cibles"],
                segments_cibles=raw["segments_cibles"],
                feature_deltas=[FeatureDelta(**d) for d in raw["feature_deltas"]],
                intensite=raw["intensite"],
            )

    raise RuntimeError("Claude n'a pas retourné de paramètres de scénario (tool_use absent).")
