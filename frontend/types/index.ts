export type RiskLevel = "VERT" | "JAUNE" | "ORANGE" | "ROUGE";

export interface RiskDistribution {
  VERT: number;
  JAUNE: number;
  ORANGE: number;
  ROUGE: number;
}

export interface PortfolioSummary {
  total: number;
  distribution: RiskDistribution;
  pct_rouge: number;
  pct_defaut: number;
  score_moyen: number;
  encours_rouge: number;
}

export interface GovernorateStats {
  gouvernorat: string;
  total: number;
  nb_rouge: number;
  nb_orange: number;
  nb_jaune: number;
  nb_vert: number;
  pct_rouge: number;
  avg_score: number;
}

export interface ClientListItem {
  client_id: number;
  neo4j_id: string;
  alerte: RiskLevel;
  prob_defaut: number;
  score_solvabilite: number;
  classe_risque: string;
  score_anomalie: number;
  gnn_risk_score: number;
  gouvernorat?: string;
  segment?: string;
}

export interface ClientListResponse {
  total: number;
  page: number;
  limit: number;
  pages: number;
  items: ClientListItem[];
}

// ── Client Detail ────────────────────────────────────────────────────────────

export interface ShapFeature {
  feature: string;
  label: string;
  shap_value: number;
  feature_value: number;
  direction: "aggrave" | "ameliore";
}

export interface ShapResult {
  base_value: number;
  top_features: ShapFeature[];
}

export interface CfSuggestion {
  feature: string;
  label: string;
  valeur_actuelle: number;
  valeur_cible: number;
  effort_pct: number;
  reduction_prob: number;
  nouvelle_prob: number;
  atteint_seuil: boolean;
}

export interface CounterfactualResult {
  current_prob: number;
  target_prob: number;
  suggestions: CfSuggestion[];
  seuil_atteignable: boolean;
  note?: string;
  message?: string;
  method: string;
}

export interface AlertResult {
  niveau_alerte: RiskLevel;
  triggers: string[];
  score_solvabilite: number;
  prob_defaut: number;
  score_anomalie: number;
  gnn_risk_score: number;
  tendance_m3: number;
  alerte_m5: string;
}

export interface ClientDetail {
  client_id: number;
  neo4j_id: string;
  gouvernorat?: string;
  segment?: string;
  alert: AlertResult;
  shap: ShapResult;
  counterfactual: CounterfactualResult;
  narrative?: string;
}

// ── M7 Agents ────────────────────────────────────────────────────────────────

export interface AgentsResult {
  client_id: string;
  decision: string;
  score_global: number;
  alerte_finale: string;
  rapport_narratif: string;
  actions_recommandees: string[];
  horizon_reevaluation: string;
  score_consensus: number;
  niveau_confiance: string;
  agents_mock: string[];
  agents_completes: string[];
  erreurs: string[];
  comportement: {
    score: number;
    niveau: string;
    signaux: string[];
    is_mock: boolean;
  };
  reseau: {
    score_gnn: number;
    score_contagion: number;
    score_final_m2: number;
    alerte: string;
    nb_voisins_total: number;
    nb_voisins_rouge: number;
    voisins_top5: Array<{ client_id: string; alerte: string; score_m2: number; type_lien: string }>;
    is_mock: boolean;
  };
  forecast: {
    tendance: string;
    probabilite_defaut_6m: number;
    predictions_score: Record<string, number>;
    mois_alerte_prevu: number | null;
    is_mock: boolean;
  };
  anomalies: {
    score_anomalie: number;
    est_outlier: boolean;
    type_anomalie: string | null;
    features_aberrantes: string[];
    is_mock: boolean;
  };
  compliance: {
    rapport_client: string;
    concepts_declenches: string[];
    is_mock: boolean;
  };
}

// ── M9 Stress Testing ────────────────────────────────────────────────────────

export interface StressIndicateurs {
  nb_clients_analyses: number;
  nb_clients_bascule_rouge: number;
  pct_bascule_rouge: number;
  delta_score_moyen: number;
  encours_a_risque_stresse: number;
  delta_retard_moyen_jours: number;
  provision_recommandee: number;
  distribution_avant: Record<string, number>;
  distribution_apres: Record<string, number>;
  clients_les_plus_impactes: Array<{
    client_id: string;
    gouvernorat: string;
    segment: string;
    alerte_baseline: string;
    alerte_stresse: string;
    score_baseline: number;
    score_stresse: number;
    encours_tnd: number;
  }>;
  ic95_EaRS: [number, number];
}

export interface StressResult {
  scenario: {
    description: string;
    categorie: string;
    intensite: string;
    duree_mois: number;
    gouvernorats_cibles: string[];
    segments_cibles: string[];
    feature_deltas: Array<{
      feature: string;
      delta_type: string;
      delta_value: number;
      std_pct: number;
    }>;
  };
  indicateurs: StressIndicateurs;
  rapport: string;
  contagion: null | {
    nb_contamines: number;
    encours_cumule: number;
    vagues: Array<{ niveau: number; clients: string[] }>;
  };
}

// ── M3 Forecast ──────────────────────────────────────────────────────────────

export interface PortfolioForecastPoint {
  horizon_mois: number;
  retard_moyen_prevu: number;
  retard_lower_80: number;
  retard_upper_80: number;
  montant_regle_total_prevu: number;
  ratio_regle_portf_prevu: number;
  encours_total_prevu: number;
}

export interface ClientForecastPoint {
  horizon_mois: number;
  montant_regle_pred: number;
  lower_80: number;
  upper_80: number;
  retard_pred: number;
  risque_tendance: number;
  alerte_prev: string;
}

export interface ClientForecastResponse {
  client_id: number;
  model: string;
  points: ClientForecastPoint[];
}

// ── M4 Anomalies ─────────────────────────────────────────────────────────────

export interface AnomalySummary {
  total: number;
  nb_rouge: number;
  nb_orange: number;
  nb_jaune: number;
  avg_score_final: number;
  avg_score_if: number;
  avg_score_lstm: number;
}

export interface AnomalyAlert {
  client_id: number;
  alerte: string;
  score_anomalie_final: number;
  score_anomalie_if: number;
  score_anomalie_lstm: number;
  score_anomalie_river: number;
  nb_votes: number;
  raison_principale: string;
  retard_moyen_jours: number;
  taux_retard: number;
  ratio_encaissement: number;
  montant_ttc_moyen: number;
}

export interface AnomalyListResponse {
  total: number;
  page: number;
  limit: number;
  pages: number;
  items: AnomalyAlert[];
}

// ── M2 Network ───────────────────────────────────────────────────────────────

export interface NetworkNode {
  client_id: number;
  neo4j_id: string;
  alerte: RiskLevel;
  score_m2: number;
  prob_defaut: number;
  gouvernorat?: string;
  segment?: string;
  is_center: boolean;
}

export interface NetworkGraph {
  center: NetworkNode;
  neighbors: NetworkNode[];
  total_gouvernorat: number;
  lien_type: string;
}
