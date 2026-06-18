"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { GovernorateStats } from "@/types";

function riskColor(pct: number): string {
  if (pct >= 50) return "#ef4444";
  if (pct >= 30) return "#f97316";
  if (pct >= 15) return "#eab308";
  return "#22c55e";
}

interface Props {
  data: GovernorateStats[];
  onSelect?: (gov: string) => void;
}

export function TopRiskyGovBar({ data, onSelect }: Props) {
  const top = data.slice(0, 8);
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
        Top gouvernorats — % ROUGE
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={top} layout="vertical" margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: "#64748b", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="gouvernorat"
            width={90}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--card-border)",
              borderRadius: 8,
              color: "var(--foreground)",
              fontSize: 12,
            }}
            formatter={(value, _, props) => [
              `${Number(value).toFixed(1)}% ROUGE (${(props as {payload: GovernorateStats}).payload.nb_rouge} / ${(props as {payload: GovernorateStats}).payload.total})`,
              "Taux de risque",
            ]}
          />
          <Bar
            dataKey="pct_rouge"
            radius={[0, 4, 4, 0]}
            cursor="pointer"
            onClick={(d) => onSelect?.((d as unknown as GovernorateStats).gouvernorat)}
            animationDuration={900}
          >
            {top.map((entry) => (
              <Cell key={entry.gouvernorat} fill={riskColor(entry.pct_rouge)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
