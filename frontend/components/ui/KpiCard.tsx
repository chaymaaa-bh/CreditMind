"use client";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

interface KpiCardProps {
  label: string;
  value: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  accent?: string;
  sub?: string;
  delay?: number;
}

function useCountUp(target: number, decimals: number, delay: number) {
  const [current, setCurrent] = useState(0);
  const raf = useRef<number>(0);

  useEffect(() => {
    const duration = 1400;
    const start = performance.now() + delay;
    const step = (now: number) => {
      const elapsed = Math.max(0, now - start);
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(parseFloat((eased * target).toFixed(decimals)));
      if (progress < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, decimals, delay]);

  return current;
}

export function KpiCard({ label, value, suffix = "", prefix = "", decimals = 0, accent = "#3b82f6", sub, delay = 0 }: KpiCardProps) {
  const displayed = useCountUp(value, decimals, delay);
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: delay / 1000 }}
      className="flex flex-col gap-1 rounded-xl p-4"
      style={{
        background: "var(--card)",
        border: "1px solid var(--card-border)",
        minWidth: 0,
      }}
    >
      <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--muted)" }}>
        {label}
      </span>
      <span className="text-3xl font-bold tabular-nums" style={{ color: accent }}>
        {prefix}
        {decimals > 0 ? displayed.toFixed(decimals) : Math.round(displayed).toLocaleString("fr-FR")}
        {suffix}
      </span>
      {sub && <span className="text-xs" style={{ color: "var(--muted)" }}>{sub}</span>}
    </motion.div>
  );
}
