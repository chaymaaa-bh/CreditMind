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
