#!/usr/bin/env python3
"""
CreditMind M7 — Système multi-agents d'analyse de risque

Usage :
  python m7_agents/run.py --client R_42
  python m7_agents/run.py --client S_1234 --json
"""
from __future__ import annotations

import os
# Désactive le tracing LangSmith (pas de clé API configurée)
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

import argparse
import json
import sys
import time
from pathlib import Path

# Repo root dans sys.path pour les imports m6_graphrag / m7_agents
sys.path.insert(0, str(Path(__file__).parent.parent))

from m7_agents.graph import graph


def _sep(title: str) -> None:
    w = 64
    print(f"\n{'═' * w}\n  {title}\n{'═' * w}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CreditMind M7 — Analyse multi-agents")
    parser.add_argument("--client", required=True, help="ID client (ex: R_42, S_1234)")
    parser.add_argument("--json",   action="store_true", help="Dump JSON brut de l'état final")
    args = parser.parse_args()

    print(f"\n⚙  Démarrage de l'analyse multi-agents pour {args.client} ...")
    t0 = time.time()

    initial: dict = {
        "client_id":       args.client,
        "profil_brut":     None,
        "comportement":    None,
        "reseau":          None,
        "forecast":        None,
        "anomalies":       None,
        "compliance":      None,
        "raisonnement":    None,
        "rapport_final":   None,
        "agents_completes": [],
        "erreurs":         [],
    }

    try:
        result = graph.invoke(initial)
    except ValueError as exc:
        print(f"\n[ERREUR] {exc}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - t0

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return

    rf = result.get("rapport_final") or {}
    r  = result.get("raisonnement") or {}

    _sep(f"RAPPORT FINAL — {args.client}")
    print(
        f"Décision      : {rf.get('decision', 'N/A')}\n"
        f"Score global  : {rf.get('score_global', 0):.1f} / 100\n"
        f"Alerte        : {rf.get('alerte_finale', 'N/A')}\n"
        f"Réévaluation  : {rf.get('horizon_reevaluation', 'N/A')}"
    )

    _sep("RAPPORT NARRATIF")
    print(rf.get("rapport_narratif", "Non disponible"))

    actions = rf.get("actions_recommandees") or []
    if actions:
        _sep("ACTIONS RECOMMANDÉES")
        for i, a in enumerate(actions, 1):
            print(f"  {i}. {a}")

    _sep("SYNTHÈSE DES AGENTS")
    print(
        f"Score consensus : {r.get('score_consensus', 'N/A')}\n"
        f"Confiance       : {r.get('niveau_confiance', 'N/A')}\n"
        f"Agents mock     : {', '.join(r.get('agents_mock', [])) or 'aucun'}\n"
        f"Séquence        : {' → '.join(result.get('agents_completes', []))}"
    )

    if result.get("erreurs"):
        _sep("ERREURS")
        for e in result["erreurs"]:
            print(f"  ⚠  {e}")

    print(f"\n✓  Analyse terminée en {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
