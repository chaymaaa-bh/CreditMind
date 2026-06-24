from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from m7_agents.agents._neo4j import run_cypher
from m7_agents.state import CreditMindState, ProfilBrut

_ROOT = Path(__file__).parent.parent.parent

_CYPHER = """
MATCH (c:Client {client_id: $cid})
OPTIONAL MATCH (c)-[:SITUE_DANS]->(g:Gouvernorat)
OPTIONAL MATCH (c)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient)
OPTIONAL MATCH (c)-[:PAIE_VIA]->(m:ModePaiement)
RETURN
  c.client_id          AS client_id,
  c.source             AS source,
  c.alerte             AS alerte_m2,
  c.score_final_m2     AS score_final_m2,
  c.score_gnn          AS score_gnn,
  c.score_contagion    AS score_contagion,
  c.nb_reglements      AS nb_reglements,
  c.retard_max_jours   AS retard_max_jours,
  c.taux_retard        AS taux_retard,
  c.anciennete_jours   AS anciennete_jours,
  c.montant_ttc_total  AS montant_ttc_total,
  c.ratio_encaissement AS ratio_encaissement,
  g.nom                AS gouvernorat,
  s.nom                AS segment,
  m.mnemonique         AS mode_paiement
"""

# Lazy-loaded fallback dataframes
_df_fallback: Optional[pd.DataFrame] = None


def _load_fallback() -> pd.DataFrame:
    global _df_fallback
    if _df_fallback is not None:
        return _df_fallback

    combined = pd.read_csv(_ROOT / "dataset_combined_real_synth.csv")
    combined = combined.reset_index(drop=True)
    combined["client_id"] = combined.index

    scores = pd.read_csv(_ROOT / "m5_scores_finaux.csv")

    m2 = pd.read_csv(_ROOT / "m2_gnn_scores.csv")
    m2 = m2.rename(columns={"client_index": "client_id"})

    df = combined.merge(scores, on="client_id", how="left")
    df = df.merge(m2[["client_id", "score_gnn", "score_contagion", "score_final_m2"]], on="client_id", how="left")
    _df_fallback = df
    return df


def _profil_from_csv(client_id: str) -> Optional[ProfilBrut]:
    """Construit un ProfilBrut depuis les CSV locaux quand Neo4j ne connaît pas le client."""
    try:
        prefix = client_id[0]   # "R" ou "S"
        idx = int(client_id.split("_")[1])
    except (IndexError, ValueError):
        return None

    df = _load_fallback()
    rows = df[df["client_id"] == idx]
    if rows.empty:
        return None

    r = rows.iloc[0]
    source = "REEL" if prefix == "R" else "SYNTHETIQUE"
    alerte = str(r.get("alerte", "INCONNU"))

    # score_final_m2 sur 100 (M2 GNN) — fallback sur score_solvabilite inversé
    score_m2 = float(r.get("score_final_m2", 100 - float(r.get("score_solvabilite", 50))))
    score_gnn = float(r.get("score_gnn", r.get("gnn_risk_score", 0)))
    score_contagion = float(r.get("score_contagion", 0))

    return ProfilBrut(
        client_id=client_id,
        source=source,
        alerte_m2=alerte,
        score_final_m2=score_m2,
        score_gnn=score_gnn,
        score_contagion=score_contagion,
        nb_reglements=int(r.get("nb_reglements", 0)),
        retard_max_jours=float(r.get("retard_max_jours", 0)),
        taux_retard=float(r.get("taux_retard", 0)),
        anciennete_jours=int(r.get("anciennete_jours", 0)),
        montant_ttc_total=float(r.get("montant_ttc_total", 0)),
        ratio_encaissement=float(r.get("ratio_encaissement", 0)),
        gouvernorat="INCONNU",
        segment="INCONNU",
        mode_paiement="INCONNU",
    )


def run(state: CreditMindState) -> dict:
    client_id = state["client_id"]

    # 1. Essai Neo4j
    rows = run_cypher(_CYPHER, {"cid": client_id})

    if rows:
        r = rows[0]
        profil: ProfilBrut = ProfilBrut(
            client_id=r["client_id"] or client_id,
            source=r["source"] or "INCONNU",
            alerte_m2=r["alerte_m2"] or "INCONNU",
            score_final_m2=float(r["score_final_m2"] or 0),
            score_gnn=float(r["score_gnn"] or 0),
            score_contagion=float(r["score_contagion"] or 0),
            nb_reglements=int(r["nb_reglements"] or 0),
            retard_max_jours=float(r["retard_max_jours"] or 0),
            taux_retard=float(r["taux_retard"] or 0),
            anciennete_jours=int(r["anciennete_jours"] or 0),
            montant_ttc_total=float(r["montant_ttc_total"] or 0),
            ratio_encaissement=float(r["ratio_encaissement"] or 0),
            gouvernorat=r["gouvernorat"] or "INCONNU",
            segment=r["segment"] or "INCONNU",
            mode_paiement=r["mode_paiement"] or "INCONNU",
        )
    else:
        # 2. Fallback CSV pour les clients synthétiques (S_*) ou absents de Neo4j
        profil = _profil_from_csv(client_id)
        if profil is None:
            raise ValueError(f"Client '{client_id}' introuvable dans Neo4j et dans les CSV locaux.")

    return {
        "profil_brut":      profil,
        "agents_completes": ["superviseur"],
    }
