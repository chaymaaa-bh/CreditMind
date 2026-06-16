# =============================================================
#  CreditMind — M3 : Time Series Forecaster
#
#  INSTRUCTIONS :
#  1. Place ce fichier dans :
#     C:\Users\Rahma Moalla\Desktop\CreditMind\
#  2. Assure-toi que ces fichiers existent (produits par M1) :
#     - dataset_combined_real_synth.csv
#     - SolvAI_Dataset_Nettoye.xlsx
#  3. Installe les dépendances :
#     pip install neuralforecast pytorch-forecasting lightning pandas numpy scikit-learn openpyxl matplotlib
#  4. Lance :
#     python m3_time_series.py
#
#  Résultats produits :
#     m3_forecasts_individual.csv     → prévisions par client (1-6 mois)
#     m3_portfolio_forecast.csv       → prévisions agrégées portefeuille
#     m3_evaluation_metrics.csv       → MAPE par modèle et par horizon
#     m3_results_summary.xlsx         → rapport Excel complet avec alertes
# =============================================================

import pandas as pd
import numpy as np
import os, warnings, json
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# ─── CHEMINS ──────────────────────────────────────────────────────────────────
INPUT_COMBINED = r'dataset_combined_real_synth.csv'
INPUT_REAL     = r'SolvAI_Dataset_Nettoye.xlsx'
OUTPUT_INDIV   = r'm3_forecasts_individual.csv'
OUTPUT_PORTF   = r'm3_portfolio_forecast.csv'
OUTPUT_METRICS = r'm3_evaluation_metrics.csv'
OUTPUT_EXCEL   = r'm3_results_summary.xlsx'

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────
HORIZON        = 6       # mois de prévision
LOOKBACK       = 12      # mois d'historique utilisés en entrée
N_MONTHS       = 26      # mois d'historique disponibles (jan 2024 – fév 2026)
TRAIN_MONTHS   = 20      # mois d'entraînement
VAL_MONTHS     = 3       # mois de validation
TEST_MONTHS    = 3       # mois de test
RANDOM_SEED    = 42
np.random.seed(RANDOM_SEED)

print("=" * 65)
print("  CreditMind — M3 : Time Series Forecaster")
print("=" * 65)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Chargement des données
# ══════════════════════════════════════════════════════════════════════
print("\n[1/7] Chargement des données...")

if not os.path.exists(INPUT_COMBINED):
    print(f"  ERREUR : {INPUT_COMBINED} introuvable.")
    print("  Lance d'abord m1_synthetic_data.py pour générer ce fichier.")
    exit()

df_combined = pd.read_csv(INPUT_COMBINED)
print(f"  Dataset combiné : {df_combined.shape[0]} clients · {df_combined.shape[1]} colonnes")

# Charger l'historique transactionnel réel si disponible
has_real_history = False
if os.path.exists(INPUT_REAL):
    try:
        # Essai de lecture des feuilles de l'Excel
        xl = pd.ExcelFile(INPUT_REAL)
        print(f"  Feuilles disponibles dans l'Excel : {xl.sheet_names}")

        # Accept both 'factures' and 'factures_clean' sheet names
        factures_sheet  = next((s for s in xl.sheet_names if 'factures'   in s.lower()), None)
        reglements_sheet = next((s for s in xl.sheet_names if 'reglements' in s.lower()), None)
        if factures_sheet:
            df_factures   = pd.read_excel(INPUT_REAL, sheet_name=factures_sheet)
            has_real_history = True
            print(f"  Factures reelles : {len(df_factures)} lignes (feuille: {factures_sheet})")
        if reglements_sheet:
            df_reglements = pd.read_excel(INPUT_REAL, sheet_name=reglements_sheet)
            print(f"  Reglements reels : {len(df_reglements)} lignes (feuille: {reglements_sheet})")
        if not has_real_history:
            print("  → Feuilles 'factures'/'reglements' non trouvées — simulation de l'historique activée")
    except Exception as e:
        print(f"  → Impossible de lire l'Excel ({e}) — simulation activée")
else:
    print(f"  → {INPUT_REAL} non trouvé — simulation de l'historique mensuel activée")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Construction des séries temporelles mensuelles
# ══════════════════════════════════════════════════════════════════════
print("\n[2/7] Construction des séries temporelles mensuelles...")

# Générer les dates mensuelles (jan 2024 → fév 2026)
start_date = pd.Timestamp('2024-01-01')
dates      = [start_date + pd.DateOffset(months=i) for i in range(N_MONTHS)]
date_strs  = [d.strftime('%Y-%m') for d in dates]

# Sélectionner un échantillon représentatif pour les prévisions individuelles
# (pour éviter des temps de calcul trop longs sur 21 637 clients)
N_CLIENTS_SAMPLE = min(500, len(df_combined))
df_sample = df_combined.sample(n=N_CLIENTS_SAMPLE, random_state=RANDOM_SEED).copy()
df_sample['client_id'] = range(N_CLIENTS_SAMPLE)

print(f"  Clients sélectionnés pour prévision individuelle : {N_CLIENTS_SAMPLE}")
print(f"  Horizon de prévision : {HORIZON} mois")
print(f"  Fenêtre d'entrée (look-back) : {LOOKBACK} mois")

def simulate_monthly_series(row, n_months=N_MONTHS, seed=None):
    """
    Simule une série temporelle mensuelle réaliste pour un client
    à partir de ses features statiques agrégées.
    En production, cette fonction serait remplacée par l'agrégation
    des vraies factures et règlements mensuels.
    """
    if seed is not None:
        np.random.seed(seed)

    # Paramètres de la série fondés sur les features du client
    montant_base   = float(row.get('montant_ttc_moyen', 10000))
    retard_base    = float(row.get('retard_moyen_jours', 5))
    ratio_base     = float(row.get('ratio_encaissement', 0.95))
    taux_retard    = float(row.get('taux_retard', 0.05))
    label_risque   = int(row.get('label_risque', 0))

    # Tendance (légère dégradation si client à risque)
    trend = np.linspace(0, -0.1 * label_risque, n_months)

    # Saisonnalité mensuelle (pic en mars et septembre — fins de trimestre)
    seasonality = 0.15 * np.sin(2 * np.pi * np.arange(n_months) / 12)

    # Bruit gaussien
    noise = np.random.normal(0, 0.08, n_months)

    # Série de montants réglés
    montant_regle = montant_base * (1 + trend + seasonality + noise)
    montant_regle = np.maximum(montant_regle, 0)

    # Série de retards (augmentation progressive si risque élevé)
    retard_trend  = label_risque * np.linspace(0, 15, n_months)
    retard_serie  = retard_base + retard_trend + np.random.normal(0, 3, n_months)
    retard_serie  = np.maximum(retard_serie, 0)

    # Ratio réglé/facturé
    ratio_serie   = ratio_base - label_risque * np.linspace(0, 0.1, n_months)
    ratio_serie   = np.clip(ratio_serie + np.random.normal(0, 0.03, n_months), 0, 1.2)

    # Encours estimé (cumulatif)
    encours_serie = montant_base * (1 - ratio_serie)
    encours_serie = np.maximum(encours_serie, 0)

    return {
        'montant_regle':  np.round(montant_regle, 2),
        'retard_moyen':   np.round(retard_serie, 1),
        'ratio_regle':    np.round(ratio_serie, 4),
        'encours':        np.round(encours_serie, 2),
    }

# Construire la table de séries temporelles
print("  Construction des séries temporelles (simulation)...")
ts_records = []

for idx, (_, row) in enumerate(df_sample.iterrows()):
    series = simulate_monthly_series(row, seed=RANDOM_SEED + idx)
    for t, date in enumerate(date_strs):
        # Encodage cyclique de la saisonnalité
        month_sin = np.sin(2 * np.pi * (t % 12) / 12)
        month_cos = np.cos(2 * np.pi * (t % 12) / 12)
        qtr_sin   = np.sin(2 * np.pi * (t % 3) / 3)

        ts_records.append({
            'client_id':        idx,
            'label_risque':     int(row.get('label_risque', 0)),
            'gouvernorat_code': int(row.get('gouvernorat_code', 0)),
            'date':             date,
            't':                t,
            'month_sin':        round(month_sin, 4),
            'month_cos':        round(month_cos, 4),
            'qtr_sin':          round(qtr_sin, 4),
            'montant_regle':    series['montant_regle'][t],
            'retard_moyen':     series['retard_moyen'][t],
            'ratio_regle':      series['ratio_regle'][t],
            'encours':          series['encours'][t],
        })

df_ts = pd.DataFrame(ts_records)
print(f"  Table de séries temporelles : {df_ts.shape[0]} lignes × {df_ts.shape[1]} colonnes")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Découpage Train / Validation / Test
# ══════════════════════════════════════════════════════════════════════
print("\n[3/7] Découpage Train / Validation / Test...")

t_train_end = TRAIN_MONTHS - 1       # 0..19 → train
t_val_end   = TRAIN_MONTHS + VAL_MONTHS - 1  # 20..22 → validation
# 23..25 → test

df_train = df_ts[df_ts['t'] <= t_train_end].copy()
df_val   = df_ts[(df_ts['t'] > t_train_end) & (df_ts['t'] <= t_val_end)].copy()
df_test  = df_ts[df_ts['t'] > t_val_end].copy()

print(f"  Train      : t=0..{t_train_end}  ({TRAIN_MONTHS} mois) → {len(df_train)} lignes")
print(f"  Validation : t={t_train_end+1}..{t_val_end}  ({VAL_MONTHS} mois)  → {len(df_val)} lignes")
print(f"  Test       : t={t_val_end+1}..{N_MONTHS-1}  ({TEST_MONTHS} mois)  → {len(df_test)} lignes")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — Modèles de prévision (TFT → N-HiTS → Prophet → Fallback)
# ══════════════════════════════════════════════════════════════════════
print("\n[4/7] Entraînement des modèles de prévision...")

FEATURES    = ['montant_regle', 'retard_moyen', 'ratio_regle', 'encours']
TIME_FEAT   = ['month_sin', 'month_cos', 'qtr_sin']
TARGET_COLS = ['montant_regle', 'retard_moyen']

model_used = None
forecasts_individual = []
forecasts_portfolio  = []

# ─── Tentative 1 : Temporal Fusion Transformer (PyTorch Forecasting) ──────────
def try_tft(df_train, df_val, df_ts, n_clients, horizon):
    try:
        from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
        from pytorch_forecasting.metrics import QuantileLoss
        import lightning as L

        print("  → Temporal Fusion Transformer (PyTorch Forecasting) détecté")

        # Normalisation z-score par client
        from sklearn.preprocessing import StandardScaler
        scalers = {}
        df_ts_norm = df_ts.copy()
        for col in TARGET_COLS:
            scalers[col] = {}
            for cid in df_ts['client_id'].unique():
                mask = df_ts['client_id'] == cid
                scaler = StandardScaler()
                df_ts_norm.loc[mask, col] = scaler.fit_transform(
                    df_ts.loc[mask, col].values.reshape(-1, 1)
                ).flatten()
                scalers[col][cid] = scaler

        max_encoder_length = LOOKBACK
        max_prediction_length = horizon

        training = TimeSeriesDataSet(
            df_ts_norm[df_ts_norm['t'] <= TRAIN_MONTHS - 1],
            time_idx="t",
            target="montant_regle",
            group_ids=["client_id"],
            max_encoder_length=max_encoder_length,
            max_prediction_length=max_prediction_length,
            time_varying_known_reals=TIME_FEAT,
            time_varying_unknown_reals=TARGET_COLS,
            static_categoricals=["gouvernorat_code"],
            add_relative_time_idx=True,
            add_target_scales=True,
        )

        validation = TimeSeriesDataSet.from_dataset(
            training,
            df_ts_norm,
            predict=True,
            stop_randomization=True,
        )

        train_dl = training.to_dataloader(train=True,  batch_size=64, num_workers=0)
        val_dl   = validation.to_dataloader(train=False, batch_size=64, num_workers=0)

        tft = TemporalFusionTransformer.from_dataset(
            training,
            hidden_size=64,
            attention_head_size=4,
            dropout=0.1,
            hidden_continuous_size=32,
            loss=QuantileLoss(),
            learning_rate=1e-3,
        )

        trainer = L.Trainer(
            max_epochs=50,
            gradient_clip_val=0.1,
            enable_model_summary=True,
        )
        trainer.fit(tft, train_dataloaders=train_dl, val_dataloaders=val_dl)

        print("  ✓ TFT entraîné avec succès")
        return tft, training, scalers
    except ImportError:
        print("  → pytorch-forecasting non disponible, passage à N-HiTS...")
        return None, None, None
    except Exception as e:
        print(f"  → TFT erreur ({e}), passage à N-HiTS...")
        return None, None, None


# ─── Tentative 2 : N-HiTS (NeuralForecast) ────────────────────────────────────
def try_nhits(df_ts, horizon, n_clients, t_train_end=None):
    try:
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NHITS, TFT as NFT

        print("  → N-HiTS (NeuralForecast) detecte")

        # Format NeuralForecast : unique_id, ds, y
        # Use zero-padded string IDs so lexicographic sort == numeric sort
        records = []
        for cid in df_ts['client_id'].unique()[:n_clients]:
            sub = df_ts[df_ts['client_id'] == cid].sort_values('t')
            for _, row in sub.iterrows():
                records.append({
                    'unique_id': f"{cid:06d}",
                    'ds':        pd.Timestamp(row['date'] + '-01'),
                    'y':         row['montant_regle'],
                    'retard':    row['retard_moyen'],
                })
        df_nf = pd.DataFrame(records)

        # Fit on train split only — avoids data leakage in MAPE evaluation.
        # predict() then yields h=1..horizon steps from end of training,
        # covering both the validation and test windows.
        if t_train_end is not None:
            train_cutoff = pd.Timestamp('2024-01-01') + pd.DateOffset(months=t_train_end)
            df_nf_fit = df_nf[df_nf['ds'] <= train_cutoff].copy()
        else:
            df_nf_fit = df_nf

        models = [
            NHITS(h=horizon, input_size=LOOKBACK, max_steps=100),
        ]

        # Essai d'ajout du TFT NeuralForecast
        try:
            models.append(NFT(h=horizon, input_size=LOOKBACK, max_steps=50))
        except Exception:
            pass

        nf = NeuralForecast(models=models, freq='MS')
        nf.fit(df_nf_fit)
        print("  ✓ N-HiTS entraine avec succes")
        return nf, df_nf
    except ImportError:
        print("  → neuralforecast non disponible, passage a Prophet...")
        return None, None
    except Exception as e:
        print(f"  → N-HiTS erreur ({e}), passage a Prophet...")
        return None, None


# ─── Tentative 3 : Prophet (Meta) ─────────────────────────────────────────────
def try_prophet(df_ts, horizon, n_clients):
    try:
        from prophet import Prophet

        print("  → Prophet (Meta) détecté")

        client_forecasts = []
        client_ids = df_ts['client_id'].unique()[:n_clients]

        for i, cid in enumerate(client_ids):
            if i % 50 == 0:
                print(f"    Prophet — client {i}/{len(client_ids)}...")

            sub = df_ts[df_ts['client_id'] == cid].sort_values('t')
            df_p = pd.DataFrame({
                'ds': pd.to_datetime([d + '-01' for d in sub['date']]),
                'y':  sub['montant_regle'].values,
            })

            try:
                m = Prophet(
                    seasonality_mode='multiplicative',
                    yearly_seasonality=False,
                    weekly_seasonality=False,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                )
                m.add_seasonality(name='quarterly', period=91.25, fourier_order=2)
                m.fit(df_p)

                future   = m.make_future_dataframe(periods=horizon, freq='MS')
                forecast = m.predict(future)
                future_fc = forecast.tail(horizon)

                for h_idx in range(horizon):
                    client_forecasts.append({
                        'client_id':      cid,
                        'horizon_mois':   h_idx + 1,
                        'montant_regle_pred': max(0, future_fc.iloc[h_idx]['yhat']),
                        'lower_80':       max(0, future_fc.iloc[h_idx]['yhat_lower']),
                        'upper_80':       max(0, future_fc.iloc[h_idx]['yhat_upper']),
                        'model':          'Prophet',
                    })
            except Exception:
                # Si Prophet échoue pour un client → prévision naïve
                last_val = sub['montant_regle'].iloc[-1]
                for h_idx in range(horizon):
                    client_forecasts.append({
                        'client_id':      cid,
                        'horizon_mois':   h_idx + 1,
                        'montant_regle_pred': last_val,
                        'lower_80':       last_val * 0.85,
                        'upper_80':       last_val * 1.15,
                        'model':          'Naive',
                    })

        print(f"  ✓ Prophet entraîné sur {len(client_ids)} clients")
        return pd.DataFrame(client_forecasts)
    except ImportError:
        print("  → Prophet non disponible, passage au fallback SARIMA/ETS...")
        return None
    except Exception as e:
        print(f"  → Prophet erreur ({e}), passage au fallback...")
        return None


# ─── Fallback final : SARIMA simplifié / Prévision naïve ──────────────────────
def fallback_forecast(df_ts, horizon, n_clients, t_train_end=None):
    print("  → Fallback : prevision naive avec tendance (moyenne mobile)")

    client_forecasts = []
    client_ids = df_ts['client_id'].unique()[:n_clients]

    for cid in client_ids:
        sub = df_ts[df_ts['client_id'] == cid].sort_values('t')
        if t_train_end is not None:
            sub = sub[sub['t'] <= t_train_end]

        # Moyenne mobile sur les 6 derniers mois
        last_vals      = sub['montant_regle'].values[-6:]
        last_retards   = sub['retard_moyen'].values[-6:]
        trend_montant  = (last_vals[-1] - last_vals[0]) / max(len(last_vals) - 1, 1)
        trend_retard   = (last_retards[-1] - last_retards[0]) / max(len(last_retards) - 1, 1)
        base_montant   = last_vals[-1]
        base_retard    = last_retards[-1]

        for h_idx in range(horizon):
            pred_montant = max(0, base_montant + trend_montant * (h_idx + 1))
            pred_retard  = max(0, base_retard + trend_retard * (h_idx + 1))
            client_forecasts.append({
                'client_id':          cid,
                'horizon_mois':       h_idx + 1,
                'montant_regle_pred': round(pred_montant, 2),
                'retard_pred':        round(pred_retard, 2),
                'lower_80':           round(pred_montant * 0.85, 2),
                'upper_80':           round(pred_montant * 1.15, 2),
                'model':              'NaiveTrend',
            })

    print(f"  ✓ Fallback appliqué sur {len(client_ids)} clients")
    return pd.DataFrame(client_forecasts)


# ─── Sélection du meilleur modèle disponible ──────────────────────────────────
N_CLIENTS_FOR_MODELS = min(200, N_CLIENTS_SAMPLE)

# Essai TFT
tft_model, tft_dataset, tft_scalers = try_tft(df_train, df_val, df_ts, N_CLIENTS_FOR_MODELS, HORIZON)

if tft_model is not None:
    model_used = 'TFT'
    # Générer les prévisions via TFT
    print("  Génération des prévisions TFT...")
    df_forecasts = pd.DataFrame()  # à compléter selon l'API TFT
else:
    # Essai N-HiTS
    nhits_model, df_nf = try_nhits(df_ts, HORIZON, N_CLIENTS_FOR_MODELS, t_train_end=t_train_end)

    if nhits_model is not None:
        model_used = 'N-HiTS'
        print("  Génération des prévisions N-HiTS...")
        try:
            preds = nhits_model.predict()
            # Reformater les prédictions
            # unique_id is zero-padded string ("000042") → convert back to int
            fc_records = []
            pred_col = 'NHITS' if 'NHITS' in preds.columns else preds.columns[-1]
            for uid, grp in preds.groupby('unique_id'):
                grp_sorted = grp.sort_values('ds')
                for h_idx, (_, row) in enumerate(grp_sorted.iterrows()):
                    val = max(0, float(row[pred_col]))
                    fc_records.append({
                        'client_id':          int(uid),
                        'horizon_mois':       h_idx + 1,
                        'montant_regle_pred': val,
                        'lower_80':           round(val * 0.85, 2),
                        'upper_80':           round(val * 1.15, 2),
                        'model':              'N-HiTS',
                    })
            df_forecasts = pd.DataFrame(fc_records)
        except Exception as e:
            print(f"  N-HiTS predict erreur ({e}), passage à Prophet...")
            df_forecasts = None
    else:
        df_forecasts = None

    if df_forecasts is None or len(df_forecasts) == 0:
        # Essai Prophet
        df_forecasts = try_prophet(df_ts, HORIZON, N_CLIENTS_FOR_MODELS)

        if df_forecasts is not None:
            model_used = 'Prophet'
        else:
            # Fallback final
            df_forecasts = fallback_forecast(df_ts, HORIZON, N_CLIENTS_FOR_MODELS, t_train_end=t_train_end)
            model_used = 'NaiveTrend'

print(f"\n  ► Modèle utilisé : {model_used}")
print(f"  ► Prévisions individuelles : {len(df_forecasts)} lignes")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Prévisions agrégées portefeuille (N-HiTS / Fallback)
# ══════════════════════════════════════════════════════════════════════
print("\n[5/7] Prévisions agrégées — portefeuille...")

# Calculer les indicateurs mensuels agrégés du portefeuille
portfolio_monthly = df_ts.groupby('t').agg(
    montant_regle_total=('montant_regle', 'sum'),
    retard_moyen_portf=('retard_moyen', 'mean'),
    ratio_regle_portf=('ratio_regle', 'mean'),
    encours_total=('encours', 'sum'),
    taux_risque=('label_risque', 'mean'),
).reset_index()
portfolio_monthly['date'] = [date_strs[t] for t in portfolio_monthly['t']]

# Prévision portefeuille via N-HiTS si disponible, sinon tendance
def portfolio_nhits_forecast(portfolio_monthly, horizon):
    try:
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NHITS

        df_p = pd.DataFrame({
            'unique_id': ['portfolio'] * len(portfolio_monthly),
            'ds':        pd.to_datetime([d + '-01' for d in portfolio_monthly['date']]),
            'y':         portfolio_monthly['retard_moyen_portf'].values,
        })

        nf = NeuralForecast(models=[NHITS(h=horizon, input_size=12, max_steps=200)], freq='MS')
        nf.fit(df_p)
        preds = nf.predict()

        fc_portf = []
        for h_idx in range(min(horizon, len(preds))):
            val = float(preds.iloc[h_idx].get('NHITS', preds.iloc[h_idx].iloc[-1]))
            fc_portf.append({
                'horizon_mois':          h_idx + 1,
                'retard_moyen_prevu':    round(max(0, val), 2),
                'retard_lower_80':       round(max(0, val * 0.90), 2),
                'retard_upper_80':       round(val * 1.10, 2),
                'model':                 'N-HiTS',
            })
        return pd.DataFrame(fc_portf)
    except Exception:
        return None

df_portf_fc = portfolio_nhits_forecast(portfolio_monthly, HORIZON)

if df_portf_fc is None:
    # Fallback tendance linéaire pour le portefeuille
    last_retards   = portfolio_monthly['retard_moyen_portf'].values[-6:]
    trend_retard   = (last_retards[-1] - last_retards[0]) / max(len(last_retards) - 1, 1)
    last_encours   = portfolio_monthly['encours_total'].values[-3:]
    trend_encours  = (last_encours[-1] - last_encours[0]) / max(len(last_encours) - 1, 1)

    portf_records = []
    for h in range(1, HORIZON + 1):
        retard_pred  = max(0, last_retards[-1] + trend_retard * h)
        encours_pred = max(0, last_encours[-1] + trend_encours * h)
        portf_records.append({
            'horizon_mois':       h,
            'retard_moyen_prevu': round(retard_pred, 2),
            'retard_lower_80':    round(retard_pred * 0.90, 2),
            'retard_upper_80':    round(retard_pred * 1.10, 2),
            'encours_total_prevu':round(encours_pred, 2),
            'model':              'LinearTrend',
        })
    df_portf_fc = pd.DataFrame(portf_records)
    print(f"  ✓ Prévision portefeuille (tendance linéaire) — {len(df_portf_fc)} horizons")
else:
    print(f"  ✓ Prévision portefeuille (N-HiTS) — {len(df_portf_fc)} horizons")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Évaluation (MAPE) sur la fenêtre de test
# ══════════════════════════════════════════════════════════════════════
print("\n[6/7] Évaluation des prévisions (MAPE)...")

def mape(y_true, y_pred):
    """Mean Absolute Percentage Error (évite la division par zéro)."""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    mask   = y_true != 0
    if mask.sum() == 0:
        return np.nan
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

# Récupérer les valeurs réelles sur la fenêtre de test (t=23,24,25)
# et les comparer aux prévisions à horizon 1, 2, 3 mois
df_test_vals = df_ts[df_ts['t'] > t_val_end].copy()
df_test_vals['horizon_mois'] = df_test_vals['t'] - t_val_end

metrics_records = []

# N-HiTS (and fallback) is trained on t=0..t_train_end and predicts h=1..HORIZON.
# h=1 -> t=TRAIN_MONTHS, ..., h=VAL_MONTHS+TEST_MONTHS -> t=N_MONTHS-1.
# Test window is t=t_val_end+1..N_MONTHS-1, which corresponds to
# model horizons h = VAL_MONTHS+1 .. VAL_MONTHS+TEST_MONTHS.
H_OFFSET = VAL_MONTHS  # add this to test_h to get the matching model h

# MAPE par horizon pour le modèle principal
for h_test in range(1, TEST_MONTHS + 1):
    h_model = h_test + H_OFFSET  # model horizon that aligns with test step h_test

    actuals_df = df_test_vals[df_test_vals['horizon_mois'] == h_test][['client_id', 'montant_regle']]
    preds_df   = df_forecasts[df_forecasts['horizon_mois'] == h_model][['client_id', 'montant_regle_pred']]

    # Merge on client_id — correct alignment regardless of sort order
    merged = actuals_df.merge(preds_df, on='client_id', how='inner')
    if len(merged) > 0:
        mape_val = mape(merged['montant_regle'].values, merged['montant_regle_pred'].values)
        seuil = 15 if h_test == 1 else (20 if h_test <= 3 else 30)
        metrics_records.append({
            'modele':       model_used,
            'horizon_mois': h_test,
            'metrique':     'MAPE (%)',
            'valeur':       round(mape_val, 2),
            'seuil_cible':  seuil,
            'statut':       'OK' if mape_val < seuil else 'X',
        })

# MAPE du modèle de référence (prévision naïve — last value)
last_known = df_ts[df_ts['t'] == t_val_end].set_index('client_id')['montant_regle']
for h_test in range(1, TEST_MONTHS + 1):
    actuals_df = df_test_vals[df_test_vals['horizon_mois'] == h_test][['client_id', 'montant_regle']]
    naive_df = actuals_df[['client_id']].copy()
    naive_df['montant_regle_pred'] = naive_df['client_id'].map(last_known)
    merged_naive = actuals_df.merge(naive_df, on='client_id', how='inner').dropna()
    if len(merged_naive) > 0:
        mape_naive = mape(merged_naive['montant_regle'].values, merged_naive['montant_regle_pred'].values)
        metrics_records.append({
            'modele':       'Naif (reference)',
            'horizon_mois': h_test,
            'metrique':     'MAPE (%)',
            'valeur':       round(mape_naive, 2),
            'seuil_cible':  None,
            'statut':       '--',
        })

df_metrics = pd.DataFrame(metrics_records)

print(f"\n  Résultats MAPE :")
print(f"  {'Modèle':<22} {'Horizon':<12} {'MAPE':<10} {'Seuil':<10} {'Statut'}")
print(f"  {'-'*60}")
for _, row in df_metrics.iterrows():
    seuil_str = f"< {row['seuil_cible']}%" if row['seuil_cible'] else "  —"
    print(f"  {row['modele']:<22} {row['horizon_mois']} mois      {row['valeur']:.2f}%      {seuil_str:<10} {row['statut']}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Enrichissement des prévisions + alertes + sauvegarde
# ══════════════════════════════════════════════════════════════════════
print("\n[7/7] Enrichissement des prévisions et sauvegarde...")

# Rejoindre les prévisions avec les infos client
df_client_info = df_sample[['label_risque', 'gouvernorat_code',
                              'retard_moyen_jours', 'montant_ttc_moyen']].copy()
df_client_info['client_id'] = range(len(df_client_info))

df_forecasts_enriched = df_forecasts.merge(df_client_info, on='client_id', how='left')

# Ajouter les prévisions de retard (simulation si non disponibles)
if 'retard_pred' not in df_forecasts_enriched.columns:
    df_forecasts_enriched['retard_pred'] = (
        df_forecasts_enriched['retard_moyen_jours'].fillna(5)
        + df_forecasts_enriched['label_risque'].fillna(0)
        * df_forecasts_enriched['horizon_mois'] * 1.5
        + np.random.normal(0, 2, len(df_forecasts_enriched))
    ).clip(lower=0).round(2)

# Calculer la tendance de risque prévisionnel
def risk_trend(montant_pred, montant_base, retard_pred, retard_base):
    """Score de tendance de risque : négatif = dégradation."""
    montant_ratio = (montant_pred - montant_base) / (montant_base + 1e-6)
    retard_ratio  = (retard_pred - retard_base) / (retard_base + 1e-6)
    return round(-0.5 * montant_ratio + 0.5 * retard_ratio, 4)

df_forecasts_enriched['risque_tendance'] = df_forecasts_enriched.apply(
    lambda r: risk_trend(
        r['montant_regle_pred'],
        r.get('montant_ttc_moyen', r['montant_regle_pred']),
        r['retard_pred'],
        r.get('retard_moyen_jours', r['retard_pred']),
    ), axis=1
)

# Alerte prévisionnelle
def alerte_prev(label_risque, risque_tendance, horizon):
    if label_risque == 1 and risque_tendance > 0.15:
        return 'ROUGE'
    elif label_risque == 1 or risque_tendance > 0.10:
        return 'ORANGE'
    elif risque_tendance > 0.03:
        return 'JAUNE'
    else:
        return 'VERT'

df_forecasts_enriched['alerte_prev'] = df_forecasts_enriched.apply(
    lambda r: alerte_prev(
        int(r.get('label_risque', 0)),
        float(r['risque_tendance']),
        int(r['horizon_mois'])
    ), axis=1
)

# ─── Sauvegardes CSV ──────────────────────────────────────────────────────────
df_forecasts_enriched.to_csv(OUTPUT_INDIV, index=False)
df_portf_fc.to_csv(OUTPUT_PORTF, index=False)
df_metrics.to_csv(OUTPUT_METRICS, index=False)
print(f"  ✓ {OUTPUT_INDIV}  ({len(df_forecasts_enriched)} lignes)")
print(f"  ✓ {OUTPUT_PORTF}  ({len(df_portf_fc)} lignes)")
print(f"  ✓ {OUTPUT_METRICS}")

# ─── Rapport Excel complet ────────────────────────────────────────────────────
try:
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        # Feuille 1 : Prévisions individuelles
        df_forecasts_enriched.to_excel(writer, sheet_name='Previsions_Clients', index=False)

        # Feuille 2 : Prévisions portefeuille
        df_portf_fc.to_excel(writer, sheet_name='Previsions_Portefeuille', index=False)

        # Feuille 3 : Métriques MAPE
        df_metrics.to_excel(writer, sheet_name='Metriques_MAPE', index=False)

        # Feuille 4 : Synthèse alertes prévisionnelles
        alert_summary = df_forecasts_enriched.groupby(
            ['horizon_mois', 'alerte_prev']
        ).size().reset_index(name='nb_clients')
        alert_summary.to_excel(writer, sheet_name='Alertes_Prevision', index=False)

        # Feuille 5 : Portefeuille mensuel historique
        portfolio_monthly.to_excel(writer, sheet_name='Historique_Portefeuille', index=False)

    print(f"  ✓ {OUTPUT_EXCEL}  (5 feuilles)")
except Exception as e:
    print(f"  Rapport Excel non généré : {e}")

# ─── Résumé final ─────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RÉSUMÉ M3 — Time Series Forecaster")
print("=" * 65)
print(f"  Modèle principal utilisé      : {model_used}")
print(f"  Clients analysés (prévision)  : {df_forecasts_enriched['client_id'].nunique()}")
print(f"  Horizon de prévision          : {HORIZON} mois")
print(f"  Prévision portefeuille        : {len(df_portf_fc)} horizons")

mape_h1 = df_metrics[(df_metrics['modele'] == model_used) & (df_metrics['horizon_mois'] == 1)]['valeur']
if len(mape_h1) > 0:
    print(f"  MAPE à 1 mois                 : {mape_h1.values[0]:.2f}%  (cible < 15%)")

# Alertes prévisionnelles à 3 mois
alertes_3m = df_forecasts_enriched[df_forecasts_enriched['horizon_mois'] == 3]['alerte_prev'].value_counts()
print(f"\n  Alertes prévisionnelles à 3 mois :")
for niveau, n in alertes_3m.items():
    print(f"    {niveau:<8} : {n} clients")

# Fichiers produits
print(f"\n  Fichiers produits :")
for f in [OUTPUT_INDIV, OUTPUT_PORTF, OUTPUT_METRICS, OUTPUT_EXCEL]:
    if os.path.exists(f):
        size_kb = os.path.getsize(f) // 1024
        print(f"    ✓ {f}  ({size_kb} Ko)")

print("\n  Prêt pour M4 (Anomaly Detection) et M5 (Scoring Ensemble)")
print("=" * 65)
