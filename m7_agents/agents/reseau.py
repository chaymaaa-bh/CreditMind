from __future__ import annotations

from m7_agents.agents._neo4j import run_cypher
from m7_agents.state import CreditMindState, SortieReseau

_CYPHER_VOISINS = """
MATCH (c:Client {client_id: $cid})-[r:CONTAGION_TERRITOIRE]->(v:Client)
RETURN
  type(r)          AS type_lien,
  v.client_id      AS voisin_id,
  v.alerte         AS alerte,
  v.score_final_m2 AS score_m2
ORDER BY v.score_final_m2 DESC
LIMIT 10
"""


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "reseau":           None,
            "agents_completes": ["reseau"],
            "erreurs":          [f"agent_reseau: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p    = state["profil_brut"]
    rows = run_cypher(_CYPHER_VOISINS, {"cid": state["client_id"]})

    nb_rouge  = sum(1 for r in rows if r["alerte"] == "ROUGE")
    nb_orange = sum(1 for r in rows if r["alerte"] == "ORANGE")

    sortie: SortieReseau = {
        "score_gnn":         p["score_gnn"],
        "score_contagion":   p["score_contagion"],
        "score_final_m2":    p["score_final_m2"],
        "alerte":            p["alerte_m2"],
        "nb_voisins_total":  len(rows),
        "nb_voisins_rouge":  nb_rouge,
        "nb_voisins_orange": nb_orange,
        "voisins_top5": [
            {
                "client_id": r["voisin_id"],
                "alerte":    r["alerte"],
                "score_m2":  float(r["score_m2"] or 0),
                "type_lien": r["type_lien"],
            }
            for r in rows[:5]
        ],
        "is_mock": False,
    }
    return {"reseau": sortie, "agents_completes": ["reseau"]}
