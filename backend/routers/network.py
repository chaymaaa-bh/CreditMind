from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.schemas import NetworkGraph, NetworkNode
from backend.services.data_store import get_df

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

router = APIRouter(prefix="/network", tags=["network"])


def _parse_id(raw: str) -> int:
    if "_" in raw:
        return int(raw.split("_")[-1])
    return int(raw)


@router.get("/{raw_id}", response_model=NetworkGraph)
def get_network(raw_id: str, limit: int = Query(30, ge=5, le=100)) -> NetworkGraph:
    try:
        int_id = _parse_id(raw_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"ID invalide : {raw_id}")

    df = get_df()
    row = df[df["client_id"] == int_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Client {int_id} introuvable")

    center = row.iloc[0]

    def _node(r) -> NetworkNode:
        return NetworkNode(
            client_id=int(r["client_id"]),
            neo4j_id=str(r.get("neo4j_id", f"R_{r['client_id']}")),
            alerte=str(r["alerte"]),
            score_m2=round(float(r.get("gnn_risk_score", 0) * 100), 1),
            prob_defaut=round(float(r["prob_defaut"]), 4),
            gouvernorat=r.get("gouvernorat") or None,
            segment=r.get("segment") or None,
            is_center=False,
        )

    center_node = _node(center)
    center_node.is_center = True

    # Voisins : même gouvernorat en priorité, sinon même classe de risque
    gov = center.get("gouvernorat")
    if gov and gov == gov:  # not NaN
        neighbors_df = df[
            (df["gouvernorat"] == gov) & (df["client_id"] != int_id)
        ].sort_values("prob_defaut", ascending=False).head(limit)
    else:
        alerte_val = center["alerte"]
        neighbors_df = df[
            (df["alerte"] == alerte_val) & (df["client_id"] != int_id)
        ].sort_values("prob_defaut", ascending=False).head(limit)

    neighbor_nodes = [_node(r) for _, r in neighbors_df.iterrows()]

    return NetworkGraph(
        center=center_node,
        neighbors=neighbor_nodes,
        total_gouvernorat=int(
            len(df[df["gouvernorat"] == gov]) if (gov and gov == gov) else 0
        ),
        lien_type="SITUE_DANS_MEME_GOUVERNORAT" if (gov and gov == gov) else "MEME_CLASSE_RISQUE",
    )
