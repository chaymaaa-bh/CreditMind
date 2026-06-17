# =============================================================


#  CreditMind — M5 : Scoring Ensemble & MLOps
#
#  INSTRUCTIONS :
#  1. Place ce fichier dans :
#     C:\Users\Rahma Moalla\Desktop\CreditMind\
#  2. Assure-toi que ces fichiers existent :
#     - dataset_combined_real_synth.csv   (M1)
#     - m2_gnn_scores.csv                 (M2)
#     - m3_forecasts_individual.csv       (M3)
#     - m4_anomaly_scores.csv             (M4)
#  3. Installe les dépendances :
#     pip install xgboost lightgbm scikit-learn mlflow evidently
#     pip install autogluon.tabular        (optionnel — lourd)
#     pip install dvc                      (optionnel)
#     pip install pandas numpy openpyxl matplotlib shap
#  4. Lance :
#     python m5_scoring_ensemble.py
#
#  Résultats produits :
#     m5_scores_finaux.csv         → score solvabilité 0-100 par client
#     m5_model_metrics.csv         → métriques AUC-ROC, F1, MAPE
#     m5_shap_importance.csv       → importance des features (SHAP)
#     m5_drift_report.html         → rapport de drift Evidently
#     m5_results_summary.xlsx      → rapport Excel complet
#     mlruns/                      → expériences MLflow (dossier local)
# =============================================================

import pandas as pd
import numpy as np
import os, warnings, json, time, hashlib
from datetime import datetime
warnings.filterwarnings('ignore')

# ─── CHEMINS ──────────────────────────────────────────────────────────────────
INPUT_COMBINED  = r'dataset_combined_real_synth.csv'
INPUT_M2        = r'm2_gnn_scores.csv'
INPUT_M3        = r'm3_forecasts_individual.csv'
INPUT_M4        = r'm4_anomaly_scores.csv'

OUTPUT_SCORES   = r'm5_scores_finaux.csv'
OUTPUT_METRICS  = r'm5_model_metrics.csv'
OUTPUT_SHAP     = r'm5_shap_importance.csv'
OUTPUT_DRIFT    = r'm5_drift_report.html'
OUTPUT_EXCEL    = r'm5_results_summary.xlsx'
MLFLOW_DIR      = r'mlruns'
DVC_HASH_FILE   = r'm5_data_hash.json'

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────
TEST_SIZE       = 0.20
VAL_SIZE        = 0.10
RANDOM_SEED     = 42
XGB_PARAMS = {
    'n_estimators':     500,
    'max_depth':        6,
    'learning_rate':    0.05,
    'subsample':        0.8,
    'colsample_bytree': 0.8,
    'use_label_encoder': False,
    'eval_metric':      'logloss',
    'random_state':     RANDOM_SEED,
    'n_jobs':           -1,
}
LGB_PARAMS = {
    'n_estimators':   500,
    'max_depth':      6,
    'learning_rate':  0.05,
    'subsample':      0.8,
    'colsample_bytree': 0.8,
    'random_state':   RANDOM_SEED,
    'n_jobs':         -1,
    'verbose':        -1,
}
np.random.seed(RANDOM_SEED)

print("=" * 65)
print("  CreditMind — M5 : Scoring Ensemble & MLOps")
print("=" * 65)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Chargement et fusion des données (M1 + M2 + M3 + M4)
# ══════════════════════════════════════════════════════════════════════
print("\n[1/9] Chargement et fusion des données...")

# ── M1 : dataset de base ──────────────────────────────────────────────
if not os.path.exists(INPUT_COMBINED):
    print(f"  ERREUR : {INPUT_COMBINED} introuvable. Lance m1_synthetic_data.py d'abord.")
    exit()

df_base = pd.read_csv(INPUT_COMBINED).reset_index(drop=True)
df_base['client_id'] = df_base.index
print(f"  M1 (base)   : {len(df_base)} clients · {df_base.shape[1]} colonnes")

# ── M2 : scores GNN ──────────────────────────────────────────────────
if os.path.exists(INPUT_M2):
    df_m2 = pd.read_csv(INPUT_M2)
    # Harmonise column names from m2_gnn_scores.csv → internal names
    df_m2 = df_m2.rename(columns={
        'client_index':   'client_id',
        'score_gnn':      'gnn_risk_score',
        'score_contagion':'contagion_score',
        'score_final_m2': 'gnn_final_score',
        'label_reel':     'gnn_risk_label',
    })
    if 'client_id' not in df_m2.columns:
        df_m2['client_id'] = df_m2.index
    # M2 scores are 0-100 → normalize to 0-1
    for col in ['gnn_risk_score', 'contagion_score', 'gnn_final_score']:
        if col in df_m2.columns:
            df_m2[col] = df_m2[col] / 100.0
    m2_cols = [c for c in ['gnn_risk_score', 'contagion_score', 'gnn_final_score', 'gnn_risk_label']
               if c in df_m2.columns]
    print(f"  M2 (GNN)    : {len(df_m2)} lignes · colonnes : {m2_cols}")
else:
    print("  M2 non disponible → simulation des scores GNN")
    df_m2 = pd.DataFrame({
        'client_id':      df_base['client_id'],
        'gnn_risk_score': np.random.beta(2, 8, len(df_base)),
        'contagion_score':np.random.beta(1, 9, len(df_base)),
        'gnn_final_score':np.random.beta(2, 8, len(df_base)),
        'gnn_risk_label': df_base.get('label_risque', pd.Series(np.zeros(len(df_base)))).values,
    })
    m2_cols = ['gnn_risk_score', 'contagion_score', 'gnn_final_score', 'gnn_risk_label']

# ── M3 : prévisions (horizon 1 et 3 mois) ─────────────────────────────
if os.path.exists(INPUT_M3):
    df_m3_raw = pd.read_csv(INPUT_M3)
    # Pivoter : une ligne par client avec les prévisions h=1 et h=3
    m3_h1 = df_m3_raw[df_m3_raw['horizon_mois'] == 1][
        ['client_id', 'montant_regle_pred', 'retard_pred', 'risque_tendance']
    ].rename(columns={
        'montant_regle_pred': 'm3_montant_h1',
        'retard_pred':        'm3_retard_h1',
        'risque_tendance':    'm3_tendance_h1',
    })
    m3_h3 = df_m3_raw[df_m3_raw['horizon_mois'] == 3][
        ['client_id', 'montant_regle_pred', 'retard_pred']
    ].rename(columns={
        'montant_regle_pred': 'm3_montant_h3',
        'retard_pred':        'm3_retard_h3',
    })
    df_m3 = m3_h1.merge(m3_h3, on='client_id', how='outer')
    print(f"  M3 (forecast): {len(df_m3)} clients · {df_m3.shape[1]} colonnes")
else:
    print("  M3 non disponible → simulation des prévisions")
    n = len(df_base)
    label = df_base.get('label_risque', pd.Series(np.zeros(n))).values
    df_m3 = pd.DataFrame({
        'client_id':      df_base['client_id'],
        'm3_montant_h1':  np.random.normal(10000, 3000, n).clip(0),
        'm3_retard_h1':   np.abs(np.random.normal(5, 8, n) + label * 15),
        'm3_tendance_h1': np.random.normal(0, 0.1, n) + label * 0.15,
        'm3_montant_h3':  np.random.normal(9500, 4000, n).clip(0),
        'm3_retard_h3':   np.abs(np.random.normal(6, 10, n) + label * 20),
    })

# ── M4 : scores d'anomalie ────────────────────────────────────────────
if os.path.exists(INPUT_M4):
    df_m4 = pd.read_csv(INPUT_M4)
    if 'client_id' not in df_m4.columns:
        df_m4['client_id'] = df_m4.index
    m4_cols = [c for c in [
        'score_anomalie_final', 'score_anomalie_if',
        'score_anomalie_lstm', 'pred_ensemble'
    ] if c in df_m4.columns]
    print(f"  M4 (anomaly): {len(df_m4)} lignes · colonnes : {m4_cols}")
else:
    print("  M4 non disponible → simulation des scores d'anomalie")
    n = len(df_base)
    label = df_base.get('label_risque', pd.Series(np.zeros(n))).values
    df_m4 = pd.DataFrame({
        'client_id':            df_base['client_id'],
        'score_anomalie_final': np.clip(np.random.beta(1, 9, n) + label * 0.4, 0, 1),
        'score_anomalie_if':    np.clip(np.random.beta(1, 9, n) + label * 0.3, 0, 1),
        'score_anomalie_lstm':  np.clip(np.random.beta(1, 9, n) + label * 0.35, 0, 1),
        'pred_ensemble':        label,
    })
    m4_cols = ['score_anomalie_final', 'score_anomalie_if', 'score_anomalie_lstm', 'pred_ensemble']

# ── Fusion complète ────────────────────────────────────────────────────
BASE_COLS = [
    'client_id', 'label_risque',
    'nb_factures', 'montant_ttc_moyen', 'montant_ttc_std',
    'retard_moyen_jours', 'retard_max_jours', 'taux_retard',
    'nb_reglements', 'montant_reg_moyen', 'ratio_encaissement',
    'solde_restant', 'jours_depuis_derniere_fac',
    'gouvernorat_code', 'nature_client_code', 'mode_paiement_code',
]
base_available = [c for c in BASE_COLS if c in df_base.columns]
df = df_base[base_available].copy()

df = df.merge(df_m2[['client_id'] + m2_cols],  on='client_id', how='left')
df = df.merge(df_m3, on='client_id', how='left')
df = df.merge(df_m4[['client_id'] + m4_cols],  on='client_id', how='left')

# Remplir les NaN
for col in df.select_dtypes(include=[np.number]).columns:
    df[col] = df[col].fillna(df[col].median())

print(f"\n  Dataset fusionné : {df.shape[0]} clients · {df.shape[1]} colonnes")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Feature engineering M5
# ══════════════════════════════════════════════════════════════════════
print("\n[2/9] Feature engineering M5...")

# Features composites enrichies
if 'gnn_risk_score' in df.columns and 'score_anomalie_final' in df.columns:
    df['risk_network_x_anomaly'] = df['gnn_risk_score'] * df['score_anomalie_final']

if 'gnn_final_score' in df.columns and 'score_anomalie_final' in df.columns:
    df['gnn_x_anomaly_final'] = df['gnn_final_score'] * df['score_anomalie_final']

if 'contagion_score' in df.columns and 'm3_tendance_h1' in df.columns:
    df['contagion_x_tendance']   = df['contagion_score'] * df['m3_tendance_h1'].clip(lower=0)

if 'm3_retard_h3' in df.columns and 'retard_moyen_jours' in df.columns:
    df['delta_retard_forecast']  = (df['m3_retard_h3'] - df['retard_moyen_jours']).clip(lower=0)

if 'm3_retard_h1' in df.columns and 'retard_moyen_jours' in df.columns:
    df['retard_acceleration']    = df['m3_retard_h1'] - df['retard_moyen_jours']

if 'taux_retard' in df.columns and 'gnn_risk_score' in df.columns:
    df['risk_composite']         = 0.4 * df['taux_retard'] + 0.3 * df['gnn_risk_score'] + \
                                   0.3 * df.get('score_anomalie_final', 0)

# Ratio encours prévu vs actuel
if 'm3_montant_h1' in df.columns and 'montant_ttc_moyen' in df.columns:
    df['encours_ratio_forecast'] = df['m3_montant_h1'] / (df['montant_ttc_moyen'] + 1e-6)

# Features finales pour le modèle
EXCLUDE_COLS = ['client_id', 'label_risque']
FEATURE_COLS = [c for c in df.columns if c not in EXCLUDE_COLS
                and df[c].dtype in [np.float64, np.int64, np.float32, np.int32]]

TARGET_COL   = 'label_risque'
X = df[FEATURE_COLS].values
y = df[TARGET_COL].values if TARGET_COL in df.columns else np.zeros(len(df))

print(f"  Features totales   : {len(FEATURE_COLS)}")
print(f"  Clients (total)    : {len(X)}")
print(f"  Label risque=1     : {int(y.sum())} ({y.mean():.1%})")
print(f"  Features composites ajoutées :")
composite = [c for c in FEATURE_COLS if c in [
    'risk_network_x_anomaly','contagion_x_tendance','delta_retard_forecast',
    'retard_acceleration','risk_composite','encours_ratio_forecast']]
for c in composite:
    print(f"    + {c}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Découpage Train / Validation / Test + hash DVC
# ══════════════════════════════════════════════════════════════════════
print("\n[3/9] Découpage Train/Val/Test + versioning données...")

from sklearn.model_selection import train_test_split

X_temp, X_test, y_temp, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y if y.sum() > 1 else None
)
val_ratio = VAL_SIZE / (1 - TEST_SIZE)
X_train, X_val, y_train, y_val = train_test_split(
    X_temp, y_temp, test_size=val_ratio, random_state=RANDOM_SEED,
    stratify=y_temp if y_temp.sum() > 1 else None
)

print(f"  Train      : {len(X_train)} clients ({len(X_train)/len(X):.0%})")
print(f"  Validation : {len(X_val)} clients ({len(X_val)/len(X):.0%})")
print(f"  Test       : {len(X_test)} clients ({len(X_test)/len(X):.0%})")

# ── DVC : hash du dataset pour versioning ─────────────────────────────
print("\n  Versioning données (DVC)...")
data_str     = pd.DataFrame(X, columns=FEATURE_COLS).to_csv(index=False).encode()
data_hash    = hashlib.md5(data_str).hexdigest()
dvc_metadata = {
    'run_timestamp':   datetime.now().isoformat(),
    'dataset_hash_md5': data_hash,
    'n_clients':       int(len(X)),
    'n_features':      int(len(FEATURE_COLS)),
    'features':        FEATURE_COLS,
    'train_size':      int(len(X_train)),
    'val_size':        int(len(X_val)),
    'test_size':       int(len(X_test)),
    'sources': {
        'M1': INPUT_COMBINED,
        'M2': INPUT_M2,
        'M3': INPUT_M3,
        'M4': INPUT_M4,
    }
}
with open(DVC_HASH_FILE, 'w') as f:
    json.dump(dvc_metadata, f, indent=2)
print(f"  Hash dataset MD5   : {data_hash[:12]}...")
print(f"  Métadonnées sauvegardées : {DVC_HASH_FILE}")

# Normalisation
from sklearn.preprocessing import StandardScaler
scaler_m5 = StandardScaler()
X_train_s = scaler_m5.fit_transform(X_train)
X_val_s   = scaler_m5.transform(X_val)
X_test_s  = scaler_m5.transform(X_test)
X_all_s   = scaler_m5.transform(X)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — MLflow : initialisation du tracking
# ══════════════════════════════════════════════════════════════════════
print("\n[4/9] Initialisation MLflow...")

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    os.makedirs(MLFLOW_DIR, exist_ok=True)
    mlflow.set_tracking_uri(f"file:///{os.path.abspath(MLFLOW_DIR)}")
    mlflow.set_experiment("CreditMind_M5_ScoringEnsemble")
    mlflow_available = True
    print(f"  ✓ MLflow initialisé → {MLFLOW_DIR}/")
    print(f"    Pour voir l'UI : mlflow ui --backend-store-uri {os.path.abspath(MLFLOW_DIR)}")
except ImportError:
    mlflow_available = False
    print("  MLflow non disponible — pip install mlflow")

def mlflow_log(params, metrics, tags=None):
    """Log vers MLflow si disponible."""
    if not mlflow_available:
        return
    try:
        if params:  mlflow.log_params(params)
        if metrics: mlflow.log_metrics(metrics)
        if tags:
            for k, v in tags.items():
                mlflow.set_tag(k, v)
    except Exception as e:
        print(f"  MLflow log erreur : {e}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Entraînement des modèles de base
# ══════════════════════════════════════════════════════════════════════
print("\n[5/9] Entraînement des modèles de base...")

from sklearn.metrics import (roc_auc_score, f1_score, precision_score,
                              recall_score, accuracy_score, log_loss)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

trained_models = {}
model_probs    = {}   # probabilités sur X_test
model_metrics  = {}

# ─────────────────────────────────────────────────────────────────────
def evaluate_model(name, y_true, y_prob, y_pred=None):
    """Calcule et affiche les métriques d'un modèle."""
    if y_pred is None:
        y_pred = (y_prob >= 0.5).astype(int)
    try:
        auc  = roc_auc_score(y_true, y_prob)   if y_true.sum() > 0 else 0.5
        f1   = f1_score(y_true, y_pred,        zero_division=0)
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec  = recall_score(y_true, y_pred,    zero_division=0)
        acc  = accuracy_score(y_true, y_pred)
        ll   = log_loss(y_true, y_prob)        if y_true.sum() > 0 else 1.0
    except Exception:
        auc, f1, prec, rec, acc, ll = 0.5, 0.0, 0.0, 0.0, 0.5, 1.0

    print(f"  {name:<22} AUC={auc:.4f}  F1={f1:.4f}  Prec={prec:.4f}  Rec={rec:.4f}")
    return {'auc': auc, 'f1': f1, 'precision': prec, 'recall': rec,
            'accuracy': acc, 'log_loss': ll}

# ── Modèle 1 : XGBoost ────────────────────────────────────────────────
print("\n  ► XGBoost...")
try:
    import xgboost as xgb

    run_name_xgb = f"XGBoost_{datetime.now().strftime('%H%M%S')}"
    if mlflow_available:
        mlflow.start_run(run_name=run_name_xgb)

    t0 = time.time()
    xgb_model = xgb.XGBClassifier(**XGB_PARAMS)
    xgb_model.fit(
        X_train_s, y_train,
        eval_set=[(X_val_s, y_val)],
        verbose=False,
    )
    elapsed_xgb = time.time() - t0

    xgb_prob_test = xgb_model.predict_proba(X_test_s)[:, 1]
    xgb_prob_all  = xgb_model.predict_proba(X_all_s)[:, 1]
    m = evaluate_model('XGBoost', y_test, xgb_prob_test)
    model_metrics['XGBoost'] = {**m, 'train_time_s': round(elapsed_xgb, 2)}
    model_probs['XGBoost']   = xgb_prob_all
    trained_models['XGBoost'] = xgb_model

    mlflow_log(
        params  = {**{f'xgb_{k}': v for k, v in XGB_PARAMS.items() if not isinstance(v, bool)}},
        metrics = {f'test_{k}': v for k, v in m.items()},
        tags    = {'module': 'M5', 'model': 'XGBoost', 'dataset_hash': data_hash[:8]}
    )
    if mlflow_available:
        mlflow.xgboost.log_model(xgb_model, "xgboost_model")
        mlflow.end_run()

    print(f"    Entraîné en {elapsed_xgb:.1f}s")

except ImportError:
    print("  XGBoost non disponible — pip install xgboost")
    if mlflow_available:
        try: mlflow.end_run()
        except: pass

# ── Modèle 2 : LightGBM ───────────────────────────────────────────────
print("\n  ► LightGBM...")
try:
    import lightgbm as lgb

    run_name_lgb = f"LightGBM_{datetime.now().strftime('%H%M%S')}"
    if mlflow_available:
        mlflow.start_run(run_name=run_name_lgb)

    t0 = time.time()
    lgb_model = lgb.LGBMClassifier(**LGB_PARAMS)
    lgb_model.fit(
        X_train_s, y_train,
        eval_set=[(X_val_s, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)]
    )
    elapsed_lgb = time.time() - t0

    lgb_prob_test = lgb_model.predict_proba(X_test_s)[:, 1]
    lgb_prob_all  = lgb_model.predict_proba(X_all_s)[:, 1]
    m = evaluate_model('LightGBM', y_test, lgb_prob_test)
    model_metrics['LightGBM'] = {**m, 'train_time_s': round(elapsed_lgb, 2)}
    model_probs['LightGBM']   = lgb_prob_all
    trained_models['LightGBM'] = lgb_model

    mlflow_log(
        params  = {**{f'lgb_{k}': v for k, v in LGB_PARAMS.items() if not isinstance(v, bool)}},
        metrics = {f'test_{k}': v for k, v in m.items()},
        tags    = {'module': 'M5', 'model': 'LightGBM', 'dataset_hash': data_hash[:8]}
    )
    if mlflow_available:
        mlflow.sklearn.log_model(lgb_model, "lightgbm_model")
        mlflow.end_run()

    print(f"    Entraîné en {elapsed_lgb:.1f}s")

except ImportError:
    print("  LightGBM non disponible — pip install lightgbm")
    if mlflow_available:
        try: mlflow.end_run()
        except: pass

# ── Modèle 3 : AutoGluon (optionnel) ──────────────────────────────────
print("\n  ► AutoGluon (optionnel)...")
autogluon_prob_all = None
try:
    from autogluon.tabular import TabularPredictor

    run_name_ag = f"AutoGluon_{datetime.now().strftime('%H%M%S')}"
    if mlflow_available:
        mlflow.start_run(run_name=run_name_ag)

    df_train_ag = pd.DataFrame(X_train_s, columns=FEATURE_COLS)
    df_train_ag['label_risque'] = y_train
    df_test_ag  = pd.DataFrame(X_test_s,  columns=FEATURE_COLS)
    df_all_ag   = pd.DataFrame(X_all_s,   columns=FEATURE_COLS)

    t0 = time.time()
    ag_predictor = TabularPredictor(
        label='label_risque',
        eval_metric='roc_auc',
        path='autogluon_models/',
        verbosity=0,
    ).fit(
        df_train_ag,
        time_limit=120,       # 2 minutes max
        presets='medium_quality',
    )
    elapsed_ag = time.time() - t0

    ag_prob_test = ag_predictor.predict_proba(df_test_ag)[1].values
    autogluon_prob_all = ag_predictor.predict_proba(df_all_ag)[1].values
    m = evaluate_model('AutoGluon', y_test, ag_prob_test)
    model_metrics['AutoGluon'] = {**m, 'train_time_s': round(elapsed_ag, 2)}
    model_probs['AutoGluon']   = autogluon_prob_all
    trained_models['AutoGluon'] = ag_predictor

    mlflow_log(
        params  = {'ag_time_limit': 120, 'ag_preset': 'medium_quality'},
        metrics = {f'test_{k}': v for k, v in m.items()},
        tags    = {'module': 'M5', 'model': 'AutoGluon', 'dataset_hash': data_hash[:8]}
    )
    if mlflow_available:
        mlflow.end_run()

    print(f"    AutoGluon entraîné en {elapsed_ag:.1f}s")

except ImportError:
    print("  AutoGluon non disponible (normal) — pip install autogluon.tabular")
    if mlflow_available:
        try: mlflow.end_run()
        except: pass
except Exception as e:
    print(f"  AutoGluon erreur : {e}")
    if mlflow_available:
        try: mlflow.end_run()
        except: pass

# ── Modèle de référence : Logistic Regression ─────────────────────────
print("\n  ► Logistic Regression (référence)...")
lr_model = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)
lr_model.fit(X_train_s, y_train)
lr_prob_test = lr_model.predict_proba(X_test_s)[:, 1]
lr_prob_all  = lr_model.predict_proba(X_all_s)[:, 1]
m = evaluate_model('LogisticRegression', y_test, lr_prob_test)
model_metrics['LogisticRegression'] = {**m, 'train_time_s': 0.0}
model_probs['LogisticRegression']   = lr_prob_all
trained_models['LogisticRegression'] = lr_model

# ── Modèle 4 : Random Forest ──────────────────────────────────────────
print("\n  ► Random Forest...")
from sklearn.ensemble import RandomForestClassifier
t0 = time.time()
n_pos_train = int(y_train.sum())
n_neg_train = len(y_train) - n_pos_train
rf_model = RandomForestClassifier(
    n_estimators=300,
    max_depth=8,
    class_weight='balanced',
    random_state=RANDOM_SEED,
    n_jobs=-1,
)
rf_model.fit(X_train_s, y_train)
elapsed_rf   = time.time() - t0
rf_prob_test = rf_model.predict_proba(X_test_s)[:, 1]
rf_prob_all  = rf_model.predict_proba(X_all_s)[:, 1]
m = evaluate_model('RandomForest', y_test, rf_prob_test)
model_metrics['RandomForest'] = {**m, 'train_time_s': round(elapsed_rf, 2)}
model_probs['RandomForest']   = rf_prob_all
trained_models['RandomForest'] = rf_model
print(f"    Entraîné en {elapsed_rf:.1f}s")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Méta-modèle Stacking + calibration
# ══════════════════════════════════════════════════════════════════════
print("\n[6/9] Méta-modèle Stacking + calibration Platt...")

if len(model_probs) >= 2:
    # Base models used in stacking (no AutoGluon — different API)
    meta_models = [k for k in ['XGBoost', 'LightGBM', 'RandomForest', 'LogisticRegression']
                   if k in model_probs]

    # Build meta-train from val set predictions (no data leakage)
    meta_train_cols = [trained_models[name].predict_proba(X_val_s)[:, 1] for name in meta_models]
    X_meta_train = np.column_stack(meta_train_cols)
    y_meta_train = y_val

    # Meta-model: LR stacked on val probabilities
    meta_model = LogisticRegression(C=1.0, max_iter=500, random_state=RANDOM_SEED)
    meta_model.fit(X_meta_train, y_meta_train)

    # Build meta-test from test set predictions
    meta_test_cols = [trained_models[name].predict_proba(X_test_s)[:, 1] for name in meta_models]
    X_meta_test    = np.column_stack(meta_test_cols)
    ensemble_prob_test = meta_model.predict_proba(X_meta_test)[:, 1]

    # All-clients predictions for final scoring
    meta_all_cols = [model_probs[name] for name in meta_models]
    X_meta_all    = np.column_stack(meta_all_cols)
    ensemble_prob_all = meta_model.predict_proba(X_meta_all)[:, 1]

    # AUC-based weights for transparency report
    aucs    = [model_metrics[name]['auc'] for name in meta_models]
    weights = np.array(aucs) / sum(aucs)
    print(f"  Modèles combinés : {meta_models}")
    print(f"  Poids (par AUC)  : {dict(zip(meta_models, [round(w,3) for w in weights]))}")

    m_ens = evaluate_model('Ensemble (stacking)', y_test, ensemble_prob_test)
    model_metrics['Ensemble'] = {**m_ens, 'train_time_s': 0.0}

    # ── Calibration Platt Scaling ──────────────────────────────────────
    lr_calib = LogisticRegression(C=1.0, max_iter=500, random_state=RANDOM_SEED)
    val_ensemble = meta_model.predict_proba(X_meta_train)[:, 1]
    lr_calib.fit(val_ensemble.reshape(-1, 1), y_val)

    calib_prob_all  = lr_calib.predict_proba(ensemble_prob_all.reshape(-1, 1))[:, 1]
    calib_prob_test = lr_calib.predict_proba(ensemble_prob_test.reshape(-1, 1))[:, 1]

    print(f"\n  ✓ Calibration Platt appliquée")
    print(f"  Plage probabilités avant calibration : [{ensemble_prob_all.min():.3f}, {ensemble_prob_all.max():.3f}]")
    print(f"  Plage probabilités après calibration : [{calib_prob_all.min():.3f}, {calib_prob_all.max():.3f}]")

    m_calib = evaluate_model('Ensemble calibré', y_test, calib_prob_test)
    model_metrics['Ensemble_calibre'] = {**m_calib, 'train_time_s': 0.0}

    # MLflow : run final ensemble
    if mlflow_available:
        mlflow.start_run(run_name=f"Ensemble_final_{datetime.now().strftime('%H%M%S')}")
        mlflow_log(
            params  = {'meta_models': str(meta_models), 'calibration': 'PlattScaling'},
            metrics = {f'test_{k}': v for k, v in m_calib.items()},
            tags    = {'module': 'M5', 'model': 'Ensemble_calibre', 'stage': 'production'}
        )
        mlflow.end_run()

    final_prob = calib_prob_all

else:
    print("  Un seul modèle disponible — pas de stacking")
    final_prob = list(model_probs.values())[0]
    model_metrics['Ensemble_calibre'] = model_metrics[list(model_metrics.keys())[0]]

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Score de solvabilité 0-100 + alertes
# ══════════════════════════════════════════════════════════════════════
print("\n[7/9] Calcul du score de solvabilité 0-100...")

# Transformation : probabilité de défaut → score de solvabilité
# Score = 100 × (1 − prob_défaut)  avec mise à l'échelle [5, 95]
score_raw  = 100 * (1 - final_prob)
score_0100 = np.clip(5 + 90 * (score_raw - score_raw.min()) /
                     (score_raw.max() - score_raw.min() + 1e-8), 5, 95)
score_0100 = np.round(score_0100, 1)

def score_to_alert(score, prob_defaut):
    """Convertit le score en niveau d'alerte."""
    if score < 20 or prob_defaut > 0.75:  return 'ROUGE'
    elif score < 40 or prob_defaut > 0.50: return 'ORANGE'
    elif score < 60 or prob_defaut > 0.30: return 'JAUNE'
    else:                                   return 'VERT'

def score_to_class(score):
    """Classe de risque textuelle."""
    if score < 20:  return 'RISQUE_ELEVE'
    elif score < 40: return 'RISQUE_MOYEN'
    elif score < 60: return 'SURVEILLE'
    else:            return 'SAIN'

# Construire le dataframe de résultats finaux
df_scores = df[['client_id', 'label_risque']].copy()
df_scores['prob_defaut']        = np.round(final_prob, 4)
df_scores['score_solvabilite']  = score_0100
df_scores['classe_risque']      = [score_to_class(s) for s in score_0100]
df_scores['alerte']             = [score_to_alert(s, p)
                                    for s, p in zip(score_0100, final_prob)]

# Ajouter les scores composants pour tracabilité
if 'XGBoost' in model_probs:
    df_scores['prob_xgb']   = np.round(model_probs['XGBoost'], 4)
if 'LightGBM' in model_probs:
    df_scores['prob_lgb']   = np.round(model_probs['LightGBM'], 4)
if 'gnn_risk_score' in df.columns:
    df_scores['gnn_risk_score'] = df['gnn_risk_score'].values
if 'score_anomalie_final' in df.columns:
    df_scores['score_anomalie'] = df['score_anomalie_final'].values
if 'm3_tendance_h1' in df.columns:
    df_scores['tendance_m3'] = df['m3_tendance_h1'].values

# Distribution des scores
print(f"\n  Score solvabilité 0-100 :")
print(f"    Min    : {score_0100.min():.1f}")
print(f"    Max    : {score_0100.max():.1f}")
print(f"    Moyen  : {score_0100.mean():.1f}")
print(f"    Médiane: {np.median(score_0100):.1f}")

alert_dist = df_scores['alerte'].value_counts()
print(f"\n  Distribution des alertes finales :")
for level in ['ROUGE', 'ORANGE', 'JAUNE', 'VERT']:
    n   = alert_dist.get(level, 0)
    pct = n / len(df_scores) * 100
    bar = '█' * int(pct / 2)
    print(f"    {level:<8} : {n:6d} clients ({pct:5.1f}%)  {bar}")

# Vérification seuil cible AUC-ROC
auc_final = model_metrics.get('Ensemble_calibre', {}).get('auc', 0)
print(f"\n  ┌─────────────────────────────────────────────────┐")
print(f"  │  AUC-ROC Ensemble final : {auc_final:.4f}              │")
print(f"  │  Seuil cible            : > 0.90                │")
print(f"  │  Statut : {'✓ ATTEINT' if auc_final >= 0.90 else '✗ À améliorer (données simulées)'}                      │")
print(f"  └─────────────────────────────────────────────────┘")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 8 — SHAP : importance des features
# ══════════════════════════════════════════════════════════════════════
print("\n[8/9] Calcul SHAP (importance des features)...")

df_shap_importance = pd.DataFrame()
try:
    import shap

    # SHAP sur XGBoost (plus rapide)
    if 'XGBoost' in trained_models:
        print("  Calcul SHAP sur XGBoost...")
        explainer  = shap.TreeExplainer(trained_models['XGBoost'])
        # Utiliser un sous-échantillon pour la rapidité
        n_shap     = min(500, len(X_all_s))
        idx_shap   = np.random.choice(len(X_all_s), n_shap, replace=False)
        shap_vals  = explainer.shap_values(X_all_s[idx_shap])

        # Importance globale (valeur absolue moyenne)
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1]  # classe 1 (risque)

        mean_abs_shap = np.abs(shap_vals).mean(axis=0)
        df_shap_importance = pd.DataFrame({
            'feature':        FEATURE_COLS,
            'shap_importance': mean_abs_shap,
        }).sort_values('shap_importance', ascending=False)

        print(f"\n  Top 10 features par importance SHAP :")
        print(f"  {'Feature':<30} {'SHAP importance':>16}")
        print(f"  {'-'*48}")
        for _, row in df_shap_importance.head(10).iterrows():
            bar = '▓' * int(row['shap_importance'] / mean_abs_shap.max() * 20)
            print(f"  {row['feature']:<30} {row['shap_importance']:>10.4f}  {bar}")

        df_shap_importance.to_csv(OUTPUT_SHAP, index=False)
        print(f"\n  ✓ SHAP importance sauvegardée : {OUTPUT_SHAP}")

        # Log SHAP dans MLflow
        if mlflow_available:
            mlflow.start_run(run_name=f"SHAP_{datetime.now().strftime('%H%M%S')}")
            mlflow.log_artifact(OUTPUT_SHAP, "shap")
            top5 = df_shap_importance.head(5)
            for _, r in top5.iterrows():
                mlflow.log_metric(f"shap_{r['feature'][:20]}", round(r['shap_importance'], 4))
            mlflow.end_run()

except ImportError:
    print("  SHAP non disponible — pip install shap")
    # Fallback : importance des features XGBoost native
    if 'XGBoost' in trained_models:
        xgb_imp = trained_models['XGBoost'].feature_importances_
        df_shap_importance = pd.DataFrame({
            'feature':        FEATURE_COLS,
            'shap_importance': xgb_imp,
        }).sort_values('shap_importance', ascending=False)
        df_shap_importance.to_csv(OUTPUT_SHAP, index=False)
        print(f"  Importance XGBoost native sauvegardée : {OUTPUT_SHAP}")
    elif 'LightGBM' in trained_models:
        lgb_imp = trained_models['LightGBM'].feature_importances_
        df_shap_importance = pd.DataFrame({
            'feature':        FEATURE_COLS,
            'shap_importance': lgb_imp / lgb_imp.max(),
        }).sort_values('shap_importance', ascending=False)
        df_shap_importance.to_csv(OUTPUT_SHAP, index=False)
        print(f"  Importance LightGBM native sauvegardée : {OUTPUT_SHAP}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 9 — Evidently : drift monitoring + sauvegarde
# ══════════════════════════════════════════════════════════════════════
print("\n[9/9] Drift monitoring (Evidently) + sauvegarde...")

# ── Evidently ──────────────────────────────────────────────────────────
try:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
    from evidently import ColumnMapping

    print("  Evidently détecté — génération du rapport de drift...")

    # Référence = données d'entraînement, courante = données de test
    df_reference = pd.DataFrame(X_train_s[:500], columns=FEATURE_COLS)
    df_current   = pd.DataFrame(X_test_s[:200],  columns=FEATURE_COLS)
    df_reference['label_risque'] = y_train[:500]
    df_current['label_risque']   = y_test[:200]

    column_mapping = ColumnMapping(target='label_risque')

    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(
        reference_data=df_reference,
        current_data=df_current,
        column_mapping=column_mapping,
    )
    report.save_html(OUTPUT_DRIFT)
    print(f"  ✓ Rapport de drift sauvegardé : {OUTPUT_DRIFT}")

    # Log dans MLflow
    if mlflow_available:
        mlflow.start_run(run_name=f"Drift_{datetime.now().strftime('%H%M%S')}")
        mlflow.log_artifact(OUTPUT_DRIFT, "drift")
        mlflow.end_run()

except ImportError:
    print("  Evidently non disponible — pip install evidently")
    # Drift manuel simplifié
    print("  → Calcul du drift manuel (KS-test)...")
    from scipy import stats

    drift_records = []
    for col in FEATURE_COLS[:10]:  # top 10 features
        try:
            ref   = X_train_s[:, FEATURE_COLS.index(col)]
            curr  = X_test_s[:,  FEATURE_COLS.index(col)]
            ks_stat, ks_pval = stats.ks_2samp(ref, curr)
            drift_records.append({
                'feature':    col,
                'ks_stat':    round(ks_stat, 4),
                'ks_pval':    round(ks_pval, 4),
                'drift':      'OUI' if ks_pval < 0.05 else 'NON',
            })
        except Exception:
            pass

    df_drift = pd.DataFrame(drift_records)
    if len(df_drift) > 0:
        df_drift.to_csv('m5_drift_manual.csv', index=False)
        n_drift = (df_drift['drift'] == 'OUI').sum()
        print(f"  Features avec drift détecté : {n_drift}/{len(df_drift)}")

except Exception as e:
    print(f"  Evidently erreur : {e}")

# ── Sauvegarde des résultats ───────────────────────────────────────────
print("\n  Sauvegarde des fichiers...")

# CSV 1 : Scores finaux
df_scores.to_csv(OUTPUT_SCORES, index=False)
print(f"  ✓ {OUTPUT_SCORES}  ({len(df_scores)} clients)")

# CSV 2 : Métriques modèles
metrics_rows = []
for model_name, m in model_metrics.items():
    metrics_rows.append({
        'modele':       model_name,
        'auc_roc':      round(m.get('auc', 0), 4),
        'f1_score':     round(m.get('f1', 0), 4),
        'precision':    round(m.get('precision', 0), 4),
        'recall':       round(m.get('recall', 0), 4),
        'accuracy':     round(m.get('accuracy', 0), 4),
        'log_loss':     round(m.get('log_loss', 0), 4),
        'train_time_s': m.get('train_time_s', 0),
        'seuil_auc':    '> 0.90' if model_name == 'Ensemble_calibre' else '—',
        'statut':       '✓' if m.get('auc', 0) >= 0.90 else '✗',
    })
df_metrics_out = pd.DataFrame(metrics_rows)
df_metrics_out.to_csv(OUTPUT_METRICS, index=False)
print(f"  ✓ {OUTPUT_METRICS}")

# Excel rapport complet
try:
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:

        # Feuille 1 : Scores finaux
        df_scores.to_excel(writer, sheet_name='Scores_Solvabilite', index=False)

        # Feuille 2 : Alertes (ROUGE + ORANGE)
        df_alertes = df_scores[df_scores['alerte'].isin(['ROUGE','ORANGE'])]\
                     .sort_values('score_solvabilite')
        df_alertes.to_excel(writer, sheet_name='Alertes_Critiques', index=False)

        # Feuille 3 : Métriques modèles
        df_metrics_out.to_excel(writer, sheet_name='Metriques_Modeles', index=False)

        # Feuille 4 : Importance SHAP
        if len(df_shap_importance) > 0:
            df_shap_importance.to_excel(writer, sheet_name='SHAP_Importance', index=False)

        # Feuille 5 : Synthèse par classe de risque
        synthese = df_scores.groupby('classe_risque').agg(
            nb_clients        = ('client_id', 'count'),
            score_moyen       = ('score_solvabilite', 'mean'),
            prob_defaut_moyen = ('prob_defaut', 'mean'),
            clients_label_1   = ('label_risque', 'sum'),
        ).reset_index()
        synthese['score_moyen']       = synthese['score_moyen'].round(1)
        synthese['prob_defaut_moyen'] = synthese['prob_defaut_moyen'].round(3)
        synthese.to_excel(writer, sheet_name='Synthese_Classes', index=False)

        # Feuille 6 : DVC metadata
        pd.DataFrame([dvc_metadata]).to_excel(writer, sheet_name='DVC_Metadata', index=False)

    print(f"  ✓ {OUTPUT_EXCEL}  (6 feuilles)")
except Exception as e:
    print(f"  Rapport Excel erreur : {e}")

# ─── Résumé final ─────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RÉSUMÉ M5 — Scoring Ensemble & MLOps")
print("=" * 65)
print(f"\n  Modèles entraînés :")
for name, m in model_metrics.items():
    print(f"    {name:<25} AUC={m.get('auc',0):.4f}  F1={m.get('f1',0):.4f}")

print(f"\n  Score de solvabilité 0-100 :")
print(f"    Clients SAIN         (≥ 60) : {(score_0100 >= 60).sum():6d}")
print(f"    Clients SURVEILLÉS  (40-60) : {((score_0100 >= 40)&(score_0100 < 60)).sum():6d}")
print(f"    Clients RISQUE MOYEN(20-40) : {((score_0100 >= 20)&(score_0100 < 40)).sum():6d}")
print(f"    Clients RISQUE ÉLEVÉ (< 20) : {(score_0100 < 20).sum():6d}")

print(f"\n  MLOps :")
print(f"    MLflow tracking  : {'✓ actif' if mlflow_available else '✗ non disponible'}")
print(f"    DVC hash         : {data_hash[:12]}...")
print(f"    SHAP importance  : {'✓ calculée' if len(df_shap_importance) > 0 else '✗ non disponible'}")
print(f"    Drift monitoring : {'✓ rapport HTML' if os.path.exists(OUTPUT_DRIFT) else '✗ non disponible'}")

print(f"\n  Fichiers produits :")
for f in [OUTPUT_SCORES, OUTPUT_METRICS, OUTPUT_SHAP, OUTPUT_DRIFT, OUTPUT_EXCEL, DVC_HASH_FILE]:
    exists = os.path.exists(f)
    size   = os.path.getsize(f) // 1024 if exists else 0
    print(f"    {'✓' if exists else '✗'} {f}  ({size} Ko)")

print(f"\n  Prêt pour M6 (GraphRAG & LLM) et M8 (XAI & Dashboard)")
print("=" * 65)
