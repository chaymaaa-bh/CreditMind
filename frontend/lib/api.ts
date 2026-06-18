import type {
  ClientListResponse,
  GovernorateStats,
  PortfolioSummary,
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
};
