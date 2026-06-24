"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { KpiCard } from "@/components/ui/KpiCard";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { api } from "@/lib/api";
import type { PortfolioForecastPoint, ClientForecastResponse } from "@/types";

const CARD = { background: "var(--card)", border: "1px solid var(--card-border)" };
const MUTED = { color: "var(--muted)" };
const FG = { color: "var(--foreground)" };

function fmt(n: number) {
  return n.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
}

export default function ForecastPage() {
  const [portfolio, setPortfolio] = useState<PortfolioForecastPoint[]>([]);
  const [topAlerts, setTopAlerts] = useState<Record<string, number | string>[]>([]);
  const [clientId, setClientId] = useState("");
  const [clientForecast, setClientForecast] = useState<ClientForecastResponse | null>(null);
  const [clientLoading, setClientLoading] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.forecast.portfolio(), api.forecast.topAlerts(15)])
      .then(([p, t]) => {
        setPortfolio(p);
        setTopAlerts(t);
      })
      .catch((e) => setError(String(e)));
  }, []);

  function loadClient() {
    const id = parseInt(clientId.trim(), 10);
    if (isNaN(id)) return;
    setClientLoading(true);
    setClientError(null);
    setClientForecast(null);
    api.forecast
      .client(id)
      .then(setClientForecast)
      .catch((e) => setClientError(String(e)))
      .finally(() => setClientLoading(false));
  }

  const lastPoint = portfolio[portfolio.length - 1];
  const firstPoint = portfolio[0];

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-2xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold" style={FG}>
          Prévisions Temporelles M3
        </h1>
        <p className="text-sm mt-0.5" style={MUTED}>
          Modèle N-HiTS — Horizon 6 mois · Intervalle de confiance 80%
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

      {/* KPIs portefeuille */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Retard moyen prévu (M1)"
          value={firstPoint?.retard_moyen_prevu ?? 0}
          suffix=" j"
          decimals={1}
          accent="#3b82f6"
          sub="horizon 1 mois"
          delay={0}
        />
        <KpiCard
          label="Retard moyen prévu (M6)"
          value={lastPoint?.retard_moyen_prevu ?? 0}
          suffix=" j"
          decimals={1}
          accent="#f97316"
          sub="horizon 6 mois"
          delay={80}
        />
        <KpiCard
          label="Encours total prévu (M6)"
          value={(lastPoint?.encours_total_prevu ?? 0) / 1000}
          suffix=" k TND"
          decimals={0}
          accent="#8b5cf6"
          sub="portefeuille"
          delay={160}
        />
        <KpiCard
          label="Ratio règlement prévu"
          value={(lastPoint?.ratio_regle_portf_prevu ?? 0) * 100}
          suffix="%"
          decimals={1}
          accent="#22c55e"
          sub="M12 M6 vs encours"
          delay={240}
        />
      </div>

      {/* Graphique portfolio retard */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="rounded-xl p-5"
        style={CARD}
      >
        <h2 className="text-sm font-semibold mb-4" style={FG}>
          Évolution du retard moyen prévu — Portefeuille (IC 80%)
        </h2>
        {portfolio.length === 0 ? (
          <div className="h-64 animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={portfolio} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
              <XAxis
                dataKey="horizon_mois"
                tickFormatter={(v) => `M${v}`}
                tick={{ fill: "var(--muted)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--muted)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v} j`}
              />
              <Tooltip
                contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8 }}
                labelFormatter={(v) => `Horizon M${v}`}
                formatter={(value, name) => {
                  const labels: Record<string, string> = {
                    retard_upper_80: "IC sup 80%",
                    retard_moyen_prevu: "Retard prévu",
                    retard_lower_80: "IC inf 80%",
                  };
                  return [`${Number(value).toFixed(2)} j`, labels[String(name)] ?? String(name)];
                }}
              />
              <Area
                type="monotone"
                dataKey="retard_upper_80"
                stroke="transparent"
                fill="url(#bandGrad)"
                name="retard_upper_80"
              />
              <Line
                type="monotone"
                dataKey="retard_moyen_prevu"
                stroke="#3b82f6"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#3b82f6" }}
                name="retard_moyen_prevu"
              />
              <Line
                type="monotone"
                dataKey="retard_lower_80"
                stroke="#3b82f6"
                strokeWidth={1}
                strokeDasharray="4 3"
                dot={false}
                name="retard_lower_80"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </motion.div>

      {/* Graphique encours + montant réglé */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.25 }}
          className="rounded-xl p-5"
          style={CARD}
        >
          <h2 className="text-sm font-semibold mb-4" style={FG}>
            Encours total prévu (TND)
          </h2>
          {portfolio.length === 0 ? (
            <div className="h-48 animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={portfolio} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="encGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="horizon_mois" tickFormatter={(v) => `M${v}`} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${fmt(v / 1000)}k`} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8 }}
                  labelFormatter={(v) => `M${v}`}
                  formatter={(v) => [`${fmt(Number(v))} TND`, "Encours"]}
                />
                <Area type="monotone" dataKey="encours_total_prevu" stroke="#8b5cf6" strokeWidth={2} fill="url(#encGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl p-5"
          style={CARD}
        >
          <h2 className="text-sm font-semibold mb-4" style={FG}>
            Montant réglé prévu (TND)
          </h2>
          {portfolio.length === 0 ? (
            <div className="h-48 animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={portfolio} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="montGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="horizon_mois" tickFormatter={(v) => `M${v}`} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${fmt(v / 1000)}k`} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8 }}
                  labelFormatter={(v) => `M${v}`}
                  formatter={(v) => [`${fmt(Number(v))} TND`, "Réglé"]}
                />
                <Area type="monotone" dataKey="montant_regle_total_prevu" stroke="#22c55e" strokeWidth={2} fill="url(#montGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </motion.div>
      </div>

      {/* Prévision individuelle */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="rounded-xl p-5"
        style={CARD}
      >
        <h2 className="text-sm font-semibold mb-4" style={FG}>
          Prévision client individuelle
        </h2>
        <div className="flex gap-3 mb-5">
          <input
            type="number"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadClient()}
            placeholder="ID client (ex: 608)"
            className="rounded-lg px-4 py-2 text-sm flex-1 max-w-xs"
            style={{
              background: "rgba(148,163,184,0.07)",
              border: "1px solid var(--card-border)",
              color: "var(--foreground)",
              outline: "none",
            }}
          />
          <button
            onClick={loadClient}
            disabled={clientLoading}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity"
            style={{ background: "#3b82f6", color: "#fff", opacity: clientLoading ? 0.6 : 1 }}
          >
            {clientLoading ? "Chargement…" : "Analyser"}
          </button>
        </div>

        {clientError && (
          <p className="text-sm mb-4" style={{ color: "#ef4444" }}>
            {clientError}
          </p>
        )}

        {clientForecast && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium" style={FG}>
                Client #{clientForecast.client_id}
              </span>
              <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
                {clientForecast.model}
              </span>
              {clientForecast.points.map((p) => (
                <span key={p.horizon_mois} className="flex items-center gap-1 text-xs" style={{ color: "var(--muted)" }}>
                  M{p.horizon_mois}:&nbsp;<RiskBadge level={p.alerte_prev as "VERT" | "ORANGE" | "ROUGE" | "JAUNE"} size="xs" />
                </span>
              ))}
            </div>

            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={clientForecast.points} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="horizon_mois" tickFormatter={(v) => `M${v}`} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 8 }}
                  labelFormatter={(v) => `Horizon M${v}`}
                  formatter={(value, name) => {
                    if (name === "retard_pred") return [`${Number(value).toFixed(2)} j`, "Retard prévu"];
                    return [String(value), String(name)];
                  }}
                />
                <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" />
                <Line type="monotone" dataKey="retard_pred" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 5, fill: "#3b82f6" }} name="retard_pred" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </motion.div>

      {/* Top clients à risque prévu */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="rounded-xl p-5"
        style={CARD}
      >
        <h2 className="text-sm font-semibold mb-4" style={FG}>
          Clients avec la plus forte tendance de risque prévue (Top 15)
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--card-border)" }}>
                {["Client ID", "Tendance max", "Alerte M1"].map((h) => (
                  <th key={h} className="text-left py-2 pr-4 font-medium" style={MUTED}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topAlerts.map((row) => (
                <tr
                  key={row.client_id}
                  className="border-b transition-colors cursor-pointer"
                  style={{ borderColor: "var(--card-border)" }}
                  onClick={() => {
                    setClientId(String(row.client_id));
                    setTimeout(loadClient, 50);
                  }}
                >
                  <td className="py-2 pr-4 font-mono" style={FG}>
                    #{row.client_id}
                  </td>
                  <td className="py-2 pr-4">
                    <span style={{ color: "#f97316" }}>{Number(row.max_risque_tendance).toFixed(4)}</span>
                  </td>
                  <td className="py-2">
                    <RiskBadge level={(row.alerte_prev as "VERT" | "ORANGE" | "ROUGE" | "JAUNE") ?? "VERT"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
