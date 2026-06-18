"use client";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { useState, useEffect, useCallback } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown, Search } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { api } from "@/lib/api";
import type { ClientListItem, RiskLevel } from "@/types";

const col = createColumnHelper<ClientListItem>();

const COLUMNS = [
  col.accessor("neo4j_id", {
    header: "ID Client",
    cell: (info) => (
      <span className="font-mono text-xs" style={{ color: "#93c5fd" }}>
        {info.getValue()}
      </span>
    ),
  }),
  col.accessor("alerte", {
    header: "Alerte",
    cell: (info) => <RiskBadge level={info.getValue() as RiskLevel} size="xs" />,
  }),
  col.accessor("prob_defaut", {
    header: "Prob. Défaut",
    cell: (info) => {
      const v = info.getValue();
      const color = v > 0.7 ? "#ef4444" : v > 0.4 ? "#f97316" : v > 0.1 ? "#eab308" : "#22c55e";
      return <span style={{ color, fontWeight: 600 }}>{(v * 100).toFixed(1)}%</span>;
    },
  }),
  col.accessor("score_solvabilite", {
    header: "Score M5",
    cell: (info) => {
      const v = info.getValue();
      return (
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 rounded-full" style={{ background: "rgba(148,163,184,0.15)" }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${v}%`,
                background: v > 80 ? "#22c55e" : v > 50 ? "#eab308" : "#ef4444",
              }}
            />
          </div>
          <span className="text-xs tabular-nums" style={{ color: "var(--foreground)" }}>{v}</span>
        </div>
      );
    },
  }),
  col.accessor("classe_risque", {
    header: "Classe",
    cell: (info) => (
      <span className="text-xs" style={{ color: "var(--muted)" }}>{info.getValue()}</span>
    ),
  }),
  col.accessor("gouvernorat", {
    header: "Gouvernorat",
    cell: (info) => (
      <span className="text-xs" style={{ color: "var(--muted)" }}>{info.getValue() ?? "—"}</span>
    ),
  }),
  col.accessor("gnn_risk_score", {
    header: "GNN",
    cell: (info) => (
      <span className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>
        {(info.getValue() * 100).toFixed(0)}
      </span>
    ),
  }),
];

const ALERT_FILTERS: Array<{ label: string; value: string; color: string }> = [
  { label: "Tous", value: "", color: "#94a3b8" },
  { label: "ROUGE",  value: "ROUGE",  color: "#ef4444" },
  { label: "ORANGE", value: "ORANGE", color: "#f97316" },
  { label: "JAUNE",  value: "JAUNE",  color: "#eab308" },
  { label: "VERT",   value: "VERT",   color: "#22c55e" },
];

interface Props {
  filterGov?: string;
}

export function ClientTable({ filterGov }: Props) {
  const [data, setData]       = useState<ClientListItem[]>([]);
  const [total, setTotal]     = useState(0);
  const [pages, setPages]     = useState(1);
  const [page, setPage]       = useState(1);
  const [alertFilter, setAlertFilter] = useState("");
  const [search, setSearch]   = useState("");
  const [sorting, setSorting] = useState<SortingState>([{ id: "prob_defaut", desc: true }]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const sort = sorting[0];
      const resp = await api.portfolio.clients({
        page,
        limit: 50,
        alert: alertFilter || undefined,
        q: search || undefined,
        gouvernorat: filterGov || undefined,
        sort_by: sort?.id ?? "prob_defaut",
        sort_dir: sort?.desc ? "desc" : "asc",
      });
      setData(resp.items);
      setTotal(resp.total);
      setPages(resp.pages);
    } catch {
      // keep previous data on error
    } finally {
      setLoading(false);
    }
  }, [page, alertFilter, search, sorting, filterGov]);

  useEffect(() => { setPage(1); }, [alertFilter, search, filterGov]);
  useEffect(() => { fetchData(); }, [fetchData]);

  const table = useReactTable({
    data,
    columns: COLUMNS,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    onSortingChange: setSorting,
    state: { sorting },
  });

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-40">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
          <input
            type="text"
            placeholder="Rechercher ID client..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg pl-8 pr-3 py-2 text-sm outline-none"
            style={{
              background: "var(--card)",
              border: "1px solid var(--card-border)",
              color: "var(--foreground)",
            }}
          />
        </div>
        {/* Alert filter pills */}
        <div className="flex gap-1">
          {ALERT_FILTERS.map(({ label, value, color }) => (
            <button
              key={value}
              onClick={() => setAlertFilter(value)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{
                background: alertFilter === value ? `${color}22` : "var(--card)",
                border: `1px solid ${alertFilter === value ? color : "var(--card-border)"}`,
                color: alertFilter === value ? color : "var(--muted)",
              }}
            >
              {label}
            </button>
          ))}
        </div>
        {/* Count */}
        <span className="text-xs ml-auto" style={{ color: "var(--muted)" }}>
          {total.toLocaleString("fr-FR")} résultats
        </span>
      </div>

      {/* Table */}
      <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--card-border)" }}>
        <table className="w-full text-sm border-collapse">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} style={{ background: "rgba(15,23,42,0.8)", borderBottom: "1px solid var(--card-border)" }}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider cursor-pointer select-none"
                    style={{ color: "var(--muted)" }}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc" ? (
                        <ChevronUp size={12} />
                      ) : header.column.getIsSorted() === "desc" ? (
                        <ChevronDown size={12} />
                      ) : (
                        <ChevronsUpDown size={12} className="opacity-30" />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            <AnimatePresence mode="wait">
              {loading ? (
                <tr>
                  <td colSpan={COLUMNS.length} className="text-center py-12" style={{ color: "var(--muted)" }}>
                    <div className="inline-block w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row, i) => (
                  <motion.tr
                    key={row.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.01 }}
                    className="transition-colors cursor-pointer"
                    style={{ borderBottom: "1px solid rgba(148,163,184,0.06)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(148,163,184,0.04)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2.5">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </motion.tr>
                ))
              )}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--muted)" }}>
        <span>Page {page} sur {pages}</span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 rounded-lg disabled:opacity-30 transition-colors"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            Préc.
          </button>
          <button
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="px-3 py-1 rounded-lg disabled:opacity-30 transition-colors"
            style={{ background: "var(--card)", border: "1px solid var(--card-border)" }}
          >
            Suiv.
          </button>
        </div>
      </div>
    </div>
  );
}
