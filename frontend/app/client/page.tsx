"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Search, ArrowRight } from "lucide-react";

const EXAMPLES = ["R_0", "R_1078", "S_10395", "R_1664", "S_5000"];

export default function ClientSearchPage() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const navigate = (id: string) => {
    const trimmed = id.trim();
    if (trimmed) router.push(`/client/${encodeURIComponent(trimmed)}`);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-6 gap-8">
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-3xl font-bold mb-2" style={{ color: "var(--foreground)" }}>
          Détail Client
        </h1>
        <p className="text-sm" style={{ color: "var(--muted)" }}>
          Entrez un identifiant client (ex: R_42, S_1637) pour accéder au profil complet
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1 }}
        className="w-full max-w-lg"
      >
        <form
          onSubmit={(e) => { e.preventDefault(); navigate(query); }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--muted)" }} />
            <input
              type="text"
              placeholder="R_42, S_1637, 42…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
              className="w-full rounded-xl pl-10 pr-4 py-3 text-sm outline-none transition-all"
              style={{
                background: "var(--card)",
                border: "1px solid var(--card-border)",
                color: "var(--foreground)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(139,92,246,0.5)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--card-border)")}
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-2 px-4 py-3 rounded-xl font-medium text-sm transition-all"
            style={{ background: "#6d28d9", color: "white" }}
          >
            <ArrowRight size={16} />
          </button>
        </form>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex flex-col items-center gap-3"
      >
        <p className="text-xs" style={{ color: "var(--muted)" }}>Exemples</p>
        <div className="flex flex-wrap gap-2 justify-center">
          {EXAMPLES.map((id) => (
            <button
              key={id}
              onClick={() => navigate(id)}
              className="px-3 py-1.5 rounded-lg text-xs font-mono transition-all"
              style={{
                background: "var(--card)",
                border: "1px solid var(--card-border)",
                color: "#93c5fd",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "rgba(139,92,246,0.4)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--card-border)")}
            >
              {id}
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
