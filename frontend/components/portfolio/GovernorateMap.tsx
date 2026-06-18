"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import type { GovernorateStats } from "@/types";

// Tunisia SVG viewport: 300 × 520
// Geographic bounds: lon [7.5, 11.8], lat [30.2, 37.8]
const LON_MIN = 7.5, LON_MAX = 11.8;
const LAT_MIN = 30.2, LAT_MAX = 37.8;
const W = 300, H = 520;

function project(lon: number, lat: number): [number, number] {
  const x = ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * W;
  const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * H;
  return [x, y];
}

// Approximate governorate centers
const GOV_COORDS: Record<string, [number, number]> = {
  BIZERTE:      [9.87,  37.27],
  BÉJA:         [9.18,  36.73],
  JENDOUBA:     [8.78,  36.50],
  "LE KEF":     [8.70,  36.18],
  SILIANA:      [9.37,  36.08],
  MANNOUBA:     [9.97,  36.84],
  ARIANA:       [10.19, 36.86],
  TUNIS:        [10.18, 36.80],
  "BEN AROUS":  [10.22, 36.75],
  ZAGHOUAN:     [10.14, 36.40],
  NABEUL:       [10.73, 36.47],
  SOUSSE:       [10.64, 35.83],
  MONASTIR:     [10.83, 35.78],
  MAHDIA:       [11.06, 35.50],
  KAIROUAN:     [10.10, 35.67],
  KASSERINE:    [8.83,  35.17],
  "SIDI BOUZID":[9.48,  35.03],
  SFAX:         [10.76, 34.74],
  GAFSA:        [8.78,  34.42],
  TOZEUR:       [8.13,  33.92],
  KÉBILLI:      [8.97,  33.70],
  GABÈS:        [9.90,  33.88],
  MÉDENINE:     [10.50, 33.35],
  TATAOUINE:    [10.45, 32.93],
};

// Simplified Tunisia outline polygon
const OUTLINE = [
  [42, 18], [90, 12], [145, 8], [168, 20],
  [182, 30], [237, 58], [250, 84], [252, 118],
  [248, 152], [246, 175], [238, 198], [242, 238],
  [244, 262], [234, 282], [218, 296], [210, 320],
  [192, 375], [175, 450], [162, 520],
  [0, 520], [8, 388], [16, 315], [24, 272],
  [38, 232], [44, 202], [58, 178], [64, 142],
  [70, 112], [60, 88], [42, 72], [38, 48],
].map(([x, y]) => `${x},${y}`).join(" ");

function riskColor(pct: number): string {
  if (pct >= 40) return "#ef4444";
  if (pct >= 25) return "#f97316";
  if (pct >= 12) return "#eab308";
  return "#22c55e";
}

function riskGlow(pct: number): string {
  if (pct >= 40) return "rgba(239,68,68,0.4)";
  if (pct >= 25) return "rgba(249,115,22,0.4)";
  if (pct >= 12) return "rgba(234,179,8,0.4)";
  return "rgba(34,197,94,0.4)";
}

interface Props {
  data: GovernorateStats[];
  onSelect?: (gov: string) => void;
  selectedGov?: string;
}

export function GovernorateMap({ data, onSelect, selectedGov }: Props) {
  const [tooltip, setTooltip] = useState<{
    gov: string; x: number; y: number; stats: GovernorateStats;
  } | null>(null);

  const statsMap = Object.fromEntries(data.map((d) => [d.gouvernorat, d]));

  return (
    <div className="flex flex-col gap-2 h-full">
      <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
        Carte de risque — Tunisie
      </h3>
      <div className="relative flex-1 flex items-center justify-center">
        <svg
          viewBox="0 0 300 520"
          style={{ maxHeight: 420, width: "100%", overflow: "visible" }}
          aria-label="Carte de risque des gouvernorats tunisiens"
        >
          {/* Tunisia outline */}
          <polygon
            points={OUTLINE}
            fill="rgba(15,23,42,0.6)"
            stroke="rgba(148,163,184,0.2)"
            strokeWidth={1.5}
          />

          {/* Governorate bubbles */}
          {Object.entries(GOV_COORDS).map(([name, [lon, lat]], i) => {
            const [cx, cy] = project(lon, lat);
            const stats = statsMap[name];
            const pct = stats?.pct_rouge ?? 0;
            const isSelected = selectedGov === name;
            const r = stats ? Math.max(7, Math.min(14, 7 + (stats.total / 21637) * 120)) : 7;

            return (
              <motion.g
                key={name}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: i * 0.03, duration: 0.4, type: "spring", stiffness: 200 }}
                style={{ transformOrigin: `${cx}px ${cy}px`, cursor: stats ? "pointer" : "default" }}
                onClick={() => stats && onSelect?.(name)}
                onMouseEnter={() => stats && setTooltip({ gov: name, x: cx, y: cy, stats })}
                onMouseLeave={() => setTooltip(null)}
              >
                {/* Glow ring for high risk */}
                {pct >= 20 && (
                  <circle cx={cx} cy={cy} r={r + 5} fill="none" stroke={riskGlow(pct)} strokeWidth={1.5} opacity={0.6} />
                )}
                {/* Selected ring */}
                {isSelected && (
                  <circle cx={cx} cy={cy} r={r + 7} fill="none" stroke="white" strokeWidth={2} opacity={0.8} />
                )}
                {/* Main bubble */}
                <circle
                  cx={cx}
                  cy={cy}
                  r={r}
                  fill={stats ? riskColor(pct) : "#334155"}
                  fillOpacity={0.85}
                  stroke="rgba(255,255,255,0.2)"
                  strokeWidth={1}
                />
                {/* Label for larger cities */}
                {r >= 10 && (
                  <text
                    x={cx}
                    y={cy + r + 9}
                    textAnchor="middle"
                    fontSize={8}
                    fill="rgba(148,163,184,0.8)"
                  >
                    {name.length > 8 ? name.slice(0, 8) : name}
                  </text>
                )}
              </motion.g>
            );
          })}

          {/* Tooltip */}
          {tooltip && (
            <g>
              <rect
                x={Math.min(tooltip.x + 8, W - 115)}
                y={Math.max(tooltip.y - 52, 4)}
                width={110}
                height={50}
                rx={6}
                fill="var(--card)"
                stroke="var(--card-border)"
                strokeWidth={1}
                filter="drop-shadow(0 4px 6px rgba(0,0,0,0.5))"
              />
              <text x={Math.min(tooltip.x + 14, W - 109)} y={Math.max(tooltip.y - 35, 21)} fontSize={9} fontWeight={600} fill="var(--foreground)">
                {tooltip.gov}
              </text>
              <text x={Math.min(tooltip.x + 14, W - 109)} y={Math.max(tooltip.y - 22, 34)} fontSize={8} fill="#94a3b8">
                {tooltip.stats.total.toLocaleString("fr-FR")} clients
              </text>
              <text x={Math.min(tooltip.x + 14, W - 109)} y={Math.max(tooltip.y - 10, 46)} fontSize={8} fill={riskColor(tooltip.stats.pct_rouge)} fontWeight={600}>
                {tooltip.stats.pct_rouge.toFixed(1)}% ROUGE
              </text>
            </g>
          )}
        </svg>

        {/* Legend */}
        <div className="absolute bottom-0 right-0 flex flex-col gap-1 p-2 rounded-lg" style={{ background: "rgba(15,23,42,0.8)", border: "1px solid var(--card-border)" }}>
          {[
            { label: "≥ 40%", color: "#ef4444" },
            { label: "25–40%", color: "#f97316" },
            { label: "12–25%", color: "#eab308" },
            { label: "< 12%", color: "#22c55e" },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5">
              <div className="rounded-full" style={{ width: 8, height: 8, background: color }} />
              <span style={{ fontSize: 10, color: "#94a3b8" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
