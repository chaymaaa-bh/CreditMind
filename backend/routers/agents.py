from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.schemas import AgentsResult

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

router = APIRouter(prefix="/agents", tags=["agents"])


def _parse_id(raw: str) -> str:
    """Normalise 'R_42', 'S_1234', '42' en identifiant M7."""
    raw = raw.strip()
    if "_" in raw:
        return raw
    try:
        n = int(raw)
        return f"R_{n}" if n < 1637 else f"S_{n}"
    except ValueError:
        return raw


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


@router.get("/{raw_id}", response_model=AgentsResult)
def run_agents(raw_id: str) -> AgentsResult:
    client_id = _parse_id(raw_id)

    try:
        from m7_agents.graph import graph
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur import M7: {exc}")

    initial: dict = {
        "client_id":        client_id,
        "profil_brut":      None,
        "comportement":     None,
        "reseau":           None,
        "forecast":         None,
        "anomalies":        None,
        "compliance":       None,
        "raisonnement":     None,
        "rapport_final":    None,
        "agents_completes": [],
        "erreurs":          [],
    }

    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(graph.invoke, initial)
            result = future.result(timeout=120)
    except concurrent.futures.TimeoutError:
        raise HTTPException(status_code=504, detail="M7 timeout après 120s — réessayez")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    rf  = result.get("rapport_final") or {}
    r   = result.get("raisonnement") or {}
    c   = result.get("comportement") or {}
    res = result.get("reseau") or {}
    fc  = result.get("forecast") or {}
    an  = result.get("anomalies") or {}
    co  = result.get("compliance") or {}

    return AgentsResult(
        client_id=client_id,
        decision=str(rf.get("decision", "N/A")),
        score_global=_safe_float(rf.get("score_global", 0)),
        alerte_finale=str(rf.get("alerte_finale", "N/A")),
        rapport_narratif=str(rf.get("rapport_narratif", "")),
        actions_recommandees=list(rf.get("actions_recommandees") or []),
        horizon_reevaluation=str(rf.get("horizon_reevaluation", "")),
        score_consensus=_safe_float(r.get("score_consensus", 0)),
        niveau_confiance=str(r.get("niveau_confiance", "N/A")),
        agents_mock=list(r.get("agents_mock") or []),
        agents_completes=list(result.get("agents_completes") or []),
        erreurs=list(result.get("erreurs") or []),
        comportement={
            "score": _safe_float(c.get("score", 0)),
            "niveau": str(c.get("niveau", "N/A")),
            "signaux": list(c.get("signaux") or []),
            "is_mock": bool(c.get("is_mock", True)),
        },
        reseau={
            "score_gnn": _safe_float(res.get("score_gnn", 0)),
            "score_contagion": _safe_float(res.get("score_contagion", 0)),
            "score_final_m2": _safe_float(res.get("score_final_m2", 0)),
            "alerte": str(res.get("alerte", "N/A")),
            "nb_voisins_total": int(res.get("nb_voisins_total", 0)),
            "nb_voisins_rouge": int(res.get("nb_voisins_rouge", 0)),
            "voisins_top5": list(res.get("voisins_top5") or []),
            "is_mock": bool(res.get("is_mock", True)),
        },
        forecast={
            "tendance": str(fc.get("tendance", "N/A")),
            "probabilite_defaut_6m": _safe_float(fc.get("probabilite_defaut_6m", 0)),
            "predictions_score": dict(fc.get("predictions_score") or {}),
            "mois_alerte_prevu": fc.get("mois_alerte_prevu"),
            "is_mock": bool(fc.get("is_mock", True)),
        },
        anomalies={
            "score_anomalie": _safe_float(an.get("score_anomalie", 0)),
            "est_outlier": bool(an.get("est_outlier", False)),
            "type_anomalie": an.get("type_anomalie"),
            "features_aberrantes": list(an.get("features_aberrantes") or []),
            "is_mock": bool(an.get("is_mock", True)),
        },
        compliance={
            "rapport_client": str(co.get("rapport_client", "")),
            "concepts_declenches": list(co.get("concepts_declenches") or []),
            "is_mock": bool(co.get("is_mock", True)),
        },
    )
