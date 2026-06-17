from __future__ import annotations

from typing import Annotated, TypedDict
import operator


class ProfilBrut(TypedDict):
    client_id:          str
    source:             str    # "REEL" | "SYNTHETIQUE"
    alerte_m2:          str    # "VERT" | "JAUNE" | "ORANGE" | "ROUGE"
    score_final_m2:     float
    score_gnn:          float
    score_contagion:    float
    nb_reglements:      int
    retard_max_jours:   float
    taux_retard:        float
    anciennete_jours:   int
    montant_ttc_total:  float
    ratio_encaissement: float
    gouvernorat:        str
    segment:            str
    mode_paiement:      str


class SortieComportement(TypedDict):
    score:          float
    niveau:         str            # "VERT" | "JAUNE" | "ORANGE" | "ROUGE"
    signaux:        list[str]
    features_cles:  dict[str, float]
    modele_utilise: str
    is_mock:        bool


class SortieReseau(TypedDict):
    score_gnn:         float
    score_contagion:   float
    score_final_m2:    float
    alerte:            str
    nb_voisins_total:  int
    nb_voisins_rouge:  int
    nb_voisins_orange: int
    voisins_top5:      list[dict]
    is_mock:           bool


class SortieForecast(TypedDict):
    predictions_score:     dict[str, float]  # {"m1": score, ..., "m6": score}
    tendance:              str               # "HAUSSE" | "STABLE" | "BAISSE"
    probabilite_defaut_6m: float
    mois_alerte_prevu:     int | None
    is_mock:               bool


class SortieAnomalies(TypedDict):
    score_anomalie:      float
    est_outlier:         bool
    type_anomalie:       str | None
    features_aberrantes: list[str]
    is_mock:             bool


class SortieCompliance(TypedDict):
    rapport_client:      str
    analyse_contagion:   str
    concepts_declenches: list[str]
    regles_applicables:  list[str]
    is_mock:             bool


class SortieRaisonnement(TypedDict):
    chaine_de_pensee: str
    facteurs_risque:  list[dict]   # [{"facteur", "score_impact", "source_agent"}]
    score_consensus:  float
    niveau_confiance: str          # "HAUTE" | "MOYENNE" | "FAIBLE"
    agents_mock:      list[str]
    contradictions:   list[str]


class RapportFinal(TypedDict):
    decision:             str      # "APPROUVER" | "SURVEILLER" | "REFUSER"
    score_global:         float
    alerte_finale:        str      # "VERT" | "ORANGE" | "ROUGE"
    rapport_narratif:     str
    actions_recommandees: list[str]
    horizon_reevaluation: str


class CreditMindState(TypedDict):
    # ── Input (posé par le Superviseur) ───────────────────────────
    client_id:   str
    profil_brut: ProfilBrut | None

    # ── Sorties des 5 agents parallèles ───────────────────────────
    comportement: SortieComportement | None
    reseau:       SortieReseau       | None
    forecast:     SortieForecast     | None
    anomalies:    SortieAnomalies    | None
    compliance:   SortieCompliance   | None

    # ── Sorties des agents séquentiels ────────────────────────────
    raisonnement:  SortieRaisonnement | None
    rapport_final: RapportFinal       | None

    # ── Métadonnées (accumulées par reducer) ──────────────────────
    agents_completes: Annotated[list[str], operator.add]
    erreurs:          Annotated[list[str], operator.add]
