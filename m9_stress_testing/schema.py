from __future__ import annotations

from typing import TypedDict


class FeatureDelta(TypedDict):
    feature: str       # nom de la feature Neo4j du nœud Client
    delta_type: str    # "multiplicatif" | "additif"
    delta_value: float # multiplicatif : feature × (1 + delta_value) ; additif : feature + delta_value
    std_pct: float     # incertitude Monte Carlo : std = std_pct × |delta_value|


class ScenarioParams(TypedDict):
    description_originale: str
    categorie: str              # inflation_couts | contraction_credit | risque_regional | choc_change | contagion
    duree_mois: int
    gouvernorats_cibles: list[str]  # [] = tous ; noms Neo4j en MAJUSCULES (ex: "SFAX")
    segments_cibles: list[str]      # [] = tous
    feature_deltas: list[FeatureDelta]
    intensite: str              # "FAIBLE" | "MODERE" | "SEVERE"


class IndicateursStress(TypedDict):
    nb_clients_analyses: int
    nb_clients_bascule_rouge: int       # médiane sur N simulations
    pct_bascule_rouge: float
    delta_score_moyen: float            # variation moyenne du score_final_m2 (sim médiane)
    encours_a_risque_stresse: float     # EaRS médiane en TND
    delta_retard_moyen_jours: float     # Δ délai moyen de paiement (sim médiane)
    provision_recommandee: float        # EaRS médiane × 15 % (IFRS 9 Stage 3)
    distribution_avant: dict            # {"VERT": n, "ORANGE": n, "ROUGE": n}
    distribution_apres: dict            # idem, simulation médiane
    clients_les_plus_impactes: list[dict]
    ic95_EaRS: list[float]              # [percentile_2.5, percentile_97.5]
