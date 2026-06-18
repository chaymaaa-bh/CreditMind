"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { KpiCard } from "@/components/ui/KpiCard";
import { RiskDonut } from "@/components/portfolio/RiskDonut";
import { GovernorateMap } from "@/components/portfolio/GovernorateMap";
import { TopRiskyGovBar } from "@/components/portfolio/TopRiskyGovBar";
import { ClientTable } from "@/components/portfolio/ClientTable";
import { api } from "@/lib/api";
import type { GovernorateStats, PortfolioSummary } from "@/types";

export default function PortfolioPage() {
  const [summary, setSummary]     = useState<PortfolioSummary | null>(null);
  const [govData, setGovData]     = useState<GovernorateStats[]>([]);
  const [selectedGov, setSelectedGov] = useState<string | undefined>();
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.portfolio.summary(), api.portfolio.byGovernorate()])
      .then(([s, g]) => {
        setSummary(s);
        setGovData(g);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const handleGovSelect = (gov: string) => {
    setSelectedGov((prev) => (prev === gov ? undefined : gov));
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div
          className="rounded-xl p-6 text-center"
          style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444" }}
        >
          <p className="font-semibold">Erreur de connexion API</p>
          <p className="text-sm mt-1 opacity-75">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-2xl mx-auto">

      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>
            Vue Portefeuille
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--muted)" }}>
            Analyse globale — {(21637).toLocaleString("fr-FR")} clients entreprises
          </p>
        </div>
        {selectedGov && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setSelectedGov(undefined)}
            className="px-3 py-1.5 rounded-lg text-sm flex items-center gap-2"
            style={{
              background: "rgba(59,130,246,0.1)",
              border: "1px solid rgba(59,130,246,0.3)",
              color: "#3b82f6",
            }}
          >
            Filtre : {selectedGov} ✕
          </motion.button>
        )}
      </motion.div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {summary ? (
          <>
            <KpiCard
              label="Total clients"
              value={summary.total}
              accent="#3b82f6"
              sub="portefeuille complet"
              delay={0}
            />
            <KpiCard
              label="Alertes ROUGE"
              value={summary.encours_rouge}
              accent="#ef4444"
              sub={`${summary.pct_rouge}% du portefeuille`}
              delay={80}
            />
            <KpiCard
              label="Score moyen M5"
              value={summary.score_moyen}
              suffix=" / 100"
              decimals={1}
              accent="#8b5cf6"
              sub="solvabilité ensemble"
              delay={160}
            />
            <KpiCard
              label="Taux de défaut"
              value={summary.pct_defaut}
              suffix="%"
              decimals={1}
              accent="#f97316"
              sub="label réel M5"
              delay={240}
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl h-24 animate-pulse"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
            />
          ))
        )}
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* Map — 3 cols */}
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
          className="lg:col-span-3 rounded-xl p-5"
          style={{ background: "var(--card)", border: "1px solid var(--card-border)", minHeight: 460 }}
        >
          {govData.length > 0 ? (
            <GovernorateMap
              data={govData}
              onSelect={handleGovSelect}
              selectedGov={selectedGov}
            />
          ) : (
            <div className="h-full animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
          )}
        </motion.div>

        {/* Right panel — 2 cols */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          {/* Donut */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.25 }}
            className="rounded-xl p-5"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            {summary ? (
              <RiskDonut distribution={summary.distribution} total={summary.total} />
            ) : (
              <div className="h-48 animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
            )}
          </motion.div>

          {/* Bar chart */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="rounded-xl p-5"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            {govData.length > 0 ? (
              <TopRiskyGovBar data={govData} onSelect={handleGovSelect} />
            ) : (
              <div className="h-48 animate-pulse rounded-lg" style={{ background: "rgba(148,163,184,0.05)" }} />
            )}
          </motion.div>
        </div>
      </div>

      {/* Client table */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="rounded-xl p-5"
        style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
            Liste des clients
            {selectedGov && (
              <span className="ml-2 text-xs font-normal" style={{ color: "#3b82f6" }}>
                — {selectedGov}
              </span>
            )}
          </h2>
        </div>
        <ClientTable filterGov={selectedGov} />
      </motion.div>
    </div>
  );
}
