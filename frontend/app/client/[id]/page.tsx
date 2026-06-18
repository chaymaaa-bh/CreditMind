"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react";
import Link from "next/link";

import { ScoreGauge } from "@/components/ui/ScoreGauge";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { AlertPanel } from "@/components/client/AlertPanel";
import { ShapWaterfall } from "@/components/client/ShapWaterfall";
import { CounterfactualPanel } from "@/components/client/CounterfactualPanel";
import { NarrativeCard } from "@/components/client/NarrativeCard";
import { api } from "@/lib/api";
import type { ClientDetail, RiskLevel } from "@/types";

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = decodeURIComponent(params.id as string);

  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.client.detail(rawId)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [rawId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Loader2 size={32} className="animate-spin" style={{ color: "#6d28d9" }} />
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Chargement SHAP + M8 pour <span className="font-mono text-blue-400">{rawId}</span>…
        </p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 px-6">
        <div className="rounded-xl p-6 text-center max-w-md w-full" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
          <p className="font-semibold mb-1" style={{ color: "#ef4444" }}>Client introuvable</p>
          <p className="text-xs mb-4" style={{ color: "#fca5a5" }}>{error}</p>
          <button onClick={() => router.push("/client")} className="text-xs underline" style={{ color: "#94a3b8" }}>
            ← Retour à la recherche
          </button>
        </div>
      </div>
    );
  }

  const { alert, shap, counterfactual } = detail;

  return (
    <div className="flex flex-col gap-5 p-6 max-w-screen-xl mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4">
        <Link href="/client" className="p-2 rounded-lg transition-colors" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
          <ArrowLeft size={16} style={{ color: "var(--muted)" }} />
        </Link>
        <div className="flex items-center gap-3 flex-1">
          <h1 className="text-xl font-bold font-mono" style={{ color: "var(--foreground)" }}>{detail.neo4j_id}</h1>
          <RiskBadge level={alert.niveau_alerte as RiskLevel} size="md" />
          {detail.gouvernorat && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
              {detail.gouvernorat}
            </span>
          )}
          {detail.segment && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
              {detail.segment}
            </span>
          )}
        </div>
        <Link
          href={`/agents?client_id=${encodeURIComponent(detail.neo4j_id)}`}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all"
          style={{ background: "rgba(59,130,246,0.12)", border: "1px solid rgba(59,130,246,0.3)", color: "#60a5fa" }}
        >
          <ExternalLink size={14} />
          Lancer analyse M7
        </Link>
      </motion.div>

      {/* Score Gauges */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-xl p-5"
        style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
      >
        <p className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--muted)" }}>
          Scores synthétiques
        </p>
        <div className="flex items-center justify-around gap-4 flex-wrap">
          <ScoreGauge value={alert.score_solvabilite} label="Score M5" size={108} />
          <ScoreGauge value={Math.round(alert.prob_defaut * 100)} label="Prob. défaut" size={108} invert />
          <ScoreGauge value={Math.round(alert.gnn_risk_score * 100)} label="Risque réseau GNN" size={108} invert />
          <ScoreGauge value={Math.round(alert.score_anomalie)} label="Score anomalie M4" size={108} invert />
        </div>
      </motion.div>

      {/* Main grid : Alert + SHAP */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl p-5"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
        >
          <AlertPanel
            alert={alert}
            neo4j_id={detail.neo4j_id}
            gouvernorat={detail.gouvernorat}
            segment={detail.segment}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="rounded-xl p-5"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
        >
          <ShapWaterfall shap={shap} />
        </motion.div>
      </div>

      {/* Second grid : CF + Narrative */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="rounded-xl p-5"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
        >
          <CounterfactualPanel cf={counterfactual} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-xl p-5"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
        >
          <NarrativeCard
            clientId={detail.neo4j_id}
            initialNarrative={detail.narrative}
            onLoaded={(updated) => setDetail(updated)}
          />
        </motion.div>
      </div>
    </div>
  );
}
