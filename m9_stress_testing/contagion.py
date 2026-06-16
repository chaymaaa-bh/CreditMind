"""
Propagation de risque par contagion graphe (scénario défaillance systémique).
Invoqué uniquement quand ScenarioParams.categorie == "contagion".
"""
from __future__ import annotations

import logging
from typing import Any

from m7_agents.agents._neo4j import run_cypher

logger = logging.getLogger(__name__)


def run_contagion(
    seed_client_ids: list[str],
    depth: int = 2,
) -> dict[str, Any]:
    """
    Propage le risque par vagues BFS depuis les clients déclencheurs (seed_client_ids).

    Utilise les arêtes CONTAGION_TERRITOIRE et CONTAGION_PORTEFEUILLE construites en M2.
    depth est limité à 3 pour éviter l'explosion combinatoire.

    Returns:
        vagues         : list[dict] — clients par niveau de propagation
        totaux         : dict[str, int] — nb clients par vague
        encours_cumule : float — montant_ttc_total cumulé des clients contaminés (TND)
        nb_contamines  : int
    """
    if not seed_client_ids:
        return {"vagues": [], "totaux": {}, "encours_cumule": 0.0, "nb_contamines": 0}

    depth = min(depth, 3)

    cypher = f"""
    MATCH path = (seed:Client)-[:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE*1..{depth}]->(voisin:Client)
    WHERE seed.client_id IN $seeds
      AND NOT voisin.client_id IN $seeds
    WITH voisin,
         min(length(path))                          AS niveau,
         avg([r IN relationships(path) | r.poids])  AS poids_moyen
    RETURN
      voisin.client_id        AS client_id,
      voisin.alerte           AS alerte,
      voisin.score_final_m2   AS score_final_m2,
      voisin.montant_ttc_total AS encours,
      niveau,
      poids_moyen
    ORDER BY niveau ASC, score_final_m2 DESC
    """

    rows = run_cypher(cypher, {"seeds": seed_client_ids})
    if not rows:
        logger.info("Aucun voisin de contagion trouvé pour %d déclencheurs.", len(seed_client_ids))
        return {"vagues": [], "totaux": {}, "encours_cumule": 0.0, "nb_contamines": 0}

    vagues: dict[int, list[dict]] = {}
    encours_cumule = 0.0

    for r in rows:
        niv = int(r.get("niveau") or 1)
        encours = float(r.get("encours") or 0)
        vagues.setdefault(niv, []).append({
            "client_id":        r.get("client_id"),
            "alerte":           r.get("alerte"),
            "score":            round(float(r.get("score_final_m2") or 0), 1),
            "encours":          round(encours, 0),
            "poids_contagion":  round(float(r.get("poids_moyen") or 0), 4),
        })
        encours_cumule += encours

    totaux = {f"vague_{k}": len(v) for k, v in sorted(vagues.items())}
    nb_contamines = sum(len(v) for v in vagues.values())

    logger.info(
        "Contagion : %d déclencheurs → %d contaminés sur %d niveaux, encours=%,.0f TND",
        len(seed_client_ids), nb_contamines, depth, encours_cumule,
    )

    return {
        "vagues":          [{"niveau": k, "clients": v} for k, v in sorted(vagues.items())],
        "totaux":          totaux,
        "encours_cumule":  round(encours_cumule, 0),
        "nb_contamines":   nb_contamines,
    }
