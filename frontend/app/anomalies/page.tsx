"use client";
import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { KpiCard } from "@/components/ui/KpiCard";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { api } from "@/lib/api";
import type { AnomalySummary, AnomalyAlert, AnomalyListResponse } from "@/types";

const CARD = { background: "var(--card)", border: "1px solid var(--card-border)" };
const MUTED = { color: "var(--muted)" };
const FG = { color: "var(--foreground)" };

const ALERT_COLORS: Record<string, string> = {
  ROUGE: "#ef4444",
  ORANGE: "#f97316",
  JAUNE: "#eab308",
  VERT: "#22c55e",
};

const SORT_OPTIONS = [
  { value: "score_anomalie_final", label: "Score final" },
  { value: "score_anomalie_if", label: "Isolation Forest" },
  { value: "score_anomalie_lstm", label: "LSTM" },
  { value: "retard_moyen_jours", label: "Retard (j)" },
  { value: "client_id", label: "ID client" },
];

export default function AnomaliesPage() {
  const [summary, setSummary] = useState<AnomalySummary | null>(null);
  const [data, setData] = useState<AnomalyListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [filterAlerte, setFilterAlerte] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("score_anomalie_final");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.anomalies.summary().then(setSummary).catch((e) => setError(String(e)));
  }, []);

  const fetchList = useCallback(() => {
    setLoading(true);
    api.anomalies
      .list({ page, limit: 50, alerte: filterAlerte || undefined, q: search || undefined, sort_by: sortBy, sort_dir: sortDir })
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [page, filterAlerte, search, sortBy, sortDir]);

  useEffect(() => { fetchList(); }, [fetchList]);

  function toggleSort(col: string) {
    if (sortBy === col) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
    setPage(1);
  }

  const scoreBarData = summary
    ? [
        { name: "IF", value: summary.avg_score_if, color: "#3b82f6" },
        { name: "LSTM", value: summary.avg_score_lstm, color: "#8b5cf6" },
        { name: "Final", value: summary.avg_score_final, color: "#f97316" },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-2xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold" style={FG}>
          Détection d'Anomalies M4
        </h1>
        <p className="text-sm mt-0.5" style={MUTED}>
          Ensemble Isolation Forest · LSTM · River — {summary?.total ?? "…"} alertes détectées
        </p>
      </motion.div>

      {error && (
        <div
          className="rounded-xl p-4"
          style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}
        >
          Erreur : {error}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total alertes"
          value={summary?.total ?? 0}
          accent="#3b82f6"
          sub="clients anormaux"
          delay={0}
        />
        <KpiCard
          label="Alertes ROUGE"
          value={summary?.nb_rouge ?? 0}
          accent="#ef4444"
          sub="score ≥ 0.7"
          delay={80}
        />
        <KpiCard
          label="Alertes ORANGE"
          value={summary?.nb_orange ?? 0}
          accent="#f97316"
          sub="score 0.4–0.7"
          delay={160}
        />
        <KpiCard
          label="Score anomalie moyen"
          value={(summary?.avg_score_final ?? 0) * 100}
          suffix="%"
          decimals={1}
          accent="#8b5cf6"
          sub="ensemble pondéré"
          delay={240}
        />
      </div>

      {/* Scores par modèle */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="md:col-span-1 rounded-xl p-5"
          style={CARD}
        >
          <h2 className="text-sm font-semibold mb-4" style={FG}>
            Score moyen par modèle
          </h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={scoreBarData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" horizontal={false} />
              <XAxis type="number" domain={[0, 1]} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
              <YAxis type="category" dataKey="name" tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} width={40} />
              <Tooltip
                contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8 }}
                formatter={(v) => [`${(Number(v) * 100).toFixed(2)}%`, "Score moyen"]}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {scoreBarData.map((d) => (
                  <Cell key={d.name} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Distribution alertes */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="md:col-span-2 rounded-xl p-5"
          style={CARD}
        >
          <h2 className="text-sm font-semibold mb-4" style={FG}>
            Répartition des alertes
          </h2>
          {summary && (
            <div className="flex flex-col gap-3 mt-2">
              {[
                { level: "ROUGE", nb: summary.nb_rouge, color: "#ef4444" },
                { level: "ORANGE", nb: summary.nb_orange, color: "#f97316" },
                { level: "JAUNE", nb: summary.nb_jaune, color: "#eab308" },
              ].map(({ level, nb, color }) => (
                <div key={level} className="flex items-center gap-3">
                  <span className="w-16 text-xs font-medium" style={{ color }}>{level}</span>
                  <div className="flex-1 rounded-full overflow-hidden h-3" style={{ background: "rgba(148,163,184,0.1)" }}>
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${(nb / summary.total) * 100}%`, background: color }}
                    />
                  </div>
                  <span className="w-16 text-right text-xs font-mono" style={MUTED}>
                    {nb} ({((nb / summary.total) * 100).toFixed(1)}%)
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="rounded-xl p-5"
        style={CARD}
      >
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <h2 className="text-sm font-semibold flex-1" style={FG}>
            Liste des anomalies
            {data && (
              <span className="ml-2 text-xs font-normal" style={MUTED}>
                {data.total} résultats · page {data.page}/{data.pages}
              </span>
            )}
          </h2>
          <input
            type="text"
            placeholder="Rechercher ID…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded-lg px-3 py-1.5 text-sm w-36"
            style={{ background: "rgba(148,163,184,0.07)", border: "1px solid var(--card-border)", color: "var(--foreground)", outline: "none" }}
          />
          <div className="flex gap-1">
            {["", "ROUGE", "ORANGE", "JAUNE"].map((lvl) => (
              <button
                key={lvl}
                onClick={() => { setFilterAlerte(lvl); setPage(1); }}
                className="px-2.5 py-1 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: filterAlerte === lvl ? (ALERT_COLORS[lvl] ?? "rgba(59,130,246,0.15)") : "rgba(148,163,184,0.07)",
                  color: filterAlerte === lvl ? "#fff" : "var(--muted)",
                  border: "1px solid transparent",
                }}
              >
                {lvl || "Tous"}
              </button>
            ))}
          </div>
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
            className="rounded-lg px-2 py-1.5 text-xs"
            style={{ background: "rgba(148,163,184,0.07)", border: "1px solid var(--card-border)", color: "var(--foreground)", outline: "none" }}
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--card-border)" }}>
                {[
                  { key: "client_id", label: "Client" },
                  { key: "alerte", label: "Alerte" },
                  { key: "score_anomalie_final", label: "Score final" },
                  { key: "score_anomalie_if", label: "IF" },
                  { key: "score_anomalie_lstm", label: "LSTM" },
                  { key: "nb_votes", label: "Votes" },
                  { key: "raison_principale", label: "Raison" },
                  { key: "retard_moyen_jours", label: "Retard (j)" },
                  { key: "ratio_encaissement", label: "Encaissement" },
                ].map(({ key, label }) => (
                  <th
                    key={key}
                    className="text-left py-2 pr-4 font-medium cursor-pointer select-none"
                    style={{ ...MUTED, userSelect: "none" }}
                    onClick={() => toggleSort(key)}
                  >
                    {label}
                    {sortBy === key && (
                      <span className="ml-1 opacity-60">{sortDir === "desc" ? "↓" : "↑"}</span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 9 }).map((__, j) => (
                        <td key={j} className="py-2 pr-4">
                          <div className="h-4 rounded animate-pulse" style={{ background: "rgba(148,163,184,0.08)" }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : data?.items.map((row) => (
                    <tr
                      key={row.client_id}
                      className="border-b"
                      style={{ borderColor: "var(--card-border)" }}
                    >
                      <td className="py-2 pr-4 font-mono" style={FG}>#{row.client_id}</td>
                      <td className="py-2 pr-4">
                        <RiskBadge level={row.alerte as "VERT" | "ORANGE" | "ROUGE" | "JAUNE"} />
                      </td>
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(148,163,184,0.1)" }}>
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${row.score_anomalie_final * 100}%`,
                                background: ALERT_COLORS[row.alerte] ?? "#3b82f6",
                              }}
                            />
                          </div>
                          <span className="font-mono text-xs" style={FG}>
                            {(row.score_anomalie_final * 100).toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-2 pr-4 font-mono text-xs" style={MUTED}>
                        {(row.score_anomalie_if * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 pr-4 font-mono text-xs" style={MUTED}>
                        {(row.score_anomalie_lstm * 100).toFixed(1)}%
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className="px-1.5 py-0.5 rounded text-xs font-medium"
                          style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}
                        >
                          {row.nb_votes}/3
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-xs max-w-xs truncate" style={MUTED} title={row.raison_principale}>
                        {row.raison_principale}
                      </td>
                      <td className="py-2 pr-4 font-mono text-xs" style={{ color: row.retard_moyen_jours < 0 ? "#ef4444" : "#22c55e" }}>
                        {row.retard_moyen_jours.toFixed(1)} j
                      </td>
                      <td className="py-2 font-mono text-xs" style={FG}>
                        {(row.ratio_encaissement * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-end gap-2 mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 rounded-lg text-xs disabled:opacity-30"
              style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}
            >
              ← Préc.
            </button>
            <span className="text-xs" style={MUTED}>
              {page} / {data.pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="px-3 py-1 rounded-lg text-xs disabled:opacity-30"
              style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}
            >
              Suiv. →
            </button>
          </div>
        )}
      </motion.div>
    </div>
  );
}
