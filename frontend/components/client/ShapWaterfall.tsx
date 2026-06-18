"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  ReferenceLine, ResponsiveContainer,
} from "recharts";
import type { ShapResult } from "@/types";

interface Props { shap: ShapResult }

export function ShapWaterfall({ shap }: Props) {
  const features = [...shap.top_features].sort(
    (a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value)
  );

  const data = features.map((f) => ({
    label: f.label.length > 32 ? f.label.slice(0, 30) + "…" : f.label,
    value: f.shap_value,
    direction: f.direction,
    feature_value: f.feature_value,
    fullLabel: f.label,
  }));

  const absMax = Math.max(...data.map((d) => Math.abs(d.value)), 0.1);
  const domain = [-absMax * 1.15, absMax * 1.15];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          Explication SHAP — Top {data.length} facteurs
        </h3>
        <div className="flex gap-3 text-xs" style={{ color: "var(--muted)" }}>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "#ef4444" }} /> aggrave
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: "#22c55e" }} /> améliore
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={data.length * 34 + 40}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 8, right: 40, top: 4, bottom: 4 }}
          barSize={14}
        >
          <XAxis
            type="number"
            domain={domain}
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => v.toFixed(2)}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={175}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <ReferenceLine x={0} stroke="rgba(148,163,184,0.3)" strokeWidth={1} />
          <Tooltip
            cursor={{ fill: "rgba(148,163,184,0.05)" }}
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--card-border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--foreground)",
            }}
            formatter={(value, _, props) => {
              const v = Number(value);
              const p = (props as { payload?: { fullLabel?: string; feature_value?: number; direction?: string } }).payload ?? {};
              return [
                <span key="v" style={{ color: v > 0 ? "#ef4444" : "#22c55e" }}>
                  {v > 0 ? "+" : ""}{v.toFixed(4)} ({p.direction ?? ""})
                </span>,
                <span key="l" style={{ color: "var(--muted)", fontSize: 11 }}>
                  {p.fullLabel ?? ""} = {Number(p.feature_value ?? 0).toFixed(3)}
                </span>,
              ];
            }}
          />
          <Bar dataKey="value" radius={[0, 3, 3, 0]} animationDuration={800}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.direction === "aggrave" ? "#ef4444" : "#22c55e"}
                fillOpacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <p className="text-xs" style={{ color: "var(--muted)" }}>
        Valeur de base : <span className="font-mono">{shap.base_value.toFixed(4)}</span>
        {" "}— Les barres rouges augmentent le risque de défaut, vertes le réduisent.
      </p>
    </div>
  );
}
