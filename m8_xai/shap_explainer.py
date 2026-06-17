from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

_ROOT = Path(__file__).parent.parent

_xgb_model  = None
_scaler     = None
_feature_cols: list[str] | None = None
_explainer  = None
_data_index: dict[int, np.ndarray] | None = None

FEATURE_LABELS: dict[str, str] = {
    "nb_factures":           "Nombre de factures",
    "montant_ttc_moyen":     "Montant TTC moyen",
    "montant_ttc_std":       "Volatilité des montants TTC",
    "retard_moyen_jours":    "Retard moyen de paiement (j)",
    "retard_max_jours":      "Retard maximal (j)",
    "taux_retard":           "Taux de retard",
    "nb_reglements":         "Nombre de règlements",
    "montant_reg_moyen":     "Montant moyen des règlements",
    "ratio_encaissement":    "Ratio d'encaissement",
    "gouvernorat_code":      "Gouvernorat",
    "nature_client_code":    "Nature du client",
    "mode_paiement_code":    "Mode de paiement",
    "gnn_risk_score":        "Score de risque réseau GNN",
    "contagion_score":       "Score de contagion",
    "gnn_final_score":       "Score final GNN",
    "gnn_risk_label":        "Label risque réseau",
    "m3_montant_h1":         "Prévision montant (M+1)",
    "m3_retard_h1":          "Prévision retard (M+1)",
    "m3_tendance_h1":        "Tendance M3 (M+1)",
    "m3_montant_h3":         "Prévision montant (M+3)",
    "m3_retard_h3":          "Prévision retard (M+3)",
    "score_anomalie_final":  "Score anomalie final M4",
    "score_anomalie_if":     "Score anomalie Isolation Forest",
    "score_anomalie_lstm":   "Score anomalie LSTM",
    "pred_ensemble":         "Prédiction ensemble anomalies",
    "risk_network_x_anomaly":"Risque réseau × anomalie",
    "gnn_x_anomaly_final":   "GNN × anomalie finale",
    "contagion_x_tendance":  "Contagion × tendance M3",
    "delta_retard_forecast": "Delta retard (prévu - actuel)",
    "retard_acceleration":   "Accélération du retard",
    "risk_composite":        "Score risque composite",
    "encours_ratio_forecast":"Ratio encours / prévision",
}


def _load_artifacts() -> None:
    global _xgb_model, _scaler, _feature_cols, _explainer
    if _xgb_model is not None:
        return
    _xgb_model = joblib.load(_ROOT / "m5_xgb_model.joblib")
    _scaler    = joblib.load(_ROOT / "m5_scaler.joblib")
    with open(_ROOT / "m5_feature_cols.json") as f:
        _feature_cols = json.load(f)
    _explainer = shap.TreeExplainer(_xgb_model)


def _build_data_index() -> dict[int, np.ndarray]:
    """Reconstruct the 32-feature matrix used in M5 training (same logic as m5_scoring_ensemble.py)."""
    _load_artifacts()

    df = pd.read_csv(_ROOT / "dataset_combined_real_synth.csv").reset_index(drop=True)
    df["client_id"] = df.index

    # M4 — anomaly scores
    m4_path = _ROOT / "m4_anomaly_scores.csv"
    if m4_path.exists():
        df_m4 = pd.read_csv(m4_path)
        if "client_id" not in df_m4.columns:
            df_m4["client_id"] = df_m4.index
        m4_cols = [c for c in ["score_anomalie_final", "score_anomalie_if", "score_anomalie_lstm", "pred_ensemble"]
                   if c in df_m4.columns]
        df = df.merge(df_m4[["client_id"] + m4_cols], on="client_id", how="left")

    # M3 — forecasts (pivot h=1 and h=3)
    m3_path = _ROOT / "m3_forecasts_individual.csv"
    if m3_path.exists():
        raw = pd.read_csv(m3_path)
        h1 = raw[raw["horizon_mois"] == 1][["client_id", "montant_regle_pred", "retard_pred", "risque_tendance"]].rename(
            columns={"montant_regle_pred": "m3_montant_h1", "retard_pred": "m3_retard_h1", "risque_tendance": "m3_tendance_h1"})
        h3 = raw[raw["horizon_mois"] == 3][["client_id", "montant_regle_pred", "retard_pred"]].rename(
            columns={"montant_regle_pred": "m3_montant_h3", "retard_pred": "m3_retard_h3"})
        df = df.merge(h1.merge(h3, on="client_id", how="outer"), on="client_id", how="left")

    # M2 — GNN scores (simulated with same seed as M5 when m2_gnn_scores.csv absent)
    m2_path = _ROOT / "m2_gnn_scores.csv"
    if m2_path.exists():
        df_m2 = pd.read_csv(m2_path).rename(columns={
            "client_index": "client_id", "score_gnn": "gnn_risk_score",
            "score_contagion": "contagion_score", "score_final_m2": "gnn_final_score",
            "label_reel": "gnn_risk_label",
        })
        for col in ["gnn_risk_score", "contagion_score", "gnn_final_score"]:
            if col in df_m2.columns:
                df_m2[col] = df_m2[col] / 100.0
        keep = [c for c in ["client_id", "gnn_risk_score", "contagion_score", "gnn_final_score", "gnn_risk_label"]
                if c in df_m2.columns]
        df = df.merge(df_m2[keep], on="client_id", how="left")
    else:
        # Reproduce exact simulation from M5 (seed=42, same distributions, same order)
        np.random.seed(42)
        n = len(df)
        label = df.get("label_risque", pd.Series(np.zeros(n))).values
        df["gnn_risk_score"]  = np.random.beta(2, 8, n)
        df["contagion_score"] = np.random.beta(1, 9, n)
        df["gnn_final_score"] = np.random.beta(2, 8, n)
        df["gnn_risk_label"]  = label

    # Feature engineering (identical to M5)
    df["risk_network_x_anomaly"] = df.get("gnn_risk_score", 0)     * df.get("score_anomalie_final", 0)
    df["contagion_x_tendance"]   = df.get("contagion_score", 0)     * df.get("m3_tendance_h1", 0)
    df["delta_retard_forecast"]  = df.get("m3_retard_h1", 0)        - df.get("retard_moyen_jours", 0)
    df["retard_acceleration"]    = df.get("m3_retard_h3", 0)        - df.get("m3_retard_h1", 0)
    df["risk_composite"]         = (df.get("gnn_risk_score", 0) + df.get("score_anomalie_final", 0) + df.get("contagion_score", 0)) / 3
    df["encours_ratio_forecast"] = df.get("montant_ttc_moyen", 1)   / df.get("m3_montant_h1", pd.Series(np.ones(len(df)))).replace(0, 1)
    df["gnn_x_anomaly_final"]    = df.get("gnn_final_score", 0)     * df.get("score_anomalie_final", 0)

    for col in _feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    df[_feature_cols] = df[_feature_cols].fillna(0.0)

    X_scaled = _scaler.transform(df[_feature_cols].values)
    return {int(df.at[i, "client_id"]): X_scaled[i] for i in range(len(df))}


def _get_data_index() -> dict[int, np.ndarray]:
    global _data_index
    if _data_index is None:
        _data_index = _build_data_index()
    return _data_index


def explain_local(client_id: int, top_n: int = 8) -> dict:
    """Return top-N SHAP contributors for a single client."""
    _load_artifacts()
    data = _get_data_index()

    if client_id not in data:
        return {"error": f"client {client_id} absent du dataset"}

    x_scaled = data[client_id].reshape(1, -1)
    x_orig   = _scaler.inverse_transform(x_scaled)[0]

    shap_vals = _explainer.shap_values(x_scaled)
    # TreeExplainer on XGB binary: returns (1, n_features) ndarray
    sv = shap_vals[0] if shap_vals.ndim == 2 else shap_vals

    indices = np.argsort(np.abs(sv))[::-1][:top_n]
    contributions = [
        {
            "feature":       _feature_cols[i],
            "label":         FEATURE_LABELS.get(_feature_cols[i], _feature_cols[i]),
            "shap_value":    round(float(sv[i]), 4),
            "feature_value": round(float(x_orig[i]), 4),
            "direction":     "aggrave" if sv[i] > 0 else "ameliore",
        }
        for i in indices
    ]

    base = _explainer.expected_value
    return {
        "client_id":    client_id,
        "base_value":   round(float(base[1] if hasattr(base, "__len__") else base), 4),
        "top_features": contributions,
    }
