from __future__ import annotations

from pathlib import Path

import pandas as pd

from m7_agents.state import CreditMindState, SortieComportement

# CSV produit par M5 — chemin relatif à la racine du projet
_M5_PATH = Path(__file__).parent.parent.parent / "m5_scores_finaux.csv"

# Cache module-level : chargé une seule fois, indexé par client_id (int)
_m5_index: dict[int, dict] | None = None


def _get_m5_index() -> dict[int, dict]:
    global _m5_index
    if _m5_index is None:
        if _M5_PATH.exists():
            df = pd.read_csv(_M5_PATH)
            _m5_index = df.set_index("client_id").to_dict("index")
        else:
            _m5_index = {}
    return _m5_index


def run(state: CreditMindState) -> dict:
    try:
        return _run(state)
    except Exception as exc:
        return {
            "comportement":     None,
            "agents_completes": ["comportement"],
            "erreurs":          [f"agent_comportement: {exc}"],
        }


def _run(state: CreditMindState) -> dict:
    p   = state["profil_brut"]
    raw = p["client_id"]
    cid = int(raw.split("_")[-1]) if "_" in raw else int(raw)
    m5  = _get_m5_index().get(cid)

    # ── Signaux comportementaux depuis ProfilBrut (toujours disponibles) ──────
    signaux: list[str] = []
    if p["nb_reglements"] == 0:
        signaux.append("Aucun règlement enregistré")
    if p["taux_retard"] > 0.5:
        signaux.append(f"Taux de retard élevé ({p['taux_retard']:.0%})")
    if p["retard_max_jours"] > 90:
        signaux.append(f"Retard grave (max {p['retard_max_jours']:.0f} j)")
    elif p["retard_max_jours"] > 30:
        signaux.append(f"Retard modéré (max {p['retard_max_jours']:.0f} j)")
    if p["ratio_encaissement"] < 0.3 and p["nb_reglements"] > 0:
        signaux.append(f"Faible encaissement ({p['ratio_encaissement']:.0%})")
    if p["anciennete_jours"] < 90:
        signaux.append(f"Client très récent ({p['anciennete_jours']} j d'ancienneté)")

    features_cles: dict[str, float] = {
        "taux_retard":        p["taux_retard"],
        "retard_max_jours":   p["retard_max_jours"],
        "nb_reglements":      float(p["nb_reglements"]),
        "ratio_encaissement": p["ratio_encaissement"],
        "anciennete_jours":   float(p["anciennete_jours"]),
    }

    if m5 is not None:
        # ── Chemin M5 : données réelles de l'ensemble XGBoost+LightGBM ────────
        score          = round(float(m5["prob_defaut"]) * 100, 2)
        niveau: str    = str(m5["alerte"])   # "VERT"|"JAUNE"|"ORANGE"|"ROUGE"
        modele_utilise = "XGBoost+LightGBM ensemble"
        is_mock        = False
    else:
        # ── Fallback stub : M5 absent ou client inconnu ────────────────────────
        s = 0.0
        if p["nb_reglements"] == 0:
            s += 30
        s += p["taux_retard"] * 40
        if p["retard_max_jours"] > 90:
            s += 20
        elif p["retard_max_jours"] > 30:
            s += 10
        if p["ratio_encaissement"] < 0.3 and p["nb_reglements"] > 0:
            s += 15
        if p["anciennete_jours"] < 90:
            s += 8
        score = round(min(s, 100.0), 2)

        if score < 25:
            niveau = "VERT"
        elif score < 50:
            niveau = "JAUNE"
        elif score < 75:
            niveau = "ORANGE"
        else:
            niveau = "ROUGE"

        modele_utilise = "stub_comportemental"
        is_mock        = True

    sortie: SortieComportement = {
        "score":          score,
        "niveau":         niveau,
        "signaux":        signaux or ["Aucun signal comportemental négatif détecté"],
        "features_cles":  features_cles,
        "modele_utilise": modele_utilise,
        "is_mock":        is_mock,
    }
    return {"comportement": sortie, "agents_completes": ["comportement"]}
