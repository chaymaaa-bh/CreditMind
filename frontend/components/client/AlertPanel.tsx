"use client";
import { motion } from "framer-motion";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { RiskBadge } from "@/components/ui/RiskBadge";
import type { AlertResult, RiskLevel } from "@/types";

interface Props {
  alert: AlertResult;
  neo4j_id: string;
  gouvernorat?: string;
  segment?: string;
}

export function AlertPanel({ alert, neo4j_id, gouvernorat, segment }: Props) {
  const tendance = alert.tendance_m3;
  const TrendIcon = tendance > 2 ? TrendingUp : tendance < -2 ? TrendingDown : Minus;
  const trendColor = tendance > 2 ? "#ef4444" : tendance < -2 ? "#22c55e" : "#64748b";

  return (
    <div className="flex flex-col gap-4">
      {/* Identity */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "var(--muted)" }}>
            Identité
          </p>
          <p className="text-lg font-bold font-mono" style={{ color: "var(--foreground)" }}>{neo4j_id}</p>
          <div className="flex gap-2 mt-1 flex-wrap">
            {gouvernorat && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
                📍 {gouvernorat}
              </span>
            )}
            {segment && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
                {segment}
              </span>
            )}
          </div>
        </div>
        <RiskBadge level={alert.niveau_alerte as RiskLevel} size="md" />
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Prob. défaut", value: `${(alert.prob_defaut * 100).toFixed(1)}%`, color: alert.prob_defaut > 0.5 ? "#ef4444" : alert.prob_defaut > 0.2 ? "#f97316" : "#22c55e" },
          { label: "Score M5", value: `${alert.score_solvabilite}/100`, color: alert.score_solvabilite > 70 ? "#22c55e" : alert.score_solvabilite > 40 ? "#eab308" : "#ef4444" },
          { label: "GNN Risk", value: `${(alert.gnn_risk_score * 100).toFixed(0)}%`, color: alert.gnn_risk_score > 0.6 ? "#ef4444" : alert.gnn_risk_score > 0.3 ? "#f97316" : "#22c55e" },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded-lg p-3 text-center" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid var(--card-border)" }}>
            <p className="text-xs mb-1" style={{ color: "var(--muted)" }}>{label}</p>
            <p className="text-base font-bold tabular-nums" style={{ color }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tendance M3 */}
      <div className="flex items-center gap-2 rounded-lg px-3 py-2" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid var(--card-border)" }}>
        <TrendIcon size={14} style={{ color: trendColor, flexShrink: 0 }} />
        <span className="text-xs" style={{ color: "var(--muted)" }}>Tendance M3 :</span>
        <span className="text-xs font-semibold" style={{ color: trendColor }}>
          {tendance > 0 ? "+" : ""}{tendance.toFixed(2)} pts
          {tendance > 2 ? " — Risque en hausse" : tendance < -2 ? " — Risque en baisse" : " — Stable"}
        </span>
      </div>

      {/* Triggers */}
      {alert.triggers.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
            Déclencheurs d'alerte
          </p>
          {alert.triggers.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="flex items-start gap-2 rounded-lg px-3 py-2"
              style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
            >
              <AlertTriangle size={13} style={{ color: "#ef4444", marginTop: 1, flexShrink: 0 }} />
              <span className="text-xs" style={{ color: "#fca5a5" }}>{t}</span>
            </motion.div>
          ))}
        </div>
      )}

      {/* Anomaly score */}
      <div className="flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid var(--card-border)" }}>
        <span className="text-xs" style={{ color: "var(--muted)" }}>Score anomalie M4</span>
        <div className="flex items-center gap-2">
          <div className="w-24 h-1.5 rounded-full" style={{ background: "rgba(148,163,184,0.15)" }}>
            <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(alert.score_anomalie, 100)}%`, background: alert.score_anomalie > 60 ? "#ef4444" : alert.score_anomalie > 30 ? "#f97316" : "#22c55e" }} />
          </div>
          <span className="text-xs font-mono font-semibold w-10 text-right" style={{ color: "var(--foreground)" }}>
            {alert.score_anomalie.toFixed(1)}
          </span>
        </div>
      </div>
    </div>
  );
}
