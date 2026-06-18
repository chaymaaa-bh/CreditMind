"use client";
import type { RiskLevel } from "@/types";

const CONFIG: Record<RiskLevel, { bg: string; text: string; dot: string }> = {
  VERT:   { bg: "rgba(34,197,94,0.12)",  text: "#22c55e", dot: "#22c55e" },
  JAUNE:  { bg: "rgba(234,179,8,0.12)",  text: "#eab308", dot: "#eab308" },
  ORANGE: { bg: "rgba(249,115,22,0.12)", text: "#f97316", dot: "#f97316" },
  ROUGE:  { bg: "rgba(239,68,68,0.12)",  text: "#ef4444", dot: "#ef4444" },
};

export function RiskBadge({ level, size = "sm" }: { level: RiskLevel; size?: "xs" | "sm" | "md" }) {
  const cfg = CONFIG[level] ?? CONFIG.ROUGE;
  const pad = size === "xs" ? "px-1.5 py-0.5 text-[10px]" : size === "md" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${pad}`}
      style={{ background: cfg.bg, color: cfg.text }}
    >
      <span
        className="rounded-full"
        style={{ width: 6, height: 6, background: cfg.dot, flexShrink: 0 }}
      />
      {level}
    </span>
  );
}
