"""
Calcule les indicateurs financiers du stress-test à partir des sorties Monte Carlo.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .schema import IndicateursStress

# Taux de provision IFRS 9 Stage 3 (approximation) pour les clients basculant ROUGE
_PROVISION_RATE = 0.15


def compute_indicators(
    clients: list[dict[str, Any]],
    sim: dict[str, Any],
) -> IndicateursStress:
    """
    Calcule les indicateurs de stress à partir des sorties de run_simulation().

    EaRS (Encours à Risque Stressé) = Σ montant_ttc_total des clients qui basculent
    de non-ROUGE à ROUGE dans une simulation donnée.  La valeur rapportée est la
    médiane sur l'ensemble des N runs Monte Carlo.
    """
    baseline_scores  = sim["baseline_scores"]    # (n_clients,)
    score_matrix     = sim["score_matrix"]        # (n_sims, n_clients)
    baseline_retard  = sim["baseline_retard"]     # (n_clients,)
    retard_matrix    = sim["retard_matrix"]       # (n_sims, n_clients)
    baseline_encours = sim["baseline_encours"]    # (n_clients,)
    n_sims, n_clients = score_matrix.shape

    # ── Codes d'alerte (0=VERT, 1=ORANGE, 2=ROUGE) ────────────────────────────
    baseline_alerte_int = np.where(baseline_scores < 30, 0,
                          np.where(baseline_scores < 70, 1, 2))           # (n_clients,)
    stressed_alerte_int = np.where(score_matrix < 30, 0,
                          np.where(score_matrix < 70, 1, 2))              # (n_sims, n_clients)

    baseline_rouge = (baseline_alerte_int == 2)                           # (n_clients,) bool

    # ── EaRS par simulation ────────────────────────────────────────────────────
    newly_rouge = (stressed_alerte_int == 2) & ~baseline_rouge            # (n_sims, n_clients)
    EaRS_per_sim = (newly_rouge.astype(float) * baseline_encours).sum(axis=1)  # (n_sims,)

    EaRS_median = float(np.median(EaRS_per_sim))
    ic95 = [
        float(np.percentile(EaRS_per_sim, 2.5)),
        float(np.percentile(EaRS_per_sim, 97.5)),
    ]

    # ── Simulation de référence : celle dont l'EaRS est la médiane ─────────────
    median_idx = int(np.argsort(EaRS_per_sim)[n_sims // 2])
    stressed_alerte_ref = stressed_alerte_int[median_idx]                 # (n_clients,)
    newly_rouge_ref     = newly_rouge[median_idx]                         # (n_clients,)

    # ── Distributions avant / après ────────────────────────────────────────────
    dist_avant = {
        "VERT":   int((baseline_alerte_int == 0).sum()),
        "ORANGE": int((baseline_alerte_int == 1).sum()),
        "ROUGE":  int((baseline_alerte_int == 2).sum()),
    }
    dist_apres = {
        "VERT":   int((stressed_alerte_ref == 0).sum()),
        "ORANGE": int((stressed_alerte_ref == 1).sum()),
        "ROUGE":  int((stressed_alerte_ref == 2).sum()),
    }

    nb_bascule  = int(newly_rouge_ref.sum())
    pct_bascule = round(nb_bascule / n_clients * 100, 2) if n_clients > 0 else 0.0

    # ── Δ Score et Δ Retard (simulation de référence) ─────────────────────────
    delta_scores_ref = score_matrix[median_idx] - baseline_scores         # (n_clients,)
    delta_score_moyen  = float(delta_scores_ref.mean())
    delta_retard_moyen = float((retard_matrix[median_idx] - baseline_retard).mean())

    # ── Top 10 clients les plus impactés ───────────────────────────────────────
    _ALERTE_LABELS = ["VERT", "ORANGE", "ROUGE"]
    top_indices = np.argsort(delta_scores_ref)[::-1][:10]
    clients_top = []
    for i in top_indices:
        c = clients[int(i)]
        clients_top.append({
            "client_id":       c["client_id"],
            "gouvernorat":     c["gouvernorat"],
            "segment":         c["segment"],
            "alerte_baseline": c["alerte"],
            "alerte_stresse":  _ALERTE_LABELS[int(stressed_alerte_ref[int(i)])],
            "score_baseline":  round(float(baseline_scores[int(i)]), 1),
            "score_stresse":   round(float(score_matrix[median_idx, int(i)]), 1),
            "encours_tnd":     round(float(c["montant_ttc_total"]), 0),
        })

    return IndicateursStress(
        nb_clients_analyses=n_clients,
        nb_clients_bascule_rouge=nb_bascule,
        pct_bascule_rouge=pct_bascule,
        delta_score_moyen=round(delta_score_moyen, 2),
        encours_a_risque_stresse=round(EaRS_median, 0),
        delta_retard_moyen_jours=round(delta_retard_moyen, 1),
        provision_recommandee=round(EaRS_median * _PROVISION_RATE, 0),
        distribution_avant=dist_avant,
        distribution_apres=dist_apres,
        clients_les_plus_impactes=clients_top,
        ic95_EaRS=ic95,
    )
