"use client";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import type { RiskDistribution } from "@/types";

const COLORS: Record<string, string> = {
  VERT:   "#22c55e",
  JAUNE:  "#eab308",
  ORANGE: "#f97316",
  ROUGE:  "#ef4444",
};

interface Props {
  distribution: RiskDistribution;
  total: number;
}

export function RiskDonut({ distribution, total }: Props) {
  const data = (["VERT", "JAUNE", "ORANGE", "ROUGE"] as const).map((key) => ({
    name: key,
    value: distribution[key],
    pct: ((distribution[key] / total) * 100).toFixed(1),
  }));

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
        Répartition par niveau de risque
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={88}
            paddingAngle={3}
            dataKey="value"
            animationBegin={200}
            animationDuration={900}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={COLORS[entry.name]} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--card-border)",
              borderRadius: 8,
              color: "var(--foreground)",
              fontSize: 12,
            }}
            formatter={(value, name) => [
              `${Number(value).toLocaleString("fr-FR")} (${((Number(value) / total) * 100).toFixed(1)}%)`,
              String(name),
            ]}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value) => (
              <span style={{ color: "var(--muted)", fontSize: 12 }}>{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Center label */}
      <div className="text-center -mt-2">
        <span className="text-xs" style={{ color: "var(--muted)" }}>
          {total.toLocaleString("fr-FR")} clients
        </span>
      </div>
    </div>
  );
}
