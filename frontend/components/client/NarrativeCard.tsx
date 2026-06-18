"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ClientDetail } from "@/types";

interface Props {
  clientId: string;
  initialNarrative?: string;
  onLoaded?: (detail: ClientDetail) => void;
}

export function NarrativeCard({ clientId, initialNarrative, onLoaded }: Props) {
  const [narrative, setNarrative] = useState(initialNarrative ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const detail = await api.client.detail(clientId, true);
      setNarrative(detail.narrative ?? "Narrative non disponible.");
      onLoaded?.(detail);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--foreground)" }}>
          <Sparkles size={14} style={{ color: "#8b5cf6" }} />
          Analyse narrative — Claude
        </h3>
        {!narrative && (
          <button
            onClick={generate}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
            style={{
              background: loading ? "rgba(139,92,246,0.1)" : "rgba(139,92,246,0.15)",
              border: "1px solid rgba(139,92,246,0.3)",
              color: "#a78bfa",
            }}
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            {loading ? "Génération…" : "Générer l'analyse"}
          </button>
        )}
      </div>

      <AnimatePresence mode="wait">
        {narrative ? (
          <motion.div
            key="narrative"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl p-4 text-sm leading-relaxed"
            style={{
              background: "rgba(139,92,246,0.06)",
              border: "1px solid rgba(139,92,246,0.2)",
              color: "#e2e8f0",
              whiteSpace: "pre-wrap",
            }}
          >
            {narrative}
          </motion.div>
        ) : loading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rounded-xl p-6 flex flex-col items-center gap-3"
            style={{ background: "rgba(139,92,246,0.05)", border: "1px solid rgba(139,92,246,0.15)" }}
          >
            <Loader2 size={24} className="animate-spin" style={{ color: "#8b5cf6" }} />
            <p className="text-xs" style={{ color: "#a78bfa" }}>Claude analyse le profil de risque…</p>
          </motion.div>
        ) : (
          <motion.div
            key="placeholder"
            className="rounded-xl p-4 text-center"
            style={{ background: "rgba(148,163,184,0.04)", border: "1px dashed rgba(148,163,184,0.2)" }}
          >
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              Cliquez sur <strong style={{ color: "#a78bfa" }}>Générer l'analyse</strong> pour obtenir une explication en langage naturel du profil de risque de ce client par Claude.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p className="text-xs rounded-lg px-3 py-2" style={{ background: "rgba(239,68,68,0.08)", color: "#fca5a5" }}>
          Erreur : {error}
        </p>
      )}
    </div>
  );
}
