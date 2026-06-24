import type {
  ClientListResponse,
  GovernorateStats,
  PortfolioSummary,
  ClientDetail,
  AgentsResult,
  StressResult,
  NetworkGraph,
  PortfolioForecastPoint,
  ClientForecastResponse,
  AnomalySummary,
  AnomalyListResponse,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  portfolio: {
    summary: () => get<PortfolioSummary>("/api/portfolio/summary"),
    byGovernorate: () => get<GovernorateStats[]>("/api/portfolio/by-governorate"),
    clients: (params: {
      page?: number;
      limit?: number;
      alert?: string;
      q?: string;
      gouvernorat?: string;
      sort_by?: string;
      sort_dir?: string;
    }) => {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
      });
      return get<ClientListResponse>(`/api/portfolio/clients?${qs}`);
    },
  },
  client: {
    detail: (id: string, withNarrative = false) =>
      get<ClientDetail>(`/api/client/${encodeURIComponent(id)}${withNarrative ? "?with_narrative=true" : ""}`),
  },
  agents: {
    run: (id: string) => get<AgentsResult>(`/api/agents/${encodeURIComponent(id)}`),
  },
  stress: {
    run: (scenario: string, n_simulations = 200) =>
      fetch(`${BASE}/api/stress/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, n_simulations }),
      }).then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail ?? `API stress/run → ${res.status}`);
        }
        return res.json() as Promise<StressResult>;
      }),
  },
  network: {
    graph: (id: string, limit = 30) =>
      get<NetworkGraph>(`/api/network/${encodeURIComponent(id)}?limit=${limit}`),
  },
  forecast: {
    portfolio: () => get<PortfolioForecastPoint[]>("/api/forecast/portfolio"),
    client: (id: number) => get<ClientForecastResponse>(`/api/forecast/client/${id}`),
    topAlerts: (limit = 20) => get<Record<string, number | string>[]>(`/api/forecast/alerts/top?limit=${limit}`),
  },
  anomalies: {
    summary: () => get<AnomalySummary>("/api/anomalies/summary"),
    list: (params: { page?: number; limit?: number; alerte?: string; q?: string; sort_by?: string; sort_dir?: string }) => {
      const qs = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
      });
      return get<AnomalyListResponse>(`/api/anomalies/list?${qs}`);
    },
  },
};
