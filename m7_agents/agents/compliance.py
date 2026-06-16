from __future__ import annotations

from m7_agents.agents._neo4j import run_cypher
from m7_agents.state import CreditMindState, SortieCompliance

# Lazy singleton — CreditMindRAG init is heavy (Neo4j + LlamaIndex)
_rag = None


def _get_rag():
    global _rag
    if _rag is None:
        from m6_graphrag.rag_engine import CreditMindRAG
        _rag = CreditMindRAG()
    return _rag


_CYPHER_CONCEPTS = """
MATCH (c:Client {client_id: $cid})-[:PRESENTE]->(cr:ConceptRisque)
RETURN cr.nom AS nom
"""

_CYPHER_REGLES = """
MATCH (c:Client {client_id: $cid})-[:PRESENTE]->(cr:ConceptRisque)-[:DEFINI_PAR]->(rd:RegleDecision)
RETURN DISTINCT rd.regle_id AS id ORDER BY rd.regle_id
"""


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "compliance":       None,
            "agents_completes": ["compliance"],
            "erreurs":          [f"agent_compliance: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    cid = state["client_id"]
    rag = _get_rag()

    rapport   = rag.get_client_report(cid)
    contagion = rag.contagion_analysis(cid, depth=2)
    concepts  = [r["nom"] for r in run_cypher(_CYPHER_CONCEPTS, {"cid": cid})]
    regles    = [r["id"]  for r in run_cypher(_CYPHER_REGLES,   {"cid": cid})]

    sortie: SortieCompliance = {
        "rapport_client":      rapport,
        "analyse_contagion":   contagion,
        "concepts_declenches": concepts,
        "regles_applicables":  regles,
        "is_mock":             False,
    }
    return {"compliance": sortie, "agents_completes": ["compliance"]}
