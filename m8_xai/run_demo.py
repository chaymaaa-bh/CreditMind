"""
Demo M8 XAI — teste le pipeline sur 4 profils représentatifs.
Usage : python -m m8_xai.run_demo
"""
from __future__ import annotations

import json
from m8_xai.api import explain

# client 0  → SAIN (VERT,  score ~95)
# client 1  → RISQUE_ELEVE (ROUGE, score ~5)
# client 50 → profil intermédiaire à vérifier
# client 200 → dans les 200 couverts par M3 (forecast réel disponible)
DEMO_CLIENTS = [0, 1, 50, 200]


def _banner(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def _print_alert(a: dict) -> None:
    print(f"  Niveau       : {a['niveau_alerte']}")
    print(f"  Score M5     : {a['score_solvabilite']}/100")
    print(f"  Prob. défaut : {a['prob_defaut']:.1%}")
    print(f"  Score anomalie M4 : {a['score_anomalie']}/100")
    for t in a["triggers"]:
        print(f"  ⚠  {t}")


def _print_shap(s: dict) -> None:
    for f in s.get("top_features", [])[:5]:
        sign = "▲" if f["direction"] == "aggrave" else "▼"
        print(f"  {sign} {f['label']:<40} SHAP={f['shap_value']:+.4f}  val={f['feature_value']:.3f}")


def _print_cf(cf: dict) -> None:
    if cf.get("message"):
        print(f"  {cf['message']}")
        return
    for s in cf.get("suggestions", [])[:3]:
        tick = "✓" if s["atteint_seuil"] else "~"
        print(f"  {tick} {s['label']:<40}  effort={s['effort_pct']}%  "
              f"prob {cf['current_prob']:.3f} → {s['nouvelle_prob']:.3f}")


def main() -> None:
    for cid in DEMO_CLIENTS:
        _banner(f"Client {cid}")
        result = explain(cid, with_narrative=False)

        print("\n[ALERTE]")
        _print_alert(result["alert"])

        print("\n[SHAP — top 5 features]")
        _print_shap(result["shap"])

        print("\n[CONTRE-FACTUELS — top 3 actions]")
        _print_cf(result["counterfactual"])

    print("\n[OK] Demo M8 terminée.")


if __name__ == "__main__":
    main()
