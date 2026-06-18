"""
Charge M5 CSV + Neo4j (gouvernorat/segment) une seule fois au démarrage.
Expose un DataFrame maître et des utilitaires de requête.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

_df: Optional[pd.DataFrame] = None


def initialize() -> None:
    global _df

    # ── 1. M5 scores ─────────────────────────────────────────────────────────
    m5 = pd.read_csv(ROOT / "m5_scores_finaux.csv")
    m5 = m5.rename(columns={"client_id": "client_id"})

    # ── 2. Neo4j : gouvernorat + segment + neo4j_id ───────────────────────────
    try:
        from m7_agents.agents._neo4j import run_cypher
        rows = run_cypher(
            """
            MATCH (c:Client)
            OPTIONAL MATCH (c)-[:SITUE_DANS]->(g:Gouvernorat)
            OPTIONAL MATCH (c)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient)
            RETURN toInteger(split(c.client_id, '_')[1]) AS client_id,
                   c.client_id  AS neo4j_id,
                   g.nom        AS gouvernorat,
                   s.nom        AS segment
            """
        )
        neo4j_df = pd.DataFrame(rows)
    except Exception as exc:
        print(f"[data_store] Neo4j indisponible ({exc}) — gouvernorat/segment absents")
        neo4j_df = pd.DataFrame(columns=["client_id", "neo4j_id", "gouvernorat", "segment"])

    # ── 3. Merge ──────────────────────────────────────────────────────────────
    if not neo4j_df.empty:
        _df = m5.merge(neo4j_df, on="client_id", how="left")
    else:
        _df = m5.copy()
        _df["neo4j_id"] = _df["client_id"].apply(lambda x: f"R_{x}" if x < 1637 else f"S_{x}")
        _df["gouvernorat"] = None
        _df["segment"] = None

    print(f"[data_store] {len(_df):,} clients chargés — colonnes: {_df.columns.tolist()}")


def get_df() -> pd.DataFrame:
    if _df is None:
        raise RuntimeError("DataStore non initialisé — appeler initialize() d'abord")
    return _df
