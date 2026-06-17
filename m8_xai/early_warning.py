from __future__ import annotations

from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).parent.parent

_m5_index: dict[int, dict] | None = None
_m4_index: dict[int, dict] | None = None


def _get_m5() -> dict[int, dict]:
    global _m5_index
    if _m5_index is None:
        df = pd.read_csv(_ROOT / "m5_scores_finaux.csv")
        _m5_index = df.set_index("client_id").to_dict("index")
    return _m5_index


def _get_m4() -> dict[int, dict]:
    global _m4_index
    if _m4_index is None:
        path = _ROOT / "m4_anomaly_scores.csv"
        if path.exists():
            df = pd.read_csv(path)
            _m4_index = df.set_index("client_id").to_dict("index")
        else:
            _m4_index = {}
    return _m4_index


def compute_alert(client_id: int) -> dict:
    m5 = _get_m5().get(client_id)
    if m5 is None:
        return {"error": f"client {client_id} absent de m5_scores_finaux.csv"}

    m4 = _get_m4().get(client_id, {})

    score      = float(m5["score_solvabilite"])
    prob       = float(m5["prob_defaut"])
    anomalie   = float(m5.get("score_anomalie", 0)) * 100  # M5 stores 0-1
    gnn        = float(m5.get("gnn_risk_score", 0))        # 0-1
    tendance   = max(-30.0, min(30.0, float(m5.get("tendance_m3", 0))))
    pred_ens   = int(m4.get("pred_ensemble", 0))
    raison     = str(m4.get("raison_principale", "")) if m4 else ""

    triggers: list[str] = []
    niveau = "VERT"

    # ── Niveau ROUGE ──────────────────────────────────────────────────────
    if score < 20:
        niveau = "ROUGE"
        triggers.append(f"score_solvabilite critique ({score:.0f}/100)")
    elif score < 40 and (anomalie > 60 or gnn > 0.75):
        niveau = "ROUGE"
        triggers.append(f"score faible ({score:.0f}) combiné à anomalie/contagion élevée")

    # ── Niveau ORANGE ─────────────────────────────────────────────────────
    elif score < 40:
        niveau = "ORANGE"
        triggers.append(f"score_solvabilite faible ({score:.0f}/100)")
    elif score < 60 and anomalie > 50:
        niveau = "ORANGE"
        triggers.append(f"score anomalie M4 élevé ({anomalie:.0f}/100)")
    elif score < 60 and gnn > 0.70:
        niveau = "ORANGE"
        triggers.append(f"risque réseau GNN élevé ({gnn:.2f})")

    # ── Niveau JAUNE ──────────────────────────────────────────────────────
    elif score < 60:
        niveau = "JAUNE"
        triggers.append(f"score_solvabilite modéré ({score:.0f}/100)")
    elif pred_ens == 1 and score < 75:
        niveau = "JAUNE"
        triggers.append("détecté comme outlier par M4 malgré score acceptable")
    elif tendance > 3:
        niveau = "JAUNE"
        triggers.append(f"tendance M3 haussière (Δrisque = +{tendance:.1f})")
    elif anomalie > 60:
        niveau = "JAUNE"
        triggers.append(f"anomalie comportementale détectée ({anomalie:.0f}/100)")

    if raison and niveau in ("ORANGE", "ROUGE"):
        triggers.append(f"raison M4 : {raison}")

    return {
        "client_id":        client_id,
        "niveau_alerte":    niveau,
        "triggers":         triggers,
        "score_solvabilite": round(score, 1),
        "prob_defaut":      round(prob, 3),
        "score_anomalie":   round(anomalie, 1),
        "gnn_risk_score":   round(gnn, 3),
        "tendance_m3":      round(tendance, 3),
        "alerte_m5":        str(m5.get("alerte", "?")),
    }
