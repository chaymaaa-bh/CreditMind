"use client";
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const CARD = { background: "var(--card)", border: "1px solid var(--card-border)" };
const MUTED = { color: "var(--muted)" };
const FG = { color: "var(--foreground)" };

type Message = { role: "user" | "assistant"; text: string; loading?: boolean };

const EXAMPLE_QUERIES = [
  "Quels clients ROUGE ont un retard supérieur à 90 jours ?",
  "Distribution des alertes par gouvernorat",
  "Segments avec le plus fort taux de risque",
  "Concepts de risque présents dans le portefeuille",
  "Règles de décision actives",
];

const EXAMPLE_CONCEPTS = ["retard de paiement", "encaissement", "contagion", "taux de défaut"];

async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json() as Promise<T>;
}

export default function GraphRAGPage() {
  const [status, setStatus] = useState<{ available: boolean; message: string } | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "client" | "knowledge">("chat");
  const [clientId, setClientId] = useState("");
  const [clientReport, setClientReport] = useState<string | null>(null);
  const [clientLoading, setClientLoading] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [concepts, setConcepts] = useState<Record<string, string>[]>([]);
  const [rules, setRules] = useState<Record<string, string>[]>([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [conceptInput, setConceptInput] = useState("");
  const [conceptResult, setConceptResult] = useState<string | null>(null);
  const [conceptLoading, setConceptLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    get<{ available: boolean; message: string }>("/api/graphrag/status").then(setStatus);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendQuery(question: string) {
    if (!question.trim() || sending) return;
    setInput("");
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", text: question },
      { role: "assistant", text: "", loading: true },
    ]);
    try {
      const res = await post<{ answer: string }>("/api/graphrag/query", { question });
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text: res.answer },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text: `Erreur : ${String(e)}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function loadClientReport() {
    if (!clientId.trim()) return;
    setClientLoading(true);
    setClientError(null);
    setClientReport(null);
    try {
      const res = await get<{ report: string }>(`/api/graphrag/client/${encodeURIComponent(clientId.trim())}`);
      setClientReport(res.report);
    } catch (e) {
      setClientError(String(e));
    } finally {
      setClientLoading(false);
    }
  }

  async function loadKnowledgeBase() {
    setKbLoading(true);
    try {
      const [c, r] = await Promise.all([
        get<Record<string, string>[]>("/api/graphrag/concepts"),
        get<Record<string, string>[]>("/api/graphrag/rules"),
      ]);
      setConcepts(c);
      setRules(r);
    } catch (e) {
      console.error(e);
    } finally {
      setKbLoading(false);
    }
  }

  async function explainConcept(concept: string) {
    if (!concept.trim()) return;
    setConceptLoading(true);
    setConceptResult(null);
    try {
      const res = await post<{ explanation: string }>("/api/graphrag/explain", { concept });
      setConceptResult(res.explanation);
    } catch (e) {
      setConceptResult(`Erreur : ${String(e)}`);
    } finally {
      setConceptLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "knowledge" && concepts.length === 0) loadKnowledgeBase();
  }, [activeTab]);

  const isAvailable = status?.available ?? null;

  return (
    <div className="flex flex-col gap-6 p-6 max-w-screen-xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={FG}>GraphRAG M6</h1>
          <p className="text-sm mt-0.5" style={MUTED}>
            Knowledge Base Neo4j · LlamaIndex · Claude Sonnet 4.6
          </p>
        </div>
        {status && (
          <span
            className="text-xs font-medium px-3 py-1.5 rounded-full"
            style={{
              background: isAvailable ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
              color: isAvailable ? "#22c55e" : "#ef4444",
              border: `1px solid ${isAvailable ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
            }}
          >
            {isAvailable ? "● Neo4j connecté" : "● Neo4j indisponible"}
          </span>
        )}
      </motion.div>

      {/* Status warning if unavailable */}
      {status && !isAvailable && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-xl p-4"
          style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <p className="text-sm font-medium" style={{ color: "#ef4444" }}>
            Neo4j inaccessible — configurer NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
          </p>
          <p className="text-xs mt-1" style={MUTED}>{status.message}</p>
        </motion.div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl w-fit" style={{ background: "rgba(148,163,184,0.07)", border: "1px solid var(--card-border)" }}>
        {(["chat", "client", "knowledge"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: activeTab === tab ? "var(--card)" : "transparent",
              color: activeTab === tab ? "var(--foreground)" : "var(--muted)",
              boxShadow: activeTab === tab ? "0 1px 3px rgba(0,0,0,0.2)" : "none",
            }}
          >
            {tab === "chat" ? "Requêtes NL" : tab === "client" ? "Rapport Client" : "Base de Connaissances"}
          </button>
        ))}
      </div>

      {/* Tab: Chat */}
      {activeTab === "chat" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-4">
          {/* Example queries */}
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => sendQuery(q)}
                disabled={sending || !isAvailable}
                className="px-3 py-1.5 rounded-lg text-xs transition-all disabled:opacity-40"
                style={{ background: "rgba(59,130,246,0.08)", border: "1px solid rgba(59,130,246,0.2)", color: "#3b82f6" }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Messages */}
          <div
            className="rounded-xl p-4 flex flex-col gap-3 overflow-y-auto"
            style={{ ...CARD, minHeight: 340, maxHeight: 520 }}
          >
            {messages.length === 0 && (
              <div className="flex-1 flex items-center justify-center">
                <p className="text-sm text-center" style={MUTED}>
                  {isAvailable
                    ? "Posez une question en langage naturel sur le portefeuille crédit…"
                    : "Neo4j requis pour les requêtes GraphRAG."}
                </p>
              </div>
            )}
            <AnimatePresence>
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className="rounded-xl px-4 py-3 text-sm max-w-[85%] whitespace-pre-wrap"
                    style={{
                      background: msg.role === "user" ? "rgba(59,130,246,0.15)" : "rgba(148,163,184,0.07)",
                      border: `1px solid ${msg.role === "user" ? "rgba(59,130,246,0.25)" : "var(--card-border)"}`,
                      color: "var(--foreground)",
                    }}
                  >
                    {msg.loading ? (
                      <span className="flex gap-1 items-center" style={MUTED}>
                        <span className="animate-bounce" style={{ animationDelay: "0ms" }}>·</span>
                        <span className="animate-bounce" style={{ animationDelay: "150ms" }}>·</span>
                        <span className="animate-bounce" style={{ animationDelay: "300ms" }}>·</span>
                      </span>
                    ) : (
                      msg.text
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => { e.preventDefault(); sendQuery(input); }}
            className="flex gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ex: Quels clients ROUGE à Sfax avec retard > 60 jours ?"
              disabled={!isAvailable}
              className="flex-1 rounded-xl px-4 py-3 text-sm outline-none transition-all disabled:opacity-40"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
            />
            <button
              type="submit"
              disabled={!isAvailable || sending || !input.trim()}
              className="px-5 py-3 rounded-xl text-sm font-medium transition-all disabled:opacity-40"
              style={{ background: "#3b82f6", color: "#fff" }}
            >
              {sending ? "…" : "Envoyer"}
            </button>
          </form>
        </motion.div>
      )}

      {/* Tab: Client Report */}
      {activeTab === "client" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadClientReport()}
              placeholder="ID client (ex: R_42, S_1637)"
              disabled={!isAvailable}
              className="flex-1 max-w-sm rounded-xl px-4 py-2.5 text-sm outline-none disabled:opacity-40"
              style={{ background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
            />
            <button
              onClick={loadClientReport}
              disabled={!isAvailable || clientLoading || !clientId.trim()}
              className="px-4 py-2.5 rounded-xl text-sm font-medium disabled:opacity-40"
              style={{ background: "#6d28d9", color: "#fff" }}
            >
              {clientLoading ? "Génération…" : "Générer rapport"}
            </button>
          </div>

          {clientError && (
            <p className="text-sm" style={{ color: "#ef4444" }}>{clientError}</p>
          )}

          {clientReport && (
            <div className="rounded-xl p-5 whitespace-pre-wrap text-sm leading-relaxed" style={CARD}>
              {clientReport}
            </div>
          )}

          {!clientReport && !clientError && !clientLoading && (
            <div className="rounded-xl p-8 text-center" style={{ ...CARD, ...MUTED }}>
              <p className="text-sm">Rapport complet : scores M2, segment, gouvernorat, contagion, concepts de risque — synthétisé par Claude</p>
            </div>
          )}
        </motion.div>
      )}

      {/* Tab: Knowledge Base */}
      {activeTab === "knowledge" && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6">
          {/* Explain concept */}
          <div className="rounded-xl p-5" style={CARD}>
            <h2 className="text-sm font-semibold mb-3" style={FG}>Expliquer un concept de risque</h2>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={conceptInput}
                onChange={(e) => setConceptInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && explainConcept(conceptInput)}
                placeholder="Ex: retard de paiement, contagion…"
                disabled={!isAvailable}
                className="flex-1 max-w-sm rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-40"
                style={{ background: "rgba(148,163,184,0.07)", border: "1px solid var(--card-border)", color: "var(--foreground)" }}
              />
              <button
                onClick={() => explainConcept(conceptInput)}
                disabled={!isAvailable || conceptLoading || !conceptInput.trim()}
                className="px-3 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
                style={{ background: "#3b82f6", color: "#fff" }}
              >
                {conceptLoading ? "…" : "Expliquer"}
              </button>
            </div>
            <div className="flex flex-wrap gap-2 mb-3">
              {EXAMPLE_CONCEPTS.map((c) => (
                <button
                  key={c}
                  onClick={() => { setConceptInput(c); explainConcept(c); }}
                  disabled={!isAvailable}
                  className="px-2.5 py-1 rounded-lg text-xs disabled:opacity-40"
                  style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.2)", color: "#8b5cf6" }}
                >
                  {c}
                </button>
              ))}
            </div>
            {conceptResult && (
              <div className="rounded-lg p-4 text-sm whitespace-pre-wrap leading-relaxed" style={{ background: "rgba(148,163,184,0.05)", ...FG }}>
                {conceptResult}
              </div>
            )}
          </div>

          {/* Concepts list */}
          <div className="rounded-xl p-5" style={CARD}>
            <h2 className="text-sm font-semibold mb-3" style={FG}>Concepts de risque</h2>
            {kbLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-12 rounded-lg animate-pulse" style={{ background: "rgba(148,163,184,0.07)" }} />
                ))}
              </div>
            ) : concepts.length === 0 ? (
              <p className="text-sm" style={MUTED}>Neo4j requis pour accéder aux concepts.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {concepts.map((c, i) => (
                  <div key={i} className="rounded-lg p-3" style={{ background: "rgba(148,163,184,0.05)", border: "1px solid var(--card-border)" }}>
                    <div className="flex items-start gap-3">
                      <span className="text-xs font-bold mt-0.5 px-2 py-0.5 rounded" style={{ background: "rgba(139,92,246,0.15)", color: "#8b5cf6" }}>
                        {c.nom}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs" style={FG}>{c.description}</p>
                        {c.seuils && <p className="text-xs mt-1" style={MUTED}>Seuils : {c.seuils}</p>}
                        {c.colonne && <p className="text-xs mt-0.5 font-mono" style={{ color: "#3b82f6" }}>{c.colonne}</p>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Rules list */}
          <div className="rounded-xl p-5" style={CARD}>
            <h2 className="text-sm font-semibold mb-3" style={FG}>Règles de décision</h2>
            {kbLoading ? (
              <div className="h-24 rounded-lg animate-pulse" style={{ background: "rgba(148,163,184,0.07)" }} />
            ) : rules.length === 0 ? (
              <p className="text-sm" style={MUTED}>Neo4j requis pour accéder aux règles.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--card-border)" }}>
                      {["ID", "Description", "Action", "Concept"].map((h) => (
                        <th key={h} className="text-left py-2 pr-4 font-medium text-xs" style={MUTED}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((r, i) => (
                      <tr key={i} className="border-b" style={{ borderColor: "var(--card-border)" }}>
                        <td className="py-2 pr-4 font-mono text-xs" style={{ color: "#f97316" }}>{r.id}</td>
                        <td className="py-2 pr-4 text-xs" style={FG}>{r.description}</td>
                        <td className="py-2 pr-4 text-xs" style={{ color: "#22c55e" }}>{r.action}</td>
                        <td className="py-2 text-xs" style={MUTED}>{r.concept_parent}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
