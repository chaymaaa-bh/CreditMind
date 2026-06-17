from __future__ import annotations

from pathlib import Path

import pandas as pd

from m7_agents.state import CreditMindState, SortieAnomalies

_M4_PATH = Path(__file__).parent.parent.parent / "m4_anomaly_scores.csv"

_m4_index: dict[int, dict] | None = None


def _get_m4_index() -> dict[int, dict]:
    global _m4_index
    if _m4_index is None:
        if _M4_PATH.exists():
            df = pd.read_csv(_M4_PATH)
            _m4_index = df.set_index("client_id").to_dict("index")
        else:
            _m4_index = {}
    return _m4_index


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "anomalies":        None,
            "agents_completes": ["anomalies"],
            "erreurs":          [f"agent_anomalies: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p   = state["profil_brut"]
    raw = p["client_id"]
    cid = int(raw.split("_")[-1]) if "_" in raw else int(raw)
    m4  = _get_m4_index().get(cid)

    if m4 is not None:
        # ── Chemin M4 : données réelles IF + LSTM Autoencoder ─────────────────
        score       = round(float(m4["score_anomalie_final"]) * 100, 2)
        est_outlier = bool(int(m4["pred_ensemble"]) == 1)
        raison      = str(m4["raison_principale"]) if m4.get("raison_principale") else None

        if not est_outlier or not raison:
            type_anomalie      = None
            features_aberrantes: list[str] = []
        else:
            r = raison.lower()
            if "retard" in r:
                type_anomalie = "anomalie_retard"
            elif "encaissement" in r:
                type_anomalie = "anomalie_paiement"
            else:
                type_anomalie = "anomalie_comportementale"
            features_aberrantes = [raison]

        is_mock = False

    else:
        # ── Fallback stub : client absent du CSV M4 ────────────────────────────
        score = 0.0
        features_aberrantes = []

        if p["nb_reglements"] == 0 and p["montant_ttc_total"] > 10_000:
            score += 30
            features_aberrantes.append("nb_reglements=0 malgré montant_ttc élevé")
        if p["ratio_encaissement"] > 1.5:
            score += 25
            features_aberrantes.append(f"ratio_encaissement anormalement élevé ({p['ratio_encaissement']:.2f})")
        if p["taux_retard"] == 0.0 and p["score_contagion"] > 60:
            score += 25
            features_aberrantes.append("score_contagion élevé sans retard comportemental")
        if p["anciennete_jours"] < 90 and p["montant_ttc_total"] > 50_000:
            score += 20
            features_aberrantes.append(f"client récent ({p['anciennete_jours']} j) avec forte exposition")
        if p["retard_max_jours"] < 0:
            score += 15
            features_aberrantes.append(f"retard_max_jours négatif ({p['retard_max_jours']:.1f})")

        score       = min(score, 100.0)
        est_outlier = score > 40

        joined = " ".join(features_aberrantes)
        if score == 0:
            type_anomalie = None
        elif "ratio_encaissement" in joined:
            type_anomalie = "anomalie_paiement"
        elif "score_contagion" in joined:
            type_anomalie = "anomalie_reseau"
        else:
            type_anomalie = "anomalie_mixte"

        is_mock = True

    sortie: SortieAnomalies = {
        "score_anomalie":      round(score, 2),
        "est_outlier":         est_outlier,
        "type_anomalie":       type_anomalie,
        "features_aberrantes": features_aberrantes,
        "is_mock":             is_mock,
    }
    return {"anomalies": sortie, "agents_completes": ["anomalies"]}
