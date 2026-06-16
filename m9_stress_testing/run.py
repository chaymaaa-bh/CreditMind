"""
CreditMind M9 — Stress Testing Agentique
CLI : python -m m9_stress_testing.run --scenario "..." [--n 500] [--output file.json]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import Any

import numpy as np

from .contagion import run_contagion
from .indicators import compute_indicators
from .report import generate_report
from .scenario_parser import parse_scenario
from .simulator import load_clients, run_simulation


def _section(title: str) -> None:
    print(f"\n{'═' * 65}")
    print(f"  {title}")
    print(f"{'═' * 65}")


def main(
    scenario_text: str,
    n_simulations: int = 500,
    seed: int = 42,
    output_path: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        )

    t0 = time.time()

    # ── 1. Parsing du scénario ─────────────────────────────────────────────────
    print("⟳ Parsing du scénario via Claude...")
    params = parse_scenario(scenario_text)

    _section("SCÉNARIO PARSÉ")
    print(f"  Description : {params['description_originale']}")
    print(f"  Catégorie   : {params['categorie']}")
    print(f"  Intensité   : {params['intensite']}")
    print(f"  Durée       : {params['duree_mois']} mois")
    print(f"  Périmètre   : {', '.join(params['gouvernorats_cibles']) or 'Tout le portefeuille'}")
    print(f"  Segments    : {', '.join(params['segments_cibles']) or 'Tous les segments'}")
    print("  Perturbations :")
    for d in params["feature_deltas"]:
        if d["delta_type"] == "multiplicatif":
            pct = f"{'+' if d['delta_value'] >= 0 else ''}{d['delta_value'] * 100:.0f}%"
        else:
            pct = f"{'+' if d['delta_value'] >= 0 else ''}{d['delta_value']:.2f}"
        print(f"    {d['feature']:<30s}  {d['delta_type']:<15s}  {pct}  (±{d['std_pct'] * 100:.0f}%)")

    # ── 2. Chargement des clients ──────────────────────────────────────────────
    print("\n⟳ Chargement des clients depuis Neo4j...")
    clients = load_clients(params)
    print(f"  {len(clients):,} clients chargés.")

    if not clients:
        print("  Aucun client trouvé pour ce périmètre. Vérifiez les filtres.")
        sys.exit(1)

    # ── 3. Simulation Monte Carlo ──────────────────────────────────────────────
    print(f"\n⟳ Simulation Monte Carlo ({n_simulations} runs × {len(clients):,} clients)...")
    sim = run_simulation(clients, params, n_simulations=n_simulations, seed=seed)
    print(f"  Terminé en {time.time() - t0:.1f}s.")

    # ── 4. Indicateurs ────────────────────────────────────────────────────────
    indicators = compute_indicators(clients, sim)

    _section("INDICATEURS DE STRESS")
    print(f"  Clients analysés            : {indicators['nb_clients_analyses']:>8,}")
    print(f"  Clients → ROUGE (médiane)   : {indicators['nb_clients_bascule_rouge']:>8,}"
          f"  ({indicators['pct_bascule_rouge']:.1f}%)")
    print(f"  Δ Score moyen               : {indicators['delta_score_moyen']:>+8.1f} pts")
    print(f"  Δ Retard moyen de paiement  : {indicators['delta_retard_moyen_jours']:>+8.1f} jours")
    print(f"  EaRS (médiane)              : {indicators['encours_a_risque_stresse']:>14,.0f} TND")
    lo, hi = indicators["ic95_EaRS"]
    print(f"  EaRS IC 95%                 : [{lo:,.0f}  —  {hi:,.0f}] TND")
    print(f"  Provision recommandée       : {indicators['provision_recommandee']:>14,.0f} TND")

    _section("DISTRIBUTION DES ALERTES")
    av, ap = indicators["distribution_avant"], indicators["distribution_apres"]
    print(f"  {'Alerte':<10}  {'Avant':>10}  {'Après':>10}  {'Δ':>8}")
    print(f"  {'-' * 42}")
    for niveau in ("VERT", "ORANGE", "ROUGE"):
        delta = ap[niveau] - av[niveau]
        sign  = "+" if delta >= 0 else ""
        print(f"  {niveau:<10}  {av[niveau]:>10,}  {ap[niveau]:>10,}  {sign}{delta:>7,}")

    # ── 5. Contagion (scénario défaillance systémique uniquement) ─────────────
    contagion_result: dict[str, Any] | None = None
    if params["categorie"] == "contagion":
        # Clients nouvellement ROUGE dans la simulation médiane
        baseline_rouge_bool = sim["baseline_scores"] >= 70
        EaRS_per_sim        = (
            ((sim["score_matrix"] >= 70) & ~baseline_rouge_bool).astype(float)
            * sim["baseline_encours"]
        ).sum(axis=1)
        median_idx   = int(np.argsort(EaRS_per_sim)[n_simulations // 2])
        new_rouge_ids = [
            c["client_id"] for i, c in enumerate(clients)
            if sim["score_matrix"][median_idx, i] >= 70 and not baseline_rouge_bool[i]
        ]

        print(f"\n⟳ Propagation contagion depuis {len(new_rouge_ids)} déclencheurs (profondeur 2)...")
        contagion_result = run_contagion(new_rouge_ids, depth=2)

        _section("CONTAGION")
        print(f"  Clients déclencheurs : {len(new_rouge_ids):,}")
        print(f"  Clients contaminés   : {contagion_result['nb_contamines']:,}")
        print(f"  Encours propagé      : {contagion_result['encours_cumule']:,.0f} TND")
        for v in contagion_result["vagues"]:
            print(f"  Vague {v['niveau']}              : {len(v['clients']):,} clients")

    # ── 6. Rapport narratif ────────────────────────────────────────────────────
    print("\n⟳ Génération du rapport narratif (Claude + thinking adaptatif)...")
    rapport = generate_report(params, indicators, contagion=contagion_result)

    _section("RAPPORT DE STRESS-TEST")
    print(rapport)

    # ── 7. Export JSON (optionnel) ────────────────────────────────────────────
    result: dict[str, Any] = {
        "scenario":    params,
        "indicateurs": indicators,
        "rapport":     rapport,
    }
    if contagion_result:
        result["contagion"] = contagion_result

    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
        print(f"\n  Résultats exportés : {output_path}")

    print(f"\n  Stress-test terminé en {time.time() - t0:.1f}s.")
    return result


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="CreditMind M9 — Stress Testing Agentique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python -m m9_stress_testing.run --scenario "hausse des prix de l'énergie de 30% sur 6 mois"
  python -m m9_stress_testing.run --scenario "sécheresse grave dans le gouvernorat de Sfax" --n 500
  python -m m9_stress_testing.run --scenario "contraction du crédit bancaire de 25%" --output rapport.json
  python -m m9_stress_testing.run --scenario "défaillance systémique contagion" --n 200
        """,
    )
    parser.add_argument("--scenario", required=True,
                        help="Description du scénario de crise en langage naturel")
    parser.add_argument("--n",      type=int, default=500,
                        help="Nombre de simulations Monte Carlo (défaut : 500)")
    parser.add_argument("--seed",   type=int, default=42,
                        help="Graine aléatoire pour reproductibilité (défaut : 42)")
    parser.add_argument("--output", type=str, default=None,
                        help="Chemin fichier JSON de sortie (optionnel)")
    parser.add_argument("--verbose", action="store_true",
                        help="Activer les logs DEBUG")
    args = parser.parse_args()

    main(
        scenario_text=args.scenario,
        n_simulations=args.n,
        seed=args.seed,
        output_path=args.output,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    _cli()
