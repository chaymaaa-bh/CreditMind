from __future__ import annotations

from m7_agents.state import CreditMindState, SortieComportement


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "comportement":    None,
            "agents_completes": ["comportement"],
            "erreurs":         [f"agent_comportement: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p = state["profil_brut"]
    signaux: list[str] = []
    score = 0.0

    if p["nb_reglements"] == 0:
        score += 30
        signaux.append("Aucun règlement enregistré")

    score += p["taux_retard"] * 40
    if p["taux_retard"] > 0.5:
        signaux.append(f"Taux de retard élevé ({p['taux_retard']:.0%})")

    if p["retard_max_jours"] > 90:
        score += 20
        signaux.append(f"Retard grave (max {p['retard_max_jours']:.0f} j)")
    elif p["retard_max_jours"] > 30:
        score += 10
        signaux.append(f"Retard modéré (max {p['retard_max_jours']:.0f} j)")

    if p["ratio_encaissement"] < 0.3 and p["nb_reglements"] > 0:
        score += 15
        signaux.append(f"Faible encaissement ({p['ratio_encaissement']:.0%})")

    if p["anciennete_jours"] < 90:
        score += 8
        signaux.append(f"Client très récent ({p['anciennete_jours']} j d'ancienneté)")

    score = min(score, 100.0)

    if score < 30:
        niveau = "VERT"
    elif score < 70:
        niveau = "ORANGE"
    else:
        niveau = "ROUGE"

    sortie: SortieComportement = {
        "score":   round(score, 2),
        "niveau":  niveau,
        "signaux": signaux or ["Aucun signal comportemental négatif détecté"],
        "features_cles": {
            "taux_retard":        p["taux_retard"],
            "retard_max_jours":   p["retard_max_jours"],
            "nb_reglements":      float(p["nb_reglements"]),
            "ratio_encaissement": p["ratio_encaissement"],
            "anciennete_jours":   float(p["anciennete_jours"]),
        },
        "is_mock": True,
    }
    return {"comportement": sortie, "agents_completes": ["comportement"]}
