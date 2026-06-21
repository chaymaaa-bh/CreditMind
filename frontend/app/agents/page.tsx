"use client";
import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, ArrowRight, CheckCircle2, Circle, AlertTriangle,
  TrendingUp, TrendingDown, Minus, Loader2,
} from "lucide-react";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { ScoreGauge } from "@/components/ui/ScoreGauge";
import { api } from "@/lib/api";
import type { AgentsResult, RiskLevel } from "@/types";

const AGENT_LABELS: Record<string, string> = {
  superviseur:    "Superviseur",
  comportement:   "Comportement",
  reseau:         "Réseau GNN",
  forecast:       "Forecast M3",
  anomalies:      "Anomalies M4",
  compliance:     "Compliance",
  raisonnement:   "Raisonnement",
  rapport:        "Rapport final",
};

const DECISION_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  APPROUVER: { color: "#22c55e", bg: "rgba(34,197,94,0.1)",   label: "Approuver" },
  SURVEILLER:{ color: "#f97316", bg: "rgba(249,115,22,0.1)", label: "Surveiller" },
  REFUSER:   { color: "#ef4444", bg: "rgba(239,68,68,0.1)",   label: "Refuser" },
};

const TENDANCE_ICONS: Record<string, React.ReactNode> = {
  HAUSSE: <TrendingUp size={14} />,
  BAISSE: <TrendingDown size={14} />,
  STABLE: <Minus size={14} />,
};

const EXEMPLES = ["R_42", "S_1078", "R_1664", "S_5000"];

function AgentBadge({ name, done, isMock }: { name: string; done: boolean; isMock?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done
        ? <CheckCircle2 size={14} style={{ color: isMock ? "#f97316" : "#22c55e" }} />
        : <Circle size={14} style={{ color: "var(--muted)" }} />}
      <span style={{ color: done ? "var(--foreground)" : "var(--muted)" }}>
        {AGENT_LABELS[name] ?? name}
      </span>
      {isMock && done && (
        <span className="text-xs px-1.5 rounded" style={{ background: "rgba(249,115,22,0.15)", color: "#f97316" }}>
          mock
        </span>
      )}
    </div>
  );
}

function ScoreBar({ label, value, max = 100, accent }: { label: string; value: number; max?: number; accent: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1" style={{ color: "var(--muted)" }}>
        <span>{label}</span>
        <span style={{ color: accent }}>{value.toFixed(1)}</span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: accent }} />
      </div>
    </div>
  );
}

function AgentsPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [query, setQuery] = useState(searchParams.get("client_id") ?? "");
  const [result, setResult] = useState<AgentsResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = useCallback((id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResult(null);
    router.replace(`/agents?client_id=${encodeURIComponent(trimmed)}`, { scroll: false });
    api.agents.run(trimmed)
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    const id = searchParams.get("client_id");
    if (id) {
      setQuery(id);
      runAnalysis(id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const decCfg = result ? (DECISION_CONFIG[result.decision] ?? DECISION_CONFIG["SURVEILLER"]) : null;
  const allAgents = Object.keys(AGENT_LABELS);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      {/* Header + search */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>Analyse M7 — Multi-agents</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
            Pipeline LangGraph : 5 agents parallèles + raisonnement + rapport final
          </p>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); runAnalysis(query); }}
          className="flex gap-2 max-w-md"
        >
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input
              type="text"
              placeholder="R_42, S_1078…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-xl pl-9 pr-4 py-2.5 text-sm outline-none"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium"
            style={{ background: "#6d28d9", color: "white", opacity: loading ? 0.7 : 1 }}
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />}
            Analyser
          </button>
        </form>
        <div className="flex gap-2">
          {EXEMPLES.map((id) => (
            <button
              key={id}
              onClick={() => { setQuery(id); runAnalysis(id); }}
              className="px-2.5 py-1 rounded-lg text-xs font-mono"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "#93c5fd" }}
            >
              {id}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Loading */}
      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="rounded-xl p-6"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            <div className="flex items-center gap-3 mb-5">
              <Loader2 size={20} className="animate-spin" style={{ color: "#8b5cf6" }} />
              <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                Pipeline M7 en cours pour <span className="font-mono text-purple-400">{query}</span>…
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {allAgents.map((n) => <AgentBadge key={n} name={n} done={false} />)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl p-5" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={16} style={{ color: "#ef4444" }} />
            <span className="font-semibold text-sm" style={{ color: "#ef4444" }}>Erreur M7</span>
          </div>
          <p className="text-xs" style={{ color: "#fca5a5" }}>{error}</p>
        </div>
      )}

      {/* Results */}
      <AnimatePresence>
        {result && !loading && (
          <motion.div
            key={result.client_id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-5"
          >
            {/* Decision banner */}
            {decCfg && (
              <div
                className="rounded-xl p-5 flex items-center justify-between gap-4"
                style={{ background: decCfg.bg, border: `1px solid ${decCfg.color}40` }}
              >
                <div>
                  <p className="text-xs uppercase tracking-wider mb-1" style={{ color: decCfg.color }}>Décision finale</p>
                  <p className="text-3xl font-bold" style={{ color: decCfg.color }}>{decCfg.label}</p>
                  <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>{result.horizon_reevaluation}</p>
                </div>
                <div className="flex items-center gap-6">
                  <ScoreGauge value={result.score_global} label="Score global" size={96} />
                  <div className="flex flex-col gap-2 text-right">
                    <div>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Alerte finale</p>
                      <RiskBadge level={result.alerte_finale as RiskLevel} size="md" />
                    </div>
                    <div>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Confiance</p>
                      <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>{result.niveau_confiance}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              {/* Left : agents + scores */}
              <div className="flex flex-col gap-4">
                {/* Agents pipeline */}
                <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--muted)" }}>
                    Pipeline agents
                  </p>
                  <div className="flex flex-col gap-3">
                    {allAgents.map((n) => {
                      const done = result.agents_completes.includes(n);
                      const isMock =
                        (n === "comportement" && result.comportement?.is_mock) ||
                        (n === "reseau" && result.reseau?.is_mock) ||
                        (n === "forecast" && result.forecast?.is_mock) ||
                        (n === "anomalies" && result.anomalies?.is_mock) ||
                        (n === "compliance" && result.compliance?.is_mock);
                      return <AgentBadge key={n} name={n} done={done} isMock={isMock} />;
                    })}
                  </div>
                  {result.agents_mock.length > 0 && (
                    <p className="text-xs mt-3 pt-3" style={{ borderTop: "1px solid var(--card-border)", color: "var(--muted)" }}>
                      Neo4j indisponible — {result.agents_mock.length} agent(s) en mode mock
                    </p>
                  )}
                </div>

                {/* Scores synthèse */}
                <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--muted)" }}>
                    Scores par dimension
                  </p>
                  <div className="flex flex-col gap-3">
                    <ScoreBar label="Comportement" value={result.comportement.score} accent="#3b82f6" />
                    <ScoreBar label="Réseau GNN (M2)" value={result.reseau.score_final_m2} accent="#8b5cf6" />
                    <ScoreBar label="Anomalie (M4)" value={result.anomalies.score_anomalie * 100} accent="#f97316" />
                    <ScoreBar label="Prob. défaut 6m" value={result.forecast.probabilite_defaut_6m * 100} accent="#ef4444" />
                  </div>
                </div>
              </div>

              {/* Center : narrative + actions */}
              <div className="lg:col-span-2 flex flex-col gap-4">
                {/* Rapport narratif */}
                <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                    Rapport narratif
                  </p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--foreground)" }}>
                    {result.rapport_narratif || "Aucun rapport disponible."}
                  </p>
                </div>

                {/* Actions recommandées */}
                {result.actions_recommandees.length > 0 && (
                  <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                      Actions recommandées
                    </p>
                    <ol className="flex flex-col gap-2">
                      {result.actions_recommandees.map((a, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <span
                            className="shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center font-bold mt-0.5"
                            style={{ background: "rgba(139,92,246,0.2)", color: "#a78bfa" }}
                          >
                            {i + 1}
                          </span>
                          <span style={{ color: "var(--foreground)" }}>{a}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Agents detail row */}
                <div className="grid grid-cols-2 gap-3">
                  {/* Forecast */}
                  <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                      Forecast M3
                    </p>
                    <div className="flex items-center gap-2 mb-2">
                      <span style={{ color: result.forecast.tendance === "HAUSSE" ? "#ef4444" : result.forecast.tendance === "BAISSE" ? "#22c55e" : "#94a3b8" }}>
                        {TENDANCE_ICONS[result.forecast.tendance] ?? <Minus size={14} />}
                      </span>
                      <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                        {result.forecast.tendance}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      Prob. défaut 6m : <span style={{ color: "#f97316" }}>{(result.forecast.probabilite_defaut_6m * 100).toFixed(1)}%</span>
                    </p>
                    {result.forecast.mois_alerte_prevu && (
                      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                        Alerte prévue : mois {result.forecast.mois_alerte_prevu}
                      </p>
                    )}
                  </div>

                  {/* Anomalies */}
                  <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                      Anomalies M4
                    </p>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ background: result.anomalies.est_outlier ? "#ef4444" : "#22c55e" }}
                      />
                      <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                        {result.anomalies.est_outlier ? "Outlier détecté" : "Profil normal"}
                      </span>
                    </div>
                    {result.anomalies.features_aberrantes.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {result.anomalies.features_aberrantes.slice(0, 3).map((f) => (
                          <span key={f} className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(249,115,22,0.1)", color: "#f97316" }}>
                            {f}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Réseau */}
                  <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                      Réseau GNN
                    </p>
                    <div className="flex flex-col gap-1 text-xs">
                      <span style={{ color: "var(--muted)" }}>
                        Voisins totaux : <span style={{ color: "var(--foreground)" }}>{result.reseau.nb_voisins_total}</span>
                      </span>
                      <span style={{ color: "var(--muted)" }}>
                        Voisins ROUGE : <span style={{ color: "#ef4444" }}>{result.reseau.nb_voisins_rouge}</span>
                      </span>
                      <span style={{ color: "var(--muted)" }}>
                        Score final M2 : <span style={{ color: "#8b5cf6" }}>{result.reseau.score_final_m2.toFixed(1)}</span>
                      </span>
                    </div>
                  </div>

                  {/* Compliance */}
                  <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                    <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                      Compliance M6
                    </p>
                    {result.compliance.concepts_declenches.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {result.compliance.concepts_declenches.slice(0, 4).map((c) => (
                          <span key={c} className="text-xs px-1.5 py-0.5 rounded" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Aucun concept déclenché</p>
                    )}
                    {result.compliance.rapport_client && (
                      <p className="text-xs mt-2 line-clamp-2" style={{ color: "var(--muted)" }}>
                        {result.compliance.rapport_client}
                      </p>
                    )}
                  </div>
                </div>

                {/* Erreurs */}
                {result.erreurs.length > 0 && (
                  <div className="rounded-xl p-4" style={{ background: "rgba(249,115,22,0.06)", border: "1px solid rgba(249,115,22,0.2)" }}>
                    <p className="text-xs font-semibold mb-2" style={{ color: "#f97316" }}>Avertissements</p>
                    {result.erreurs.map((e, i) => (
                      <p key={i} className="text-xs" style={{ color: "#fdba74" }}>⚠ {e}</p>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!loading && !result && !error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-24 gap-3"
        >
          <div className="text-4xl">◎</div>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Entrez un identifiant client et lancez l'analyse multi-agents
          </p>
        </motion.div>
      )}
    </div>
  );
}

export default function AgentsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-64">
        <Loader2 size={24} className="animate-spin" style={{ color: "#8b5cf6" }} />
      </div>
    }>
      <AgentsPageInner />
    </Suspense>
  );
}
