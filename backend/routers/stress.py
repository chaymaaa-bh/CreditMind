from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

router = APIRouter(prefix="/stress", tags=["stress"])


class StressRequest(BaseModel):
    scenario: str = Field(..., min_length=10, description="Description du scénario en langage naturel")
    n_simulations: int = Field(200, ge=50, le=1000)


@router.post("/run", response_model=dict)
def run_stress(req: StressRequest) -> dict[str, Any]:
    try:
        from m9_stress_testing.run import main as stress_main
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur import M9: {exc}")

    try:
        result = stress_main(
            scenario_text=req.scenario,
            n_simulations=req.n_simulations,
            seed=42,
            verbose=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    ind = result.get("indicateurs", {})
    sc  = result.get("scenario", {})

    # Nettoyage des types numpy / non-JSON-sérialisables
    def _clean(v: Any) -> Any:
        if hasattr(v, "item"):
            return v.item()
        if isinstance(v, dict):
            return {k: _clean(vv) for k, vv in v.items()}
        if isinstance(v, list):
            return [_clean(x) for x in v]
        return v

    return {
        "scenario": {
            "description": sc.get("description_originale", req.scenario),
            "categorie": sc.get("categorie", ""),
            "intensite": sc.get("intensite", ""),
            "duree_mois": sc.get("duree_mois", 0),
            "gouvernorats_cibles": sc.get("gouvernorats_cibles", []),
            "segments_cibles": sc.get("segments_cibles", []),
            "feature_deltas": _clean(sc.get("feature_deltas", [])),
        },
        "indicateurs": {
            "nb_clients_analyses": int(ind.get("nb_clients_analyses", 0)),
            "nb_clients_bascule_rouge": int(ind.get("nb_clients_bascule_rouge", 0)),
            "pct_bascule_rouge": float(ind.get("pct_bascule_rouge", 0)),
            "delta_score_moyen": float(ind.get("delta_score_moyen", 0)),
            "encours_a_risque_stresse": float(ind.get("encours_a_risque_stresse", 0)),
            "delta_retard_moyen_jours": float(ind.get("delta_retard_moyen_jours", 0)),
            "provision_recommandee": float(ind.get("provision_recommandee", 0)),
            "distribution_avant": _clean(ind.get("distribution_avant", {})),
            "distribution_apres": _clean(ind.get("distribution_apres", {})),
            "clients_les_plus_impactes": _clean(ind.get("clients_les_plus_impactes", [])),
            "ic95_EaRS": [float(x) for x in ind.get("ic95_EaRS", [0, 0])],
        },
        "rapport": str(result.get("rapport", "")),
        "contagion": _clean(result.get("contagion")) if result.get("contagion") else None,
    }
