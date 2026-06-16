from __future__ import annotations

from m7_agents.agents._neo4j import run_cypher
from m7_agents.state import CreditMindState, ProfilBrut

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


def run(state: CreditMindState) -> dict:
    client_id = state["client_id"]
    rows = run_cypher(_CYPHER, {"cid": client_id})
    if not rows:
        raise ValueError(f"Client '{client_id}' introuvable dans Neo4j.")

    r = rows[0]
    profil: ProfilBrut = {
        "client_id":          r["client_id"] or client_id,
        "source":             r["source"] or "INCONNU",
        "alerte_m2":          r["alerte_m2"] or "INCONNU",
        "score_final_m2":     float(r["score_final_m2"] or 0),
        "score_gnn":          float(r["score_gnn"] or 0),
        "score_contagion":    float(r["score_contagion"] or 0),
        "nb_reglements":      int(r["nb_reglements"] or 0),
        "retard_max_jours":   float(r["retard_max_jours"] or 0),
        "taux_retard":        float(r["taux_retard"] or 0),
        "anciennete_jours":   int(r["anciennete_jours"] or 0),
        "montant_ttc_total":  float(r["montant_ttc_total"] or 0),
        "ratio_encaissement": float(r["ratio_encaissement"] or 0),
        "gouvernorat":        r["gouvernorat"] or "INCONNU",
        "segment":            r["segment"] or "INCONNU",
        "mode_paiement":      r["mode_paiement"] or "INCONNU",
    }
    return {
        "profil_brut":      profil,
        "agents_completes": ["superviseur"],
    }
