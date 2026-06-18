"use client";
import { useEffect, useRef, useState } from "react";

const RISK_COLOR = (v: number, invert = false): string => {
  const pct = invert ? 100 - v : v;
  if (pct >= 75) return "#22c55e";
  if (pct >= 50) return "#eab308";
  if (pct >= 25) return "#f97316";
  return "#ef4444";
};

interface ScoreGaugeProps {
  value: number;       // 0–100
  label: string;
  size?: number;
  invert?: boolean;    // true = high value is bad (prob défaut, anomalie)
  unit?: string;
}

export function ScoreGauge({ value, label, size = 96, invert = false, unit = "" }: ScoreGaugeProps) {
  const [displayed, setDisplayed] = useState(0);
  const raf = useRef<number>(0);

  useEffect(() => {
    const duration = 1000;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplayed(eased * value);
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [value]);

  const r = (size / 2) * 0.72;
  const cx = size / 2;
  const cy = size / 2 + size * 0.08;
  const startAngle = -210;
  const sweepAngle = 240;
  const color = RISK_COLOR(value, invert);

  function polarToCartesian(angle: number) {
    const rad = ((angle - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function arcPath(from: number, to: number) {
    const s = polarToCartesian(from);
    const e = polarToCartesian(to);
    const large = to - from > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const trackPath = arcPath(startAngle, startAngle + sweepAngle);
  const fillPath  = arcPath(startAngle, startAngle + (sweepAngle * displayed) / 100);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size * 0.82} viewBox={`0 0 ${size} ${size * 0.82}`}>
        {/* Track */}
        <path d={trackPath} fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth={size * 0.072} strokeLinecap="round" />
        {/* Fill */}
        <path d={fillPath}  fill="none" stroke={color} strokeWidth={size * 0.072} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 ${size * 0.06}px ${color}80)` }} />
        {/* Value */}
        <text x={cx} y={cy + 2} textAnchor="middle" fontSize={size * 0.22} fontWeight={700} fill={color}>
          {Math.round(displayed)}{unit}
        </text>
      </svg>
      <span className="text-xs text-center leading-tight px-1" style={{ color: "var(--muted)", maxWidth: size }}>
        {label}
      </span>
    </div>
  );
}
