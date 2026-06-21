"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, AlertTriangle, Send, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { StressResult } from "@/types";

const EXAMPLES = [
  { label: "Inflation énergie +30%", text: "Hausse des prix de l'énergie et des matières premières de 30% sur 6 mois sur tout le portefeuille" },
  { label: "Sécheresse Sfax", text: "Sécheresse grave dans les gouvernorats de Sfax et Gabes affectant les entreprises agroalimentaires" },
  { label: "Contraction crédit", text: "Contraction sévère du crédit bancaire de 25% suite à une crise de liquidité bancaire sur 12 mois" },
  { label: "Choc de change", text: "Dépréciation du dinar tunisien de 20% face à l'euro entraînant une hausse des coûts d'importation" },
];

const NIVEAU_COLORS: Record<string, string> = {
  VERT:   "#22c55e",
  ORANGE: "#f97316",
  ROUGE:  "#ef4444",
  FAIBLE: "#22c55e",
  MODERE: "#f97316",
  SEVERE: "#ef4444",
};

function fmt(n: number) {
  return n.toLocaleString("fr-FR");
}

function KpiStress({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent: string }) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
      <p className="text-xs uppercase tracking-wider mb-1" style={{ color: "var(--muted)" }}>{label}</p>
      <p className="text-xl font-bold" style={{ color: accent }}>{value}</p>
      {sub && <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{sub}</p>}
    </div>
  );
}

function DistributionRow({ label, avant, apres }: { label: string; avant: number; apres: number }) {
  const delta = apres - avant;
  const color = NIVEAU_COLORS[label] ?? "var(--foreground)";
  return (
    <div className="flex items-center gap-3 py-2" style={{ borderBottom: "1px solid var(--card-border)" }}>
      <span className="w-16 text-xs font-semibold" style={{ color }}>{label}</span>
      <span className="w-20 text-sm text-right" style={{ color: "var(--muted)" }}>{fmt(avant)}</span>
      <ChevronRight size={12} style={{ color: "var(--muted)" }} />
      <span className="w-20 text-sm text-right font-medium" style={{ color: "var(--foreground)" }}>{fmt(apres)}</span>
      <span
        className="ml-auto text-xs font-mono"
        style={{ color: delta > 0 ? "#ef4444" : delta < 0 ? "#22c55e" : "var(--muted)" }}
      >
        {delta > 0 ? "+" : ""}{fmt(delta)}
      </span>
    </div>
  );
}

export default function StressPage() {
  const [text, setText] = useState("");
  const [nSim, setNSim] = useState(200);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StressResult | null>(null);

  const submit = (scenario: string) => {
    const s = scenario.trim();
    if (!s) return;
    setLoading(true);
    setError(null);
    setResult(null);
    api.stress.run(s, nSim)
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  const ind = result?.indicateurs;
  const sc  = result?.scenario;

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>Stress Test M9</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
          Simulation Monte Carlo — décrivez un scénario de crise en langage naturel
        </p>
      </motion.div>

      {/* Form */}
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        className="rounded-xl p-5"
        style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
      >
        <textarea
          rows={3}
          placeholder="Ex : Hausse des prix de l'énergie de 30% sur 6 mois affectant tout le portefeuille…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-lg p-3 text-sm resize-none outline-none"
          style={{ background: "rgba(148,163,184,0.05)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
        />
        <div className="flex items-center justify-between mt-3 gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs" style={{ color: "var(--muted)" }}>Simulations</label>
            <select
              value={nSim}
              onChange={(e) => setNSim(Number(e.target.value))}
              className="text-xs rounded-lg px-2 py-1 outline-none"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
            >
              <option value={100}>100 (rapide)</option>
              <option value={200}>200</option>
              <option value={500}>500 (précis)</option>
            </select>
          </div>
          <button
            onClick={() => submit(text)}
            disabled={loading || !text.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium"
            style={{ background: "#6d28d9", color: "white", opacity: (loading || !text.trim()) ? 0.6 : 1 }}
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Lancer le stress-test
          </button>
        </div>

        {/* Examples */}
        <div className="flex flex-wrap gap-2 mt-3 pt-3" style={{ borderTop: "1px solid var(--card-border)" }}>
          <span className="text-xs self-center" style={{ color: "var(--muted)" }}>Exemples :</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => { setText(ex.text); submit(ex.text); }}
              className="px-2.5 py-1 rounded-lg text-xs"
              style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)", color: "#60a5fa" }}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Loading */}
      <AnimatePresence>
        {loading && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-4 rounded-xl p-5"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            <Loader2 size={24} className="animate-spin shrink-0" style={{ color: "#8b5cf6" }} />
            <div>
              <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                Parsing scénario (Claude) + simulation Monte Carlo ({nSim} runs)…
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                Peut prendre 15–60 secondes selon la taille du périmètre
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl p-5" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={16} style={{ color: "#ef4444" }} />
            <span className="font-semibold text-sm" style={{ color: "#ef4444" }}>Erreur M9</span>
          </div>
          <p className="text-xs" style={{ color: "#fca5a5" }}>{error}</p>
        </div>
      )}

      {/* Results */}
      <AnimatePresence>
        {result && !loading && ind && sc && (
          <motion.div
            key={sc.description}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-5"
          >
            {/* Scenario recap */}
            <div className="rounded-xl p-4 flex flex-wrap gap-3 items-center"
              style={{ background: "rgba(139,92,246,0.06)", border: "1px solid rgba(139,92,246,0.2)" }}
            >
              <span
                className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{ background: NIVEAU_COLORS[sc.intensite] + "22", color: NIVEAU_COLORS[sc.intensite] }}
              >
                {sc.intensite}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
                {sc.categorie.replace("_", " ")}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(148,163,184,0.1)", color: "var(--muted)" }}>
                {sc.duree_mois} mois
              </span>
              {sc.gouvernorats_cibles.length > 0 && (
                <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(59,130,246,0.1)", color: "#60a5fa" }}>
                  {sc.gouvernorats_cibles.join(", ")}
                </span>
              )}
              <span className="text-sm ml-auto" style={{ color: "var(--muted)" }}>
                {fmt(ind.nb_clients_analyses)} clients analysés
              </span>
            </div>

            {/* KPI grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KpiStress
                label="Clients → ROUGE"
                value={`${fmt(ind.nb_clients_bascule_rouge)} (${ind.pct_bascule_rouge.toFixed(1)}%)`}
                sub="médiane Monte Carlo"
                accent="#ef4444"
              />
              <KpiStress
                label="EaRS médiane"
                value={`${fmt(Math.round(ind.encours_a_risque_stresse))} TND`}
                sub={`IC 95% [${fmt(Math.round(ind.ic95_EaRS[0]))} — ${fmt(Math.round(ind.ic95_EaRS[1]))}]`}
                accent="#f97316"
              />
              <KpiStress
                label="Provision IFRS 9"
                value={`${fmt(Math.round(ind.provision_recommandee))} TND`}
                sub="EaRS × 15% Stage 3"
                accent="#8b5cf6"
              />
              <KpiStress
                label="Δ Score moyen"
                value={`${ind.delta_score_moyen > 0 ? "+" : ""}${ind.delta_score_moyen.toFixed(1)} pts`}
                sub={`Δ retard +${ind.delta_retard_moyen_jours.toFixed(1)}j`}
                accent={ind.delta_score_moyen > 0 ? "#ef4444" : "#22c55e"}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Distribution avant/après */}
              <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Distribution des alertes — avant / après
                </p>
                <div className="text-xs flex gap-4 mb-3" style={{ color: "var(--muted)" }}>
                  <span className="w-16" />
                  <span className="w-20 text-right">Avant</span>
                  <span className="w-4" />
                  <span className="w-20 text-right">Après</span>
                  <span className="ml-auto">Δ</span>
                </div>
                {["VERT", "ORANGE", "ROUGE"].map((n) => (
                  <DistributionRow
                    key={n}
                    label={n}
                    avant={ind.distribution_avant[n] ?? 0}
                    apres={ind.distribution_apres[n] ?? 0}
                  />
                ))}
              </div>

              {/* Feature deltas */}
              <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Perturbations appliquées
                </p>
                <div className="flex flex-col gap-2">
                  {sc.feature_deltas.map((d, i) => {
                    const pct = d.delta_type === "multiplicatif"
                      ? `×${(1 + d.delta_value) > 1 ? "+" : ""}${(d.delta_value * 100).toFixed(0)}%`
                      : `${d.delta_value > 0 ? "+" : ""}${d.delta_value.toFixed(2)}`;
                    return (
                      <div key={i} className="flex items-center justify-between text-xs py-1.5"
                        style={{ borderBottom: "1px solid var(--card-border)" }}
                      >
                        <span className="font-mono" style={{ color: "#93c5fd" }}>{d.feature}</span>
                        <div className="flex items-center gap-2">
                          <span style={{ color: d.delta_value > 0 ? "#ef4444" : "#22c55e" }}>{pct}</span>
                          <span style={{ color: "var(--muted)" }}>±{(d.std_pct * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Top impacted clients */}
            {ind.clients_les_plus_impactes.length > 0 && (
              <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Clients les plus impactés (top 10)
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr style={{ color: "var(--muted)", borderBottom: "1px solid var(--card-border)" }}>
                        <th className="text-left pb-2">Client</th>
                        <th className="text-left pb-2">Gouvernorat</th>
                        <th className="text-left pb-2">Avant</th>
                        <th className="text-left pb-2">Après</th>
                        <th className="text-right pb-2">Δ Score</th>
                        <th className="text-right pb-2">Encours TND</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ind.clients_les_plus_impactes.map((c, i) => {
                        const delta = c.score_stresse - c.score_baseline;
                        return (
                          <tr key={i} style={{ borderBottom: "1px solid rgba(148,163,184,0.05)" }}>
                            <td className="py-1.5 font-mono pr-3" style={{ color: "#93c5fd" }}>{c.client_id}</td>
                            <td className="py-1.5 pr-3" style={{ color: "var(--muted)" }}>{c.gouvernorat || "—"}</td>
                            <td className="py-1.5 pr-3">
                              <span style={{ color: NIVEAU_COLORS[c.alerte_baseline] ?? "var(--muted)" }}>
                                {c.alerte_baseline}
                              </span>
                            </td>
                            <td className="py-1.5 pr-3">
                              <span style={{ color: NIVEAU_COLORS[c.alerte_stresse] ?? "var(--muted)" }}>
                                {c.alerte_stresse}
                              </span>
                            </td>
                            <td className="py-1.5 text-right" style={{ color: delta > 0 ? "#ef4444" : "#22c55e" }}>
                              {delta > 0 ? "+" : ""}{delta.toFixed(1)}
                            </td>
                            <td className="py-1.5 text-right" style={{ color: "var(--foreground)" }}>
                              {fmt(c.encours_tnd)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Rapport narratif */}
            {result.rapport && (
              <div className="rounded-xl p-5" style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Rapport narratif (Claude)
                </p>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--foreground)" }}>
                  {result.rapport}
                </p>
              </div>
            )}

            {/* Contagion */}
            {result.contagion && (
              <div className="rounded-xl p-5" style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}>
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "#ef4444" }}>
                  Propagation contagion
                </p>
                <div className="flex gap-6 text-sm">
                  <div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Clients contaminés</p>
                    <p className="font-bold" style={{ color: "#ef4444" }}>{fmt(result.contagion.nb_contamines)}</p>
                  </div>
                  <div>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Encours propagé</p>
                    <p className="font-bold" style={{ color: "#f97316" }}>{fmt(Math.round(result.contagion.encours_cumule))} TND</p>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!loading && !result && !error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-24 gap-3"
        >
          <div className="text-4xl">◇</div>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Décrivez un scénario de crise et lancez la simulation
          </p>
        </motion.div>
      )}
    </div>
  );
}
