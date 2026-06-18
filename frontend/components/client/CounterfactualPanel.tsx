"use client";
import { motion } from "framer-motion";
import { CheckCircle, Circle, Info } from "lucide-react";
import type { CounterfactualResult } from "@/types";

interface Props { cf: CounterfactualResult }

export function CounterfactualPanel({ cf }: Props) {
  const hasMessage = !!cf.message;
  const noSuggestions = cf.suggestions.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          Actions recommandées
        </h3>
        <div className="text-right shrink-0">
          <p className="text-xs" style={{ color: "var(--muted)" }}>Prob. actuelle</p>
          <p className="text-base font-bold tabular-nums" style={{ color: cf.current_prob > 0.5 ? "#ef4444" : "#f97316" }}>
            {(cf.current_prob * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Target */}
      <div className="flex items-center justify-between rounded-lg px-3 py-2" style={{ background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.2)" }}>
        <span className="text-xs" style={{ color: "#86efac" }}>Objectif cible</span>
        <span className="text-sm font-bold" style={{ color: "#22c55e" }}>
          ≤ {(cf.target_prob * 100).toFixed(0)}%
          {cf.seuil_atteignable ? " ✓ atteignable" : " — hors portée à court terme"}
        </span>
      </div>

      {/* If no suggestions / just a message */}
      {(hasMessage || noSuggestions) && (
        <div className="flex items-start gap-2 rounded-lg px-3 py-3" style={{ background: "rgba(59,130,246,0.06)", border: "1px solid rgba(59,130,246,0.2)" }}>
          <Info size={14} style={{ color: "#60a5fa", marginTop: 1, flexShrink: 0 }} />
          <p className="text-xs" style={{ color: "#93c5fd" }}>
            {cf.message ?? "Aucune action actionnelle identifiée."}
          </p>
        </div>
      )}

      {/* Suggestions */}
      {cf.suggestions.map((s, i) => {
        const delta = s.reduction_prob;
        const barW = Math.min(100, (delta / cf.current_prob) * 100 * 3);
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }}
            className="rounded-lg p-3 flex flex-col gap-2"
            style={{ background: "rgba(148,163,184,0.04)", border: "1px solid var(--card-border)" }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                {s.atteint_seuil
                  ? <CheckCircle size={13} style={{ color: "#22c55e", flexShrink: 0 }} />
                  : <Circle size={13} style={{ color: "var(--muted)", flexShrink: 0 }} />
                }
                <span className="text-xs font-medium" style={{ color: "var(--foreground)" }}>{s.label}</span>
              </div>
              <span className="text-xs tabular-nums shrink-0" style={{ color: "var(--muted)" }}>
                effort {s.effort_pct}%
              </span>
            </div>

            {/* Probability arrow */}
            <div className="flex items-center gap-2 text-xs tabular-nums">
              <span style={{ color: "#ef4444", fontWeight: 600 }}>{(cf.current_prob * 100).toFixed(1)}%</span>
              <span style={{ color: "var(--muted)" }}>→</span>
              <span style={{ color: "#22c55e", fontWeight: 600 }}>{(s.nouvelle_prob * 100).toFixed(1)}%</span>
              <span style={{ color: "#22c55e" }}>(-{(delta * 100).toFixed(1)} pts)</span>
            </div>

            {/* Impact bar */}
            <div className="h-1 rounded-full" style={{ background: "rgba(148,163,184,0.1)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${barW}%`,
                  background: s.atteint_seuil ? "#22c55e" : "#3b82f6",
                }}
              />
            </div>
          </motion.div>
        );
      })}

      {cf.note && (
        <p className="text-xs italic" style={{ color: "var(--muted)" }}>{cf.note}</p>
      )}
    </div>
  );
}
