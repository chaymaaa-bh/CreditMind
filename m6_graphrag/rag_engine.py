"""
CreditMind M6 — RAG Engine
Neo4j PropertyGraphIndex + LlamaIndex + Claude Sonnet 4.6

Usage:
  from m6_graphrag.rag_engine import CreditMindRAG
  rag = CreditMindRAG()
  print(rag.query("Quels clients ROUGE dans le gouvernorat de Sfax ?"))
  print(rag.get_client_report("R_42"))
  print(rag.explain_concept("retard de paiement"))
  print(rag.contagion_analysis("R_5", depth=2))
"""

import os
import json
import logging
import argparse
from typing import Any, Optional

import anthropic
from dotenv import load_dotenv

from llama_index.core import PropertyGraphIndex, Settings
from llama_index.core.indices.property_graph import TextToCypherRetriever
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.llms.anthropic import Anthropic as AnthropicLLM

load_dotenv()
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement '{name}' manquante. "
            "Vérifiez votre fichier .env (NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, ANTHROPIC_API_KEY)."
        )
    return value


# ── Configuration ──────────────────────────────────────────────────────────────
NEO4J_URI  = _require_env("NEO4J_URI")
NEO4J_USER = _require_env("NEO4J_USERNAME")
NEO4J_PASS = _require_env("NEO4J_PASSWORD")
NEO4J_DB   = os.getenv("NEO4J_DATABASE", "neo4j")  # AuraDB : souvent nommé comme l'instance ID
ANTH_KEY   = os.getenv("ANTHROPIC_API_KEY")
MODEL      = "claude-sonnet-4-6"

# ── Schéma Neo4j pour le prompt Text→Cypher ────────────────────────────────────
_GRAPH_SCHEMA = """
NŒUDS:
  Client        : client_id (str, "R_i"|"S_i"), source ("REEL"|"SYNTHETIQUE"),
                  alerte ("VERT"|"ORANGE"|"ROUGE"), label_risque (0|1),
                  score_final_m2 (float 0-100), score_gnn (float), score_contagion (float),
                  nb_reglements (int), retard_max_jours (float), taux_retard (float 0-1),
                  anciennete_jours (int), montant_ttc_total (float), ratio_encaissement (float)
  Gouvernorat   : nom (str, ex: "SFAX"), region (str), taux_risque (float), nb_clients (int)
  SegmentClient : nom (str, ex: "GRN"), famille (str), taux_risque (float), nb_clients (int)
  ModePaiement  : mnemonique (str, ex: "ETRT"), libelle (str), taux_risque (float)
  Commercial    : code (str), nb_clients (int), taux_risque (float)
  AlerteRisque  : niveau ("VERT"|"ORANGE"|"ROUGE")
  ConceptRisque : nom (str), description (str), seuils (str), signal_column (str)
  RegleDecision : regle_id (str), description (str), condition_cypher (str), action (str)

RELATIONS:
  (Client)-[:SITUE_DANS]->(Gouvernorat)
  (Client)-[:APPARTIENT_AU_SEGMENT]->(SegmentClient)
  (Client)-[:PAIE_VIA]->(ModePaiement)
  (Client)-[:SUIVI_PAR]->(Commercial)
  (Client)-[:CLASSIFIE_COMME {score_gnn, score_contagion, score_final_m2}]->(AlerteRisque)
  (Client)-[:CONTAGION_TERRITOIRE {poids: float}]->(Client)
  (Client)-[:CONTAGION_PORTEFEUILLE {poids: float}]->(Client)
  (ConceptRisque)-[:DEFINI_PAR]->(RegleDecision)
  (SegmentClient)-[:ASSOCIE_AU_CONCEPT {taux_risque}]->(ConceptRisque)
  (Gouvernorat)-[:ASSOCIE_AU_CONCEPT {taux_risque}]->(ConceptRisque)
  (ModePaiement)-[:SIGNAL_DE]->(ConceptRisque)
  (Client)-[:PRESENTE]->(ConceptRisque)
"""

_CYPHER_EXAMPLES = """
Q: Clients ROUGE dans le gouvernorat de Sfax
C: MATCH (c:Client {alerte:'ROUGE'})-[:SITUE_DANS]->(g:Gouvernorat {nom:'SFAX'}) RETURN c.client_id, c.score_final_m2, c.taux_retard ORDER BY c.score_final_m2 DESC LIMIT 20

Q: Taux de risque par segment
C: MATCH (c:Client)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient) WITH s.nom AS seg, count(c) AS total, sum(c.label_risque) AS risques RETURN seg, total, risques, round(toFloat(risques)/total*100,1) AS pct_risque ORDER BY pct_risque DESC

Q: Voisins de contagion du client R_5
C: MATCH (c:Client {client_id:'R_5'})-[r:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE]->(v:Client) RETURN type(r) AS type_contagion, v.client_id, v.alerte, v.score_final_m2, r.poids ORDER BY r.poids DESC

Q: Distribution des alertes dans le portefeuille
C: MATCH (c:Client)-[:CLASSIFIE_COMME]->(a:AlerteRisque) WITH a.niveau AS alerte, count(c) AS nb RETURN alerte, nb ORDER BY CASE alerte WHEN 'ROUGE' THEN 1 WHEN 'ORANGE' THEN 2 ELSE 3 END

Q: Concepts de risque disponibles
C: MATCH (cr:ConceptRisque) RETURN cr.nom, cr.description, cr.seuils ORDER BY cr.nom

Q: Règles de décision actives
C: MATCH (rd:RegleDecision) RETURN rd.regle_id, rd.description, rd.action ORDER BY rd.regle_id

Q: Mode de paiement le plus risqué
C: MATCH (c:Client)-[:PAIE_VIA]->(m:ModePaiement) WITH m.mnemonique AS mode, m.libelle, count(c) AS total, sum(c.label_risque) AS risques RETURN mode, libelle, total, round(toFloat(risques)/total*100,1) AS pct_risque ORDER BY pct_risque DESC LIMIT 5

Q: Clients réels avec retard > 90 jours
C: MATCH (c:Client {source:'REEL'}) WHERE c.retard_max_jours > 90 RETURN c.client_id, c.alerte, c.retard_max_jours, c.taux_retard, c.score_final_m2 ORDER BY c.retard_max_jours DESC LIMIT 20
"""

_CYPHER_PROMPT = PromptTemplate(
    "Tu es expert Cypher Neo4j pour CreditMind, base de données de risque de crédit commercial tunisien.\n"
    "Génère UNE SEULE requête Cypher valide en lecture (MATCH/RETURN uniquement, pas de CREATE/DELETE/SET).\n"
    "Pas de commentaires, pas de markdown, pas d'explication — UNIQUEMENT la requête Cypher.\n\n"
    "=== SCHÉMA ===\n{schema}\n\n"
    "=== EXEMPLES ===\n{examples}\n\n"
    "=== QUESTION ===\n{query_str}\n\n"
    "Requête Cypher :"
)

_SYSTEM_PROMPT = (
    "Tu es l'assistant IA de CreditMind, système d'analyse du risque de crédit commercial tunisien.\n"
    "Base : 21 637 clients (1 637 réels R_i + 20 000 synthétiques S_i), scorés par GraphSAGE (M2).\n\n"
    "Règles de scoring :\n"
    "  VERT   = score_final_m2 < 30   → faible risque\n"
    "  ORANGE = score_final_m2 30–70  → risque modéré, surveillance\n"
    "  ROUGE  = score_final_m2 > 70   → risque élevé, action requise\n\n"
    "Réponds toujours en français, de façon concise et orientée décision métier."
)


class CreditMindRAG:
    """RAG Engine GraphRAG pour l'analyse de risque de crédit CreditMind.

    Combine un graphe Neo4j (PropertyGraphIndex) avec Claude Sonnet 4.6
    pour répondre à des questions en langage naturel sur le portefeuille.
    """

    def __init__(
        self,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_pass: str = NEO4J_PASS,
        neo4j_database: str = NEO4J_DB,
        model: str = MODEL,
    ) -> None:
        self._model = model
        self._anth = anthropic.Anthropic(api_key=ANTH_KEY)

        # ── LlamaIndex LLM (used by TextToCypherRetriever internally) ─────────
        llm = AnthropicLLM(
            model=model,
            api_key=ANTH_KEY,
            max_tokens=1024,
        )
        Settings.llm = llm

        # ── Graph store ────────────────────────────────────────────────────────
        # Workaround: llama-index-graph-stores-neo4j 0.7.0 bug — _enhanced_schema_cypher
        # calls self.query() which doesn't exist; alias it to structured_query.
        if not hasattr(Neo4jPropertyGraphStore, "query"):
            Neo4jPropertyGraphStore.query = Neo4jPropertyGraphStore.structured_query
        self._graph_store = Neo4jPropertyGraphStore(
            username=neo4j_user,
            password=neo4j_pass,
            url=neo4j_uri,
            database=neo4j_database,
        )

        # ── PropertyGraphIndex (built by ingest.py — no documents to add) ─────
        self._index = PropertyGraphIndex.from_existing(
            property_graph_store=self._graph_store,
            llm=llm,
        )

        # ── Text→Cypher retriever ──────────────────────────────────────────────
        self._cypher_retriever = TextToCypherRetriever(
            graph_store=self._graph_store,
            llm=llm,
            text_to_cypher_template=_CYPHER_PROMPT,
            extra_instructions=(
                f"{_GRAPH_SCHEMA}\n\nExemples :\n{_CYPHER_EXAMPLES}"
            ),
        )

        logger.info("CreditMindRAG prêt — modèle=%s  neo4j=%s  db=%s", model, neo4j_uri, neo4j_database)

    # ── Utilitaires internes ──────────────────────────────────────────────────

    def _run_cypher(self, cypher: str, params: Optional[dict] = None) -> list[dict]:
        """Exécute une requête Cypher et retourne les résultats."""
        try:
            rows = self._graph_store.structured_query(cypher, param_map=params or {})
            return rows if rows else []
        except Exception as exc:
            logger.error("Erreur Cypher: %s\nRequête: %s", exc, cypher)
            return []

    def _generate_cypher(self, question: str) -> str:
        """Génère une requête Cypher à partir d'une question en langage naturel."""
        prompt = (
            f"Schéma Neo4j CreditMind :\n{_GRAPH_SCHEMA}\n\n"
            f"Exemples :\n{_CYPHER_EXAMPLES}\n\n"
            f"Question : {question}\n\n"
            "Génère UNE SEULE requête Cypher en lecture (MATCH/RETURN). "
            "Pas de commentaires, pas de markdown — juste la requête.\n\nCypher :"
        )
        response = self._anth.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text content from the response
        for block in response.content:
            if block.type == "text":
                cypher = block.text.strip()
                # Strip markdown code fences if present
                if cypher.startswith("```"):
                    lines = cypher.splitlines()
                    cypher = "\n".join(
                        ln for ln in lines
                        if not ln.startswith("```")
                    ).strip()
                return cypher
        return ""

    def _synthesize(self, question: str, data: list[dict], context: str = "") -> str:
        """Synthèse en langage naturel via Claude avec streaming."""
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        user_content = (
            f"Question : {question}\n\n"
            f"Données du graphe CreditMind :\n```json\n{data_str}\n```"
        )
        if context:
            user_content += f"\n\nContexte supplémentaire :\n{context}"
        user_content += "\n\nFournis une réponse concise, orientée décision métier."

        chunks: list[str] = []
        with self._anth.messages.stream(
            model=self._model,
            max_tokens=1024,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            for text in stream.text_stream:
                chunks.append(text)

        return "".join(chunks)

    # ── API publique ──────────────────────────────────────────────────────────

    def query(self, question: str) -> str:
        """Répond à une question en langage naturel sur le graphe CreditMind.

        Flux : NL → Cypher → résultats Neo4j → synthèse Claude.
        """
        cypher = self._generate_cypher(question)
        if not cypher:
            return "Impossible de générer une requête Cypher pour cette question."
        logger.debug("Cypher généré : %s", cypher)

        rows = self._run_cypher(cypher)
        if not rows:
            return f"Aucun résultat pour la requête générée :\n{cypher}"

        return self._synthesize(question, rows)

    def get_client_report(self, client_id: str) -> str:
        """Rapport complet sur un client : scores, segment, localisation, contagion, concepts."""
        cypher_profile = """
        MATCH (c:Client {client_id: $cid})
        OPTIONAL MATCH (c)-[:SITUE_DANS]->(g:Gouvernorat)
        OPTIONAL MATCH (c)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient)
        OPTIONAL MATCH (c)-[:PAIE_VIA]->(m:ModePaiement)
        OPTIONAL MATCH (c)-[:SUIVI_PAR]->(com:Commercial)
        OPTIONAL MATCH (c)-[r:CLASSIFIE_COMME]->(a:AlerteRisque)
        RETURN
          c.client_id AS id, c.source AS source, c.alerte AS alerte,
          c.score_final_m2 AS score_m2, c.score_gnn AS score_gnn,
          c.score_contagion AS score_contagion,
          c.nb_reglements AS nb_regl, c.retard_max_jours AS retard_max,
          c.taux_retard AS taux_retard, c.anciennete_jours AS anciennete,
          c.montant_ttc_total AS montant_ttc, c.ratio_encaissement AS ratio_enc,
          g.nom AS gouvernorat, g.region AS region,
          s.nom AS segment, s.famille AS famille,
          m.mnemonique AS mode_paiement,
          com.code AS commercial
        """

        cypher_contagion = """
        MATCH (c:Client {client_id: $cid})-[r:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE]->(v:Client)
        RETURN type(r) AS type_contagion, v.client_id AS voisin_id,
               v.alerte AS voisin_alerte, v.score_final_m2 AS voisin_score,
               r.poids AS poids
        ORDER BY r.poids DESC
        """

        cypher_concepts = """
        MATCH (c:Client {client_id: $cid})-[:PRESENTE]->(cr:ConceptRisque)
        RETURN cr.nom AS concept, cr.description AS description, cr.seuils AS seuils
        """

        params = {"cid": client_id}
        profile   = self._run_cypher(cypher_profile, params)
        contagion = self._run_cypher(cypher_contagion, params)
        concepts  = self._run_cypher(cypher_concepts, params)

        if not profile:
            return f"Client '{client_id}' introuvable dans le graphe."

        data = {
            "profil": profile[0] if profile else {},
            "contagion": contagion,
            "concepts_risque": concepts,
        }
        question = f"Génère un rapport de risque complet pour le client {client_id}."
        return self._synthesize(question, [data])

    def explain_concept(self, concept_name: str) -> str:
        """Explique un concept de risque et les règles de décision associées."""
        cypher = """
        MATCH (cr:ConceptRisque)
        WHERE toLower(cr.nom) CONTAINS toLower($name)
           OR toLower(cr.description) CONTAINS toLower($name)
        OPTIONAL MATCH (cr)-[:DEFINI_PAR]->(rd:RegleDecision)
        OPTIONAL MATCH (s:SegmentClient)-[:ASSOCIE_AU_CONCEPT]->(cr)
        OPTIONAL MATCH (g:Gouvernorat)-[:ASSOCIE_AU_CONCEPT]->(cr)
        OPTIONAL MATCH (m:ModePaiement)-[:SIGNAL_DE]->(cr)
        RETURN
          cr.nom AS concept, cr.description AS description,
          cr.seuils AS seuils, cr.signal_column AS colonne,
          collect(DISTINCT rd.regle_id + ': ' + rd.description) AS regles,
          collect(DISTINCT rd.action) AS actions,
          collect(DISTINCT s.nom) AS segments_associes,
          collect(DISTINCT g.nom) AS gouvernorats_associes,
          collect(DISTINCT m.mnemonique) AS modes_signaleurs
        """
        rows = self._run_cypher(cypher, {"name": concept_name})
        if not rows:
            return f"Concept '{concept_name}' introuvable dans la base de connaissances."

        question = f"Explique le concept de risque '{concept_name}' et les règles métier associées."
        return self._synthesize(question, rows)

    def contagion_analysis(self, client_id: str, depth: int = 2) -> str:
        """Analyse la propagation du risque par contagion jusqu'à `depth` niveaux."""
        depth = min(depth, 3)  # limiter la profondeur pour éviter les explosions

        cypher = f"""
        MATCH path = (c:Client {{client_id: $cid}})
          -[:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE*1..{depth}]->(v:Client)
        WITH v, min(length(path)) AS niveau,
             collect(DISTINCT [n IN nodes(path) | n.client_id]) AS chemins
        RETURN v.client_id AS voisin, v.alerte AS alerte,
               v.score_final_m2 AS score_m2,
               v.gouvernorat_nom AS gouvernorat,
               v.segment_nom AS segment,
               niveau
        ORDER BY niveau ASC, score_m2 DESC
        LIMIT 50
        """

        # Statistiques d'exposition
        cypher_stats = f"""
        MATCH (c:Client {{client_id: $cid}})
          -[:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE*1..{depth}]->(v:Client)
        WITH v.alerte AS alerte, count(DISTINCT v) AS nb
        RETURN alerte, nb
        ORDER BY CASE alerte WHEN 'ROUGE' THEN 1 WHEN 'ORANGE' THEN 2 ELSE 3 END
        """

        params = {"cid": client_id}
        voisins = self._run_cypher(cypher, params)
        stats   = self._run_cypher(cypher_stats, params)

        if not voisins:
            return f"Aucun voisin de contagion trouvé pour '{client_id}' (profondeur={depth})."

        data = {
            "client": client_id,
            "profondeur_analysee": depth,
            "distribution_alertes_voisins": stats,
            "voisins_details": voisins,
        }
        question = (
            f"Analyse le risque de contagion du client {client_id} "
            f"sur {depth} niveaux de propagation. "
            "Identifie les clusters à risque et recommande des actions."
        )
        return self._synthesize(question, [data])

    def portfolio_overview(self) -> str:
        """Vue globale du portefeuille : distribution des risques, top gouvernorats, segments."""
        queries = {
            "alertes": (
                "MATCH (c:Client) RETURN c.alerte AS alerte, count(c) AS nb "
                "ORDER BY CASE c.alerte WHEN 'ROUGE' THEN 1 WHEN 'ORANGE' THEN 2 ELSE 3 END"
            ),
            "risque_par_gouvernorat": (
                "MATCH (c:Client)-[:SITUE_DANS]->(g:Gouvernorat) "
                "WITH g.nom AS gvt, count(c) AS total, sum(c.label_risque) AS risques "
                "RETURN gvt, total, risques, "
                "round(toFloat(risques)/total*100,1) AS pct_risque "
                "ORDER BY pct_risque DESC LIMIT 10"
            ),
            "risque_par_segment": (
                "MATCH (c:Client)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient) "
                "WITH s.nom AS seg, count(c) AS total, sum(c.label_risque) AS risques "
                "RETURN seg, total, risques, "
                "round(toFloat(risques)/total*100,1) AS pct_risque "
                "ORDER BY pct_risque DESC LIMIT 10"
            ),
            "score_moyen": (
                "MATCH (c:Client {source:'REEL'}) "
                "RETURN avg(c.score_final_m2) AS score_moyen, "
                "avg(c.taux_retard) AS taux_retard_moyen, "
                "avg(c.retard_max_jours) AS retard_max_moyen"
            ),
        }

        results: dict[str, Any] = {}
        for key, cypher in queries.items():
            results[key] = self._run_cypher(cypher)

        question = (
            "Génère un rapport de synthèse du portefeuille crédit : "
            "distribution des risques, zones géographiques à risque, "
            "segments vulnérables et recommandations prioritaires."
        )
        return self._synthesize(question, [results])

    def list_concepts(self) -> list[dict]:
        """Retourne la liste des concepts de risque de la base de connaissances."""
        return self._run_cypher(
            "MATCH (cr:ConceptRisque) "
            "RETURN cr.nom AS nom, cr.description AS description, "
            "cr.seuils AS seuils, cr.signal_column AS colonne "
            "ORDER BY cr.nom"
        )

    def list_decision_rules(self) -> list[dict]:
        """Retourne les règles de décision avec leur logique."""
        return self._run_cypher(
            "MATCH (rd:RegleDecision) "
            "OPTIONAL MATCH (cr:ConceptRisque)-[:DEFINI_PAR]->(rd) "
            "RETURN rd.regle_id AS id, rd.description AS description, "
            "rd.action AS action, cr.nom AS concept_parent "
            "ORDER BY rd.regle_id"
        )


# ── CLI interactif ─────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="CreditMind M6 — RAG Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python rag_engine.py --query "Quels clients ROUGE à Sfax ?"
  python rag_engine.py --client R_42
  python rag_engine.py --concept "retard de paiement"
  python rag_engine.py --contagion R_5 --depth 2
  python rag_engine.py --overview
  python rag_engine.py --concepts
  python rag_engine.py --rules
  python rag_engine.py --interactive
        """,
    )
    parser.add_argument("--query",       type=str, help="Question en langage naturel")
    parser.add_argument("--client",      type=str, help="Rapport client (ex: R_42)")
    parser.add_argument("--concept",     type=str, help="Expliquer un concept de risque")
    parser.add_argument("--contagion",   type=str, help="Analyse contagion pour un client")
    parser.add_argument("--depth",       type=int, default=2, help="Profondeur contagion (défaut: 2)")
    parser.add_argument("--overview",    action="store_true", help="Vue globale du portefeuille")
    parser.add_argument("--concepts",    action="store_true", help="Lister les concepts de risque")
    parser.add_argument("--rules",       action="store_true", help="Lister les règles de décision")
    parser.add_argument("--interactive", action="store_true", help="Mode interactif (REPL)")
    parser.add_argument("--model",       type=str, default=MODEL, help="Modèle Claude")
    parser.add_argument("--debug",       action="store_true", help="Activer les logs DEBUG")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("Connexion au graphe CreditMind...", flush=True)
    rag = CreditMindRAG(model=args.model)
    print("Prêt.\n")

    def _print(title: str, content: str | list) -> None:
        print(f"\n{'═' * 60}")
        print(f"  {title}")
        print(f"{'═' * 60}")
        if isinstance(content, list):
            for item in content:
                print(json.dumps(item, ensure_ascii=False, indent=2))
        else:
            print(content)
        print()

    if args.query:
        _print(f"Requête : {args.query}", rag.query(args.query))

    elif args.client:
        _print(f"Rapport client : {args.client}", rag.get_client_report(args.client))

    elif args.concept:
        _print(f"Concept : {args.concept}", rag.explain_concept(args.concept))

    elif args.contagion:
        _print(
            f"Contagion : {args.contagion} (profondeur={args.depth})",
            rag.contagion_analysis(args.contagion, depth=args.depth),
        )

    elif args.overview:
        _print("Vue globale du portefeuille", rag.portfolio_overview())

    elif args.concepts:
        _print("Concepts de risque", rag.list_concepts())

    elif args.rules:
        _print("Règles de décision", rag.list_decision_rules())

    elif args.interactive:
        print("Mode interactif — tapez 'exit' pour quitter.\n")
        print("Commandes spéciales :")
        print("  :client <id>       → rapport client")
        print("  :concept <terme>   → expliquer un concept")
        print("  :contagion <id>    → analyse contagion (profondeur 2)")
        print("  :overview          → vue portefeuille\n")
        while True:
            try:
                user_input = input("CreditMind> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nAu revoir.")
                break
            if not user_input or user_input.lower() in ("exit", "quit", "q"):
                print("Au revoir.")
                break
            if user_input.startswith(":client "):
                _print("Rapport", rag.get_client_report(user_input[8:].strip()))
            elif user_input.startswith(":concept "):
                _print("Concept", rag.explain_concept(user_input[9:].strip()))
            elif user_input.startswith(":contagion "):
                _print("Contagion", rag.contagion_analysis(user_input[11:].strip()))
            elif user_input == ":overview":
                _print("Vue portefeuille", rag.portfolio_overview())
            else:
                _print("Réponse", rag.query(user_input))

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
