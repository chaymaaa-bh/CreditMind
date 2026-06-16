"""
Moteur Monte Carlo pour le stress-test crédit CreditMind M9.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from m7_agents.agents._neo4j import run_cypher
from .schema import ScenarioParams

logger = logging.getLogger(__name__)

# Sensibilités : Δscore_final_m2 par unité de Δfeature.
# Calibrées empiriquement sur les règles M1 (R01–R03) et les seuils M2 (R04–R05).
# score_final_m2 = 0.7 × score_gnn + 0.3 × score_contagion (R06).
SENSITIVITES: dict[str, float] = {
    "taux_retard":        60.0,   # +1.0 → +60 pts  (R03 : taux > 0.5 → label=1)
    "ratio_encaissement": -40.0,  # −1.0 → +40 pts  (ratio faible = encaissement insuffisant)
    "retard_moyen_jours":  0.15,  # +1 j → +0.15 pt
    "retard_max_jours":    0.08,  # +1 j → +0.08 pt (R02 : max > 30 j → label=1)
    "nb_retards_graves":   2.0,   # +1   → +2 pts
}


def _rescore(baseline: dict[str, Any], stressed: dict[str, Any]) -> tuple[float, str]:
    """
    Approximation linéaire du score_final_m2 après perturbation des features.

    Formule : score_stressé = clip(score_baseline + Σ(sensibilité_i × Δfeature_i), 0, 100)

    Les sensibilités sont calibrées empiriquement sur les règles M1 (R01–R03) et les
    seuils de classification M2 (VERT <30 / ORANGE 30–70 / ROUGE >70).

    APPROXIMATION — remplaçable par le modèle GNN M2 si exporté par Rahma.
    Interface stable : (baseline: dict, stressed: dict) -> (float, str)
    Les deux dicts doivent contenir les clés de SENSITIVITES et "score_final_m2".
    """
    delta_score = sum(
        SENSITIVITES[f] * (stressed.get(f, 0.0) - baseline.get(f, 0.0))
        for f in SENSITIVITES
        if f in baseline
    )
    score = float(np.clip(float(baseline["score_final_m2"]) + delta_score, 0.0, 100.0))
    alerte = "VERT" if score < 30 else ("ORANGE" if score < 70 else "ROUGE")
    return score, alerte


def load_clients(params: ScenarioParams) -> list[dict[str, Any]]:
    """Charge les features des clients ciblés depuis Neo4j.

    Utilise MATCH (pas OPTIONAL MATCH) pour les dimensions filtrées : OPTIONAL MATCH
    avec WHERE laisse passer toutes les lignes quand la relation est absente (g=NULL).
    """
    cypher_params: dict[str, Any] = {}

    # Gouvernorat : MATCH régulier si filtre, sinon OPTIONAL
    if params["gouvernorats_cibles"]:
        gouv_clause = "MATCH (c)-[:SITUE_DANS]->(g:Gouvernorat) WHERE g.nom IN $gouvernorats"
        cypher_params["gouvernorats"] = params["gouvernorats_cibles"]
    else:
        gouv_clause = "OPTIONAL MATCH (c)-[:SITUE_DANS]->(g:Gouvernorat)"

    # Segment : idem
    if params["segments_cibles"]:
        seg_clause = "MATCH (c)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient) WHERE s.nom IN $segments"
        cypher_params["segments"] = params["segments_cibles"]
    else:
        seg_clause = "OPTIONAL MATCH (c)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient)"

    cypher = f"""
    MATCH (c:Client)
    {gouv_clause}
    {seg_clause}
    RETURN
      c.client_id          AS client_id,
      c.source             AS source,
      c.alerte             AS alerte,
      c.score_final_m2     AS score_final_m2,
      c.nb_reglements      AS nb_reglements,
      c.retard_moyen_jours AS retard_moyen_jours,
      c.retard_max_jours   AS retard_max_jours,
      c.nb_retards_graves  AS nb_retards_graves,
      c.taux_retard        AS taux_retard,
      c.ratio_encaissement AS ratio_encaissement,
      c.montant_ttc_moyen  AS montant_ttc_moyen,
      c.montant_ttc_total  AS montant_ttc_total,
      c.nb_factures        AS nb_factures,
      c.anciennete_jours   AS anciennete_jours,
      g.nom                AS gouvernorat,
      s.nom                AS segment
    """

    rows = run_cypher(cypher, cypher_params)

    cleaned: list[dict[str, Any]] = []
    for r in rows:
        cleaned.append({
            "client_id":          r.get("client_id") or "",
            "source":             r.get("source") or "INCONNU",
            "alerte":             r.get("alerte") or "INCONNU",
            "score_final_m2":     float(r.get("score_final_m2") or 0),
            "nb_reglements":      int(r.get("nb_reglements") or 0),
            "retard_moyen_jours": float(r.get("retard_moyen_jours") or 0),
            "retard_max_jours":   float(r.get("retard_max_jours") or 0),
            "nb_retards_graves":  int(r.get("nb_retards_graves") or 0),
            "taux_retard":        float(r.get("taux_retard") or 0),
            "ratio_encaissement": float(r.get("ratio_encaissement") or 0),
            "montant_ttc_moyen":  float(r.get("montant_ttc_moyen") or 0),
            "montant_ttc_total":  float(r.get("montant_ttc_total") or 0),
            "nb_factures":        int(r.get("nb_factures") or 0),
            "anciennete_jours":   int(r.get("anciennete_jours") or 0),
            "gouvernorat":        r.get("gouvernorat") or "INCONNU",
            "segment":            r.get("segment") or "INCONNU",
        })

    logger.info("%d clients chargés depuis Neo4j", len(cleaned))
    return cleaned


def run_simulation(
    clients: list[dict[str, Any]],
    params: ScenarioParams,
    n_simulations: int = 500,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Simulation Monte Carlo vectorisée : n_simulations runs × n_clients.

    Pour chaque run, les features de chaque client sont perturbées en tirant un
    delta aléatoire N(delta_value, std_pct × |delta_value|) par FeatureDelta.
    Le re-scoring utilise le même noyau que _rescore() mais vectorisé en numpy.

    Returns:
        baseline_scores   : np.ndarray (n_clients,)
        score_matrix      : np.ndarray (n_simulations, n_clients)
        baseline_retard   : np.ndarray (n_clients,)  retard_moyen_jours baseline
        retard_matrix     : np.ndarray (n_simulations, n_clients)  retard stressé
        baseline_encours  : np.ndarray (n_clients,)  montant_ttc_total
        n_clients         : int
    """
    n_clients = len(clients)
    if n_clients == 0:
        raise ValueError("Aucun client chargé. Vérifiez les filtres gouvernorat/segment.")

    rng = np.random.default_rng(seed)

    # ── Vecteurs baseline ──────────────────────────────────────────────────────
    baseline_scores  = np.array([c["score_final_m2"]     for c in clients], dtype=float)
    baseline_retard  = np.array([c["retard_moyen_jours"] for c in clients], dtype=float)
    baseline_encours = np.array([c["montant_ttc_total"]  for c in clients], dtype=float)

    # Matrices de features : (n_simulations, n_clients), initialisées au baseline
    feat: dict[str, np.ndarray] = {
        f: np.tile(np.array([c[f] for c in clients], dtype=float), (n_simulations, 1))
        for f in SENSITIVITES
    }

    # ── Application des perturbations ──────────────────────────────────────────
    for delta in params["feature_deltas"]:
        f = delta["feature"]
        if f not in feat:
            continue
        std = delta["std_pct"] * abs(delta["delta_value"])
        noise = rng.normal(delta["delta_value"], max(std, 1e-12), (n_simulations, n_clients))
        if delta["delta_type"] == "multiplicatif":
            feat[f] *= (1.0 + noise)
        else:
            feat[f] += noise

    # Clamp : ratios en [0, 1], délais et compteurs ≥ 0
    for f in ("taux_retard", "ratio_encaissement", "ratio_avoirs"):
        if f in feat:
            feat[f] = np.clip(feat[f], 0.0, 1.0)
    for f in ("retard_moyen_jours", "retard_max_jours", "nb_retards_graves"):
        if f in feat:
            feat[f] = np.maximum(feat[f], 0.0)

    # ── Re-scoring vectorisé (équivalent numpy de _rescore) ───────────────────
    delta_score_matrix = np.zeros((n_simulations, n_clients))
    for f, sensitivity in SENSITIVITES.items():
        baseline_f = np.array([c[f] for c in clients], dtype=float)
        delta_score_matrix += sensitivity * (feat[f] - baseline_f)

    score_matrix = np.clip(baseline_scores + delta_score_matrix, 0.0, 100.0)

    return {
        "baseline_scores":  baseline_scores,
        "score_matrix":     score_matrix,
        "baseline_retard":  baseline_retard,
        "retard_matrix":    feat.get("retard_moyen_jours",
                                     np.tile(baseline_retard, (n_simulations, 1))),
        "baseline_encours": baseline_encours,
        "n_clients":        n_clients,
    }
