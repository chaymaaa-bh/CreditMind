import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CreditMind — Risk Intelligence Platform",
  description: "Plateforme de scoring crédit et analyse de risque IA",
};

const navLinks = [
  { href: "/portfolio", label: "Portefeuille" },
  { href: "/client", label: "Clients" },
  { href: "/forecast", label: "Prévisions M3" },
  { href: "/anomalies", label: "Anomalies M4" },
  { href: "/agents", label: "Agents M7" },
  { href: "/stress", label: "Stress M9" },
  { href: "/network", label: "Réseau GNN" },
  { href: "/graphrag", label: "GraphRAG M6" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${geistSans.variable} h-full`}>
      <body className="min-h-full flex flex-col" style={{ background: "var(--background)", color: "var(--foreground)" }}>
        {/* Top navigation */}
        <nav
          style={{
            background: "var(--card)",
            borderBottom: "1px solid var(--card-border)",
          }}
          className="sticky top-0 z-50 flex items-center px-6 h-14 gap-8"
        >
          {/* Logo */}
          <Link href="/portfolio" className="flex items-center gap-2 shrink-0">
            <span
              className="text-lg font-bold tracking-tight"
              style={{
                background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              CreditMind
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded font-medium"
              style={{ background: "rgba(59,130,246,0.15)", color: "#3b82f6" }}
            >
              AI
            </span>
          </Link>

          {/* Separator */}
          <div className="h-5 w-px" style={{ background: "var(--card-border)" }} />

          {/* Nav links */}
          <div className="flex items-center gap-1 flex-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="px-3 py-1.5 rounded-md text-sm transition-colors"
                style={{ color: "var(--muted)" }}
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Right badge */}
          <span
            className="text-xs font-medium px-2 py-1 rounded-full"
            style={{
              background: "rgba(34,197,94,0.1)",
              color: "var(--risk-vert)",
              border: "1px solid rgba(34,197,94,0.2)",
            }}
          >
            ● API connectée
          </span>
        </nav>

        {/* Page content */}
        <main className="flex-1">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </body>
    </html>
  );
}
