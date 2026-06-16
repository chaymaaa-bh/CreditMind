from __future__ import annotations

from m7_agents.state import CreditMindState, SortieAnomalies


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
    p     = state["profil_brut"]
    score = 0.0
    feats: list[str] = []

    # Aucun paiement malgré un montant facturé significatif
    if p["nb_reglements"] == 0 and p["montant_ttc_total"] > 10_000:
        score += 30
        feats.append("nb_reglements=0 malgré montant_ttc élevé")

    # Sur-encaissement (ratio > 1.5 : anomalie comptable ou remboursement exceptionnel)
    if p["ratio_encaissement"] > 1.5:
        score += 25
        feats.append(f"ratio_encaissement anormalement élevé ({p['ratio_encaissement']:.2f})")

    # Risque porté par le réseau sans signal comportemental
    if p["taux_retard"] == 0.0 and p["score_contagion"] > 60:
        score += 25
        feats.append("score_contagion élevé sans retard comportemental")

    # Client récent avec forte exposition
    if p["anciennete_jours"] < 90 and p["montant_ttc_total"] > 50_000:
        score += 20
        feats.append(f"client récent ({p['anciennete_jours']} j) avec forte exposition")

    # Retard maximal négatif (incohérence de données)
    if p["retard_max_jours"] < 0:
        score += 15
        feats.append(f"retard_max_jours négatif ({p['retard_max_jours']:.1f})")

    score = min(score, 100.0)
    est_outlier = score > 40

    joined = " ".join(feats)
    if score == 0:
        type_anomalie = None
    elif "ratio_encaissement" in joined:
        type_anomalie = "anomalie_paiement"
    elif "score_contagion" in joined:
        type_anomalie = "anomalie_reseau"
    else:
        type_anomalie = "anomalie_mixte"

    sortie: SortieAnomalies = {
        "score_anomalie":     round(score, 2),
        "est_outlier":        est_outlier,
        "type_anomalie":      type_anomalie,
        "features_aberrantes": feats,
        "is_mock":            True,
    }
    return {"anomalies": sortie, "agents_completes": ["anomalies"]}
