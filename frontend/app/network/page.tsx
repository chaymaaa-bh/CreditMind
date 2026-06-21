"use client";
import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, ArrowRight, Loader2, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { api } from "@/lib/api";
import type { NetworkGraph, NetworkNode, RiskLevel } from "@/types";

const EXEMPLES = ["R_42", "S_1078", "R_1664", "S_5000"];

const ALERTE_COLOR: Record<string, string> = {
  VERT:   "#22c55e",
  JAUNE:  "#eab308",
  ORANGE: "#f97316",
  ROUGE:  "#ef4444",
};

function NodeCard({ node, isCenter = false }: { node: NetworkNode; isCenter?: boolean }) {
  const color = ALERTE_COLOR[node.alerte] ?? "#94a3b8";
  const barW = Math.min(100, node.score_m2);
  return (
    <Link href={`/client/${encodeURIComponent(node.neo4j_id)}`}>
      <motion.div
        whileHover={{ scale: 1.02 }}
        className="rounded-xl p-4 cursor-pointer transition-all"
        style={{
          background: isCenter ? "rgba(139,92,246,0.1)" : "var(--card)",
          border: `1px solid ${isCenter ? "rgba(139,92,246,0.4)" : "var(--card-border)"}`,
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <span
            className="text-xs font-mono font-semibold"
            style={{ color: isCenter ? "#a78bfa" : "#93c5fd" }}
          >
            {node.neo4j_id}
            {isCenter && (
              <span className="ml-1.5 text-xs font-normal px-1.5 py-0.5 rounded"
                style={{ background: "rgba(139,92,246,0.2)", color: "#a78bfa" }}>
                centre
              </span>
            )}
          </span>
          <RiskBadge level={node.alerte as RiskLevel} size="sm" />
        </div>

        {/* Score bar */}
        <div className="mb-2">
          <div className="flex justify-between text-xs mb-0.5" style={{ color: "var(--muted)" }}>
            <span>Score M2</span>
            <span style={{ color }}>{node.score_m2.toFixed(1)}</span>
          </div>
          <div className="h-1 rounded-full" style={{ background: "rgba(148,163,184,0.1)" }}>
            <div className="h-full rounded-full" style={{ width: `${barW}%`, background: color }} />
          </div>
        </div>

        <div className="flex gap-2 text-xs" style={{ color: "var(--muted)" }}>
          {node.gouvernorat && <span className="truncate">{node.gouvernorat}</span>}
          {node.segment && <span className="opacity-60 truncate">· {node.segment}</span>}
        </div>
        <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>
          Prob. défaut : <span style={{ color: node.prob_defaut > 0.5 ? "#ef4444" : "var(--foreground)" }}>
            {(node.prob_defaut * 100).toFixed(1)}%
          </span>
        </div>
      </motion.div>
    </Link>
  );
}

function RiskSummaryBar({ nodes }: { nodes: NetworkNode[] }) {
  const counts = nodes.reduce<Record<string, number>>((acc, n) => {
    acc[n.alerte] = (acc[n.alerte] ?? 0) + 1;
    return acc;
  }, {});
  const total = nodes.length || 1;
  const order = ["VERT", "JAUNE", "ORANGE", "ROUGE"];
  return (
    <div className="flex rounded-lg overflow-hidden h-3">
      {order.map((k) => {
        const n = counts[k] ?? 0;
        if (!n) return null;
        return (
          <div
            key={k}
            title={`${k} : ${n}`}
            style={{ width: `${(n / total) * 100}%`, background: ALERTE_COLOR[k] }}
          />
        );
      })}
    </div>
  );
}

export default function NetworkPage() {
  const [query, setQuery] = useState("");
  const [graph, setGraph] = useState<NetworkGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("ALL");

  const load = useCallback((id: string) => {
    const t = id.trim();
    if (!t) return;
    setLoading(true);
    setError(null);
    setGraph(null);
    setFilter("ALL");
    api.network.graph(t)
      .then(setGraph)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const displayed = graph
    ? (filter === "ALL" ? graph.neighbors : graph.neighbors.filter((n) => n.alerte === filter))
    : [];

  const alertCounts = graph
    ? graph.neighbors.reduce<Record<string, number>>((acc, n) => {
        acc[n.alerte] = (acc[n.alerte] ?? 0) + 1;
        return acc;
      }, {})
    : {};

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>Réseau GNN</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
          Graphe de contagion M2 — voisins par gouvernorat et proximité financière
        </p>
      </motion.div>

      {/* Search */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
        <form
          onSubmit={(e) => { e.preventDefault(); load(query); }}
          className="flex gap-2 max-w-md"
        >
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input
              type="text"
              placeholder="R_42, S_1078…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
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
          </button>
        </form>
        <div className="flex gap-2 mt-2">
          {EXEMPLES.map((id) => (
            <button
              key={id}
              onClick={() => { setQuery(id); load(id); }}
              className="px-2.5 py-1 rounded-lg text-xs font-mono"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "#93c5fd" }}
            >
              {id}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 p-4 rounded-xl"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
          <Loader2 size={18} className="animate-spin" style={{ color: "#8b5cf6" }} />
          <span className="text-sm" style={{ color: "var(--muted)" }}>
            Chargement du graphe pour <span className="font-mono text-blue-400">{query}</span>…
          </span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl p-5" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={16} style={{ color: "#ef4444" }} />
            <span className="font-semibold text-sm" style={{ color: "#ef4444" }}>Client introuvable</span>
          </div>
          <p className="text-xs" style={{ color: "#fca5a5" }}>{error}</p>
        </div>
      )}

      {/* Graph results */}
      <AnimatePresence>
        {graph && !loading && (
          <motion.div
            key={graph.center.neo4j_id}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-5"
          >
            {/* Stats bar */}
            <div className="rounded-xl p-4 flex flex-wrap items-center gap-4"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}>
              <div>
                <p className="text-xs" style={{ color: "var(--muted)" }}>Gouvernorat</p>
                <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                  {graph.center.gouvernorat ?? "—"}
                </p>
              </div>
              <div>
                <p className="text-xs" style={{ color: "var(--muted)" }}>Total dans le gouvernorat</p>
                <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                  {graph.total_gouvernorat.toLocaleString("fr-FR")} clients
                </p>
              </div>
              <div>
                <p className="text-xs" style={{ color: "var(--muted)" }}>Voisins affichés</p>
                <p className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
                  {graph.neighbors.length}
                </p>
              </div>
              <div className="flex-1 min-w-32">
                <p className="text-xs mb-1" style={{ color: "var(--muted)" }}>Distribution risque voisins</p>
                <RiskSummaryBar nodes={graph.neighbors} />
              </div>
              <div className="text-xs px-2 py-1 rounded-full" style={{ background: "rgba(148,163,184,0.08)", color: "var(--muted)" }}>
                {graph.lien_type.replace(/_/g, " ")}
              </div>
            </div>

            {/* Filter tabs */}
            <div className="flex gap-2">
              {["ALL", "ROUGE", "ORANGE", "JAUNE", "VERT"].map((a) => {
                const count = a === "ALL" ? graph.neighbors.length : (alertCounts[a] ?? 0);
                if (a !== "ALL" && !count) return null;
                return (
                  <button
                    key={a}
                    onClick={() => setFilter(a)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: filter === a
                        ? (a === "ALL" ? "rgba(139,92,246,0.2)" : (ALERTE_COLOR[a] + "22"))
                        : "var(--card)",
                      border: `1px solid ${filter === a
                        ? (a === "ALL" ? "rgba(139,92,246,0.4)" : (ALERTE_COLOR[a] + "55"))
                        : "var(--card-border)"}`,
                      color: filter === a
                        ? (a === "ALL" ? "#a78bfa" : ALERTE_COLOR[a])
                        : "var(--muted)",
                    }}
                  >
                    {a === "ALL" ? "Tous" : a} ({count})
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
              {/* Center node */}
              <div className="lg:col-span-1">
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Nœud central
                </p>
                <NodeCard node={graph.center} isCenter />
              </div>

              {/* Neighbors grid */}
              <div className="lg:col-span-3">
                <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "var(--muted)" }}>
                  Voisins ({displayed.length})
                </p>
                {displayed.length === 0 ? (
                  <p className="text-sm" style={{ color: "var(--muted)" }}>Aucun voisin pour ce filtre.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {displayed.map((n) => (
                      <NodeCard key={n.client_id} node={n} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state */}
      {!loading && !graph && !error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex flex-col items-center justify-center py-24 gap-3"
        >
          <div className="text-4xl">◈</div>
          <p className="text-sm" style={{ color: "var(--muted)" }}>
            Entrez un identifiant client pour explorer son réseau de contagion
          </p>
        </motion.div>
      )}
    </div>
  );
}
