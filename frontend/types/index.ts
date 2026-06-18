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
