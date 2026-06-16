# =============================================================
#  CreditMind — M3 : Time Series Forecaster
#
#  INSTRUCTIONS :
#  1. Place ce fichier dans le répertoire contenant :
#     - dataset_combined_real_synth.csv  (produit par M1)
#     - SolvAI_Dataset_Nettoye.xlsx      (données réelles, optionnel)
#  2. Installe les dépendances :
#     pip install neuralforecast pytorch-forecasting lightning \
#                 pandas numpy scikit-learn openpyxl matplotlib prophet
#  3. Lance :
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
import os, warnings
warnings.filterwarnings('ignore')

# ─── CHEMINS ──────────────────────────────────────────────────────────────────
INPUT_COMBINED = 'dataset_combined_real_synth.csv'
INPUT_REAL     = 'SolvAI_Dataset_Nettoye.xlsx'
OUTPUT_INDIV   = 'm3_forecasts_individual.csv'
OUTPUT_PORTF   = 'm3_portfolio_forecast.csv'
OUTPUT_METRICS = 'm3_evaluation_metrics.csv'
OUTPUT_EXCEL   = 'm3_results_summary.xlsx'

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

has_real_history = False
if os.path.exists(INPUT_REAL):
    try:
        xl = pd.ExcelFile(INPUT_REAL)
        print(f"  Feuilles disponibles dans l'Excel : {xl.sheet_names}")

        if 'factures' in xl.sheet_names:
            df_factures = pd.read_excel(INPUT_REAL, sheet_name='factures')
            has_real_history = True
            print(f"  Factures réelles : {len(df_factures)} lignes")
        if 'reglements' in xl.sheet_names:
            df_reglements = pd.read_excel(INPUT_REAL, sheet_name='reglements')
            print(f"  Règlements réels : {len(df_reglements)} lignes")
        if not has_real_history:
            print("  → Feuilles 'factures'/'reglements' non trouvées — simulation activée")
    except Exception as e:
        print(f"  → Impossible de lire l'Excel ({e}) — simulation activée")
else:
    print(f"  → {INPUT_REAL} non trouvé — simulation de l'historique mensuel activée")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Construction des séries temporelles mensuelles
# ══════════════════════════════════════════════════════════════════════
print("\n[2/7] Construction des séries temporelles mensuelles...")

start_date = pd.Timestamp('2024-01-01')
dates      = [start_date + pd.DateOffset(months=i) for i in range(N_MONTHS)]
date_strs  = [d.strftime('%Y-%m') for d in dates]

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
    En production, remplacer par l'agrégation des vraies factures/règlements.
    """
    if seed is not None:
        np.random.seed(seed)

    montant_base = float(row.get('montant_ttc_moyen', 10000))
    retard_base  = float(row.get('retard_moyen_jours', 5))
    ratio_base   = float(row.get('ratio_encaissement', 0.95))
    label_risque = int(row.get('label_risque', 0))

    trend       = np.linspace(0, -0.1 * label_risque, n_months)
    seasonality = 0.15 * np.sin(2 * np.pi * np.arange(n_months) / 12)
    noise       = np.random.normal(0, 0.08, n_months)

    montant_regle = np.maximum(montant_base * (1 + trend + seasonality + noise), 0)

    retard_trend = label_risque * np.linspace(0, 15, n_months)
    retard_serie = np.maximum(retard_base + retard_trend + np.random.normal(0, 3, n_months), 0)

    ratio_serie  = np.clip(
        ratio_base - label_risque * np.linspace(0, 0.1, n_months)
        + np.random.normal(0, 0.03, n_months),
        0, 1.2,
    )
    encours_serie = np.maximum(montant_base * (1 - ratio_serie), 0)

    return {
        'montant_regle': np.round(montant_regle, 2),
        'retard_moyen':  np.round(retard_serie, 1),
        'ratio_regle':   np.round(ratio_serie, 4),
        'encours':       np.round(encours_serie, 2),
    }


print("  Construction des séries temporelles (simulation)...")
ts_records = []

for idx, (_, row) in enumerate(df_sample.iterrows()):
    series = simulate_monthly_series(row, seed=RANDOM_SEED + idx)
    for t, date in enumerate(date_strs):
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

t_train_end = TRAIN_MONTHS - 1                    # 0..19 → train
t_val_end   = TRAIN_MONTHS + VAL_MONTHS - 1       # 20..22 → validation
# t=23..25 → test

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


# ─── Tentative 1 : Temporal Fusion Transformer (PyTorch Forecasting) ──────────
def try_tft(df_train, df_val, df_ts, n_clients, horizon):
    try:
        from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
        from pytorch_forecasting.metrics import QuantileLoss
        import lightning as L

        print("  → Temporal Fusion Transformer (PyTorch Forecasting) détecté")

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

        training = TimeSeriesDataSet(
            df_ts_norm[df_ts_norm['t'] <= TRAIN_MONTHS - 1],
            time_idx="t",
            target="montant_regle",
            group_ids=["client_id"],
            max_encoder_length=LOOKBACK,
            max_prediction_length=horizon,
            time_varying_known_reals=TIME_FEAT,
            time_varying_unknown_reals=TARGET_COLS,
            static_categoricals=["gouvernorat_code"],
            add_relative_time_idx=True,
            add_target_scales=True,
        )
        validation = TimeSeriesDataSet.from_dataset(
            training, df_ts_norm, predict=True, stop_randomization=True,
        )

        train_dl = training.to_dataloader(train=True, batch_size=64, num_workers=0)
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
        trainer = L.Trainer(max_epochs=50, gradient_clip_val=0.1, enable_model_summary=True)
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
# FIX #1 — t_max : N-HiTS est entraîné uniquement sur t<=t_val_end pour que
# predict() génère des prévisions alignées sur la période de test (t=23..25).
# Sans ce filtre, fit() voit toutes les 26 observations et predict() retourne
# des dates futures inconnues (t=26..31), rendant la MAPE sans sens.
def try_nhits(df_ts, horizon, n_clients, t_max=None):
    try:
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NHITS, TFT as NFT

        print("  → N-HiTS (NeuralForecast) détecté")

        # Filtrer les données : n'exposer au modèle que les périodes <= t_max
        df_fit = df_ts[df_ts['t'] <= t_max] if t_max is not None else df_ts

        records = []
        for cid in df_fit['client_id'].unique()[:n_clients]:
            sub = df_fit[df_fit['client_id'] == cid].sort_values('t')
            for _, row in sub.iterrows():
                records.append({
                    'unique_id': str(cid),
                    'ds':        pd.Timestamp(row['date'] + '-01'),
                    'y':         row['montant_regle'],
                    'retard':    row['retard_moyen'],
                })
        df_nf = pd.DataFrame(records)

        # FIX #3 — max_steps : 100 est trop faible ; 500 permet une vraie convergence
        models = [
            NHITS(h=horizon, input_size=LOOKBACK, max_steps=500),
        ]

        try:
            models.append(NFT(h=horizon, input_size=LOOKBACK, max_steps=50))
        except Exception as e:
            # FIX Rahma #1 — except nu remplacé : afficher l'erreur plutôt que de la masquer
            print(f"    → TFT NeuralForecast ignoré ({e})")

        nf = NeuralForecast(models=models, freq='MS')
        nf.fit(df_nf)
        print("  ✓ N-HiTS entraîné avec succès")
        return nf, df_nf
    except ImportError:
        # FIX #2 — message explicite : neuralforecast doit être installé
        print("  → neuralforecast non disponible (pip install neuralforecast), passage à Prophet...")
        return None, None
    except Exception as e:
        print(f"  → N-HiTS erreur ({e}), passage à Prophet...")
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

            sub  = df_ts[df_ts['client_id'] == cid].sort_values('t')
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

                future    = m.make_future_dataframe(periods=horizon, freq='MS')
                forecast  = m.predict(future)
                future_fc = forecast.tail(horizon)

                for h_idx in range(horizon):
                    client_forecasts.append({
                        'client_id':          cid,
                        'horizon_mois':       h_idx + 1,
                        'montant_regle_pred': max(0, future_fc.iloc[h_idx]['yhat']),
                        'lower_80':           max(0, future_fc.iloc[h_idx]['yhat_lower']),
                        'upper_80':           max(0, future_fc.iloc[h_idx]['yhat_upper']),
                        'model':              'Prophet',
                    })
            except Exception as e:
                # FIX Rahma #1 — afficher l'erreur au lieu de la masquer silencieusement
                print(f"    → Prophet client {cid} erreur ({e}) — prévision naïve appliquée")
                last_val = sub['montant_regle'].iloc[-1]
                for h_idx in range(horizon):
                    client_forecasts.append({
                        'client_id':          cid,
                        'horizon_mois':       h_idx + 1,
                        'montant_regle_pred': last_val,
                        'lower_80':           last_val * 0.85,
                        'upper_80':           last_val * 1.15,
                        'model':              'Naive',
                    })

        print(f"  ✓ Prophet entraîné sur {len(client_ids)} clients")
        return pd.DataFrame(client_forecasts)
    except ImportError:
        print("  → Prophet non disponible, passage au fallback tendance linéaire...")
        return None
    except Exception as e:
        print(f"  → Prophet erreur ({e}), passage au fallback...")
        return None


# ─── Fallback final : prévision naïve avec tendance ───────────────────────────
def fallback_forecast(df_ts, horizon, n_clients):
    print("  → Fallback : prévision naïve avec tendance (moyenne mobile)")

    client_forecasts = []
    client_ids = df_ts['client_id'].unique()[:n_clients]

    for cid in client_ids:
        sub = df_ts[df_ts['client_id'] == cid].sort_values('t')

        last_vals    = sub['montant_regle'].values[-6:]
        last_retards = sub['retard_moyen'].values[-6:]
        trend_montant = (last_vals[-1] - last_vals[0]) / max(len(last_vals) - 1, 1)
        trend_retard  = (last_retards[-1] - last_retards[0]) / max(len(last_retards) - 1, 1)
        base_montant  = last_vals[-1]
        base_retard   = last_retards[-1]

        for h_idx in range(horizon):
            pred_montant = max(0, base_montant + trend_montant * (h_idx + 1))
            pred_retard  = max(0, base_retard  + trend_retard  * (h_idx + 1))
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

tft_model, tft_dataset, tft_scalers = try_tft(df_train, df_val, df_ts, N_CLIENTS_FOR_MODELS, HORIZON)

if tft_model is not None:
    model_used   = 'TFT'
    print("  Génération des prévisions TFT...")
    df_forecasts = pd.DataFrame()
else:
    # FIX #1 — t_max=t_val_end : N-HiTS s'entraîne sur t=0..22 seulement ;
    # predict() produit alors t=23..28, aligné avec la période de test (t=23..25)
    nhits_model, df_nf = try_nhits(df_ts, HORIZON, N_CLIENTS_FOR_MODELS, t_max=t_val_end)

    if nhits_model is not None:
        model_used = 'N-HiTS'
        print("  Génération des prévisions N-HiTS...")
        try:
            preds = nhits_model.predict()
            fc_records = []
            for unique_id, grp in preds.groupby('unique_id'):
                for h_idx, (_, row) in enumerate(grp.iterrows()):
                    val = float(row.get('NHITS', row.iloc[-1]))
                    fc_records.append({
                        'client_id':          int(unique_id),
                        'horizon_mois':       h_idx + 1,
                        'montant_regle_pred': max(0, val),
                        'lower_80':           max(0, val * 0.85),
                        'upper_80':           max(0, val * 1.15),
                        'model':              'N-HiTS',
                    })
            df_forecasts = pd.DataFrame(fc_records)
        except Exception as e:
            print(f"  N-HiTS predict erreur ({e}), passage à Prophet...")
            df_forecasts = None
    else:
        df_forecasts = None

    if df_forecasts is None or len(df_forecasts) == 0:
        df_forecasts = try_prophet(df_ts, HORIZON, N_CLIENTS_FOR_MODELS)
        if df_forecasts is not None:
            model_used = 'Prophet'
        else:
            df_forecasts = fallback_forecast(df_ts, HORIZON, N_CLIENTS_FOR_MODELS)
            model_used   = 'NaiveTrend'

print(f"\n  ► Modèle utilisé : {model_used}")
print(f"  ► Prévisions individuelles : {len(df_forecasts)} lignes")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Prévisions agrégées portefeuille (N-HiTS / Fallback)
# ══════════════════════════════════════════════════════════════════════
print("\n[5/7] Prévisions agrégées — portefeuille...")

portfolio_monthly = df_ts.groupby('t').agg(
    montant_regle_total=('montant_regle', 'sum'),
    retard_moyen_portf=('retard_moyen',   'mean'),
    ratio_regle_portf=('ratio_regle',     'mean'),
    encours_total=('encours',             'sum'),
    taux_risque=('label_risque',          'mean'),
).reset_index()
portfolio_monthly['date'] = [date_strs[t] for t in portfolio_monthly['t']]


# FIX #1 (portefeuille) — t_max empêche le même désalignement temporel que
# pour les prévisions individuelles.
# FIX Rahma #2 — ajout de montant_regle_total_prevu et ratio_regle_portf_prevu
# (colonnes manquantes dans les deux chemins de sortie).
def portfolio_nhits_forecast(portfolio_monthly, horizon, t_max=None):
    try:
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NHITS

        df_src = (portfolio_monthly[portfolio_monthly['t'] <= t_max]
                  if t_max is not None else portfolio_monthly)

        df_p = pd.DataFrame({
            'unique_id': ['portfolio'] * len(df_src),
            'ds':        pd.to_datetime([d + '-01' for d in df_src['date']]),
            'y':         df_src['retard_moyen_portf'].values,
        })

        nf = NeuralForecast(models=[NHITS(h=horizon, input_size=12, max_steps=500)], freq='MS')
        nf.fit(df_p)
        preds = nf.predict()

        # Tendances naïves pour les colonnes volume/encaissement (non prévues par N-HiTS)
        last_montants = df_src['montant_regle_total'].values[-6:]
        last_ratios   = df_src['ratio_regle_portf'].values[-6:]
        last_encours  = df_src['encours_total'].values[-3:]
        trend_montant = (last_montants[-1] - last_montants[0]) / max(len(last_montants) - 1, 1)
        trend_ratio   = (last_ratios[-1]   - last_ratios[0])   / max(len(last_ratios)   - 1, 1)
        trend_encours = (last_encours[-1]  - last_encours[0])  / max(len(last_encours)  - 1, 1)

        fc_portf = []
        for h_idx in range(min(horizon, len(preds))):
            val = float(preds.iloc[h_idx].get('NHITS', preds.iloc[h_idx].iloc[-1]))
            fc_portf.append({
                'horizon_mois':               h_idx + 1,
                'retard_moyen_prevu':         round(max(0, val), 2),
                'retard_lower_80':            round(max(0, val * 0.90), 2),
                'retard_upper_80':            round(val * 1.10, 2),
                'montant_regle_total_prevu':  round(max(0, last_montants[-1] + trend_montant * (h_idx + 1)), 2),
                'ratio_regle_portf_prevu':    round(float(np.clip(last_ratios[-1] + trend_ratio * (h_idx + 1), 0, 1.2)), 4),
                'encours_total_prevu':        round(max(0, last_encours[-1] + trend_encours * (h_idx + 1)), 2),
                'model':                      'N-HiTS',
            })
        return pd.DataFrame(fc_portf)
    except Exception as e:
        # FIX Rahma #1 — afficher l'erreur au lieu de la masquer
        print(f"  → N-HiTS portefeuille erreur ({e}), passage à la tendance linéaire...")
        return None


# FIX #1 — t_max=t_val_end pour aligner predict() avec la période de test
df_portf_fc = portfolio_nhits_forecast(portfolio_monthly, HORIZON, t_max=t_val_end)

if df_portf_fc is None:
    # Fallback tendance linéaire — FIX Rahma #2 : inclure montant et ratio
    pm = portfolio_monthly
    last_retards  = pm['retard_moyen_portf'].values[-6:]
    last_montants = pm['montant_regle_total'].values[-6:]
    last_ratios   = pm['ratio_regle_portf'].values[-6:]
    last_encours  = pm['encours_total'].values[-3:]

    trend_retard  = (last_retards[-1]  - last_retards[0])  / max(len(last_retards)  - 1, 1)
    trend_montant = (last_montants[-1] - last_montants[0]) / max(len(last_montants) - 1, 1)
    trend_ratio   = (last_ratios[-1]   - last_ratios[0])   / max(len(last_ratios)   - 1, 1)
    trend_encours = (last_encours[-1]  - last_encours[0])  / max(len(last_encours)  - 1, 1)

    portf_records = []
    for h in range(1, HORIZON + 1):
        portf_records.append({
            'horizon_mois':              h,
            'retard_moyen_prevu':        round(max(0, last_retards[-1]  + trend_retard  * h), 2),
            'retard_lower_80':           round(max(0, last_retards[-1]  + trend_retard  * h) * 0.90, 2),
            'retard_upper_80':           round(max(0, last_retards[-1]  + trend_retard  * h) * 1.10, 2),
            'montant_regle_total_prevu': round(max(0, last_montants[-1] + trend_montant * h), 2),
            'ratio_regle_portf_prevu':   round(float(np.clip(last_ratios[-1] + trend_ratio * h, 0, 1.2)), 4),
            'encours_total_prevu':       round(max(0, last_encours[-1]  + trend_encours * h), 2),
            'model':                     'LinearTrend',
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


# FIX #1 — La MAPE est valide uniquement si N-HiTS a été entraîné sur t<=t_val_end :
# predict() retourne alors t=23..28, dont les horizons 1..3 coïncident avec df_test.
df_test_vals = df_ts[df_ts['t'] > t_val_end].copy()
df_test_vals['horizon_mois'] = df_test_vals['t'] - t_val_end

metrics_records = []

for h in range(1, min(TEST_MONTHS + 1, HORIZON + 1)):
    actuals = df_test_vals[df_test_vals['horizon_mois'] == h]['montant_regle'].values
    preds_h = df_forecasts[df_forecasts['horizon_mois'] == h]['montant_regle_pred'].values

    n = min(len(actuals), len(preds_h))
    if n > 0:
        mape_val = mape(actuals[:n], preds_h[:n])
        seuil    = 15 if h == 1 else (20 if h <= 3 else 30)
        metrics_records.append({
            'modele':       model_used,
            'horizon_mois': h,
            'metrique':     'MAPE (%)',
            'valeur':       round(mape_val, 2),
            'seuil_cible':  seuil,
            'statut':       '✓' if mape_val < seuil else '✗',
        })

for h in range(1, min(TEST_MONTHS + 1, HORIZON + 1)):
    actuals    = df_test_vals[df_test_vals['horizon_mois'] == h]['montant_regle'].values
    last_known = df_ts[df_ts['t'] == t_val_end].set_index('client_id')['montant_regle']
    naive_preds = [
        last_known.get(cid, np.mean(actuals))
        for cid in df_test_vals[df_test_vals['horizon_mois'] == h]['client_id'].values
    ]
    n = min(len(actuals), len(naive_preds))
    if n > 0:
        metrics_records.append({
            'modele':       'Naif (référence)',
            'horizon_mois': h,
            'metrique':     'MAPE (%)',
            'valeur':       round(mape(actuals[:n], naive_preds[:n]), 2),
            'seuil_cible':  None,
            'statut':       '—',
        })

df_metrics = pd.DataFrame(metrics_records)

# FIX Rahma #4 — vérifier que df_metrics n'est pas vide avant de l'utiliser
if df_metrics.empty:
    print("  ATTENTION : df_metrics est vide — aucune métrique MAPE calculée.")
    print("    Causes possibles : df_forecasts vide, ou df_test_vals sans clients communs.")
    print("    Vérifiez que le modèle a produit des prévisions pour la colonne 'montant_regle_pred'.")
else:
    print(f"\n  Résultats MAPE :")
    print(f"  {'Modèle':<22} {'Horizon':<12} {'MAPE':<10} {'Seuil':<10} {'Statut'}")
    print(f"  {'-' * 60}")
    for _, row in df_metrics.iterrows():
        seuil_str = f"< {row['seuil_cible']}%" if row['seuil_cible'] else "  —"
        print(f"  {row['modele']:<22} {row['horizon_mois']} mois      "
              f"{row['valeur']:.2f}%      {seuil_str:<10} {row['statut']}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Enrichissement des prévisions + alertes + sauvegarde
# ══════════════════════════════════════════════════════════════════════
print("\n[7/7] Enrichissement des prévisions et sauvegarde...")

df_client_info = df_sample[['label_risque', 'gouvernorat_code',
                             'retard_moyen_jours', 'montant_ttc_moyen']].copy()
df_client_info['client_id'] = range(len(df_client_info))

df_forecasts_enriched = df_forecasts.merge(df_client_info, on='client_id', how='left')

# FIX Rahma #3 — détecter un désalignement client_id entre df_forecasts et df_client_info
unmatched = df_forecasts_enriched['label_risque'].isna().sum()
if unmatched > 0:
    n_fc   = df_forecasts['client_id'].nunique()
    n_info = df_client_info['client_id'].nunique()
    print(f"  ATTENTION : {unmatched} lignes sans correspondance après merge "
          f"(df_forecasts={n_fc} clients uniques, df_client_info={n_info} clients).")
    print("    → Vérifiez que client_id est du même type (int/str) dans les deux DataFrames.")
    print("    → Les sorties CSV risquent d'être incomplètes (NaN dans les colonnes enrichies).")

# Ajouter les prévisions de retard si absentes — seed fixé pour reproductibilité
if 'retard_pred' not in df_forecasts_enriched.columns:
    rng_retard = np.random.default_rng(RANDOM_SEED)
    df_forecasts_enriched['retard_pred'] = (
        df_forecasts_enriched['retard_moyen_jours'].fillna(5)
        + df_forecasts_enriched['label_risque'].fillna(0)
        * df_forecasts_enriched['horizon_mois'] * 1.5
        + rng_retard.normal(0, 2, len(df_forecasts_enriched))
    ).clip(lower=0).round(2)


def risk_trend(montant_pred, montant_base, retard_pred, retard_base):
    """Score de tendance de risque : positif = dégradation."""
    montant_ratio = (montant_pred - montant_base) / (montant_base + 1e-6)
    retard_ratio  = (retard_pred  - retard_base)  / (retard_base  + 1e-6)
    return round(-0.5 * montant_ratio + 0.5 * retard_ratio, 4)


df_forecasts_enriched['risque_tendance'] = df_forecasts_enriched.apply(
    lambda r: risk_trend(
        r['montant_regle_pred'],
        r.get('montant_ttc_moyen', r['montant_regle_pred']),
        r['retard_pred'],
        r.get('retard_moyen_jours', r['retard_pred']),
    ), axis=1,
)


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
        int(r['horizon_mois']),
    ), axis=1,
)

# ─── Sauvegardes CSV ──────────────────────────────────────────────────────────
df_forecasts_enriched.to_csv(OUTPUT_INDIV, index=False)
df_portf_fc.to_csv(OUTPUT_PORTF, index=False)
df_metrics.to_csv(OUTPUT_METRICS, index=False)
print(f"  ✓ {OUTPUT_INDIV}  ({len(df_forecasts_enriched)} lignes)")
print(f"  ✓ {OUTPUT_PORTF}  ({len(df_portf_fc)} lignes)")
print(f"  ✓ {OUTPUT_METRICS}  ({len(df_metrics)} lignes)")

# ─── Rapport Excel complet ────────────────────────────────────────────────────
try:
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        df_forecasts_enriched.to_excel(writer, sheet_name='Previsions_Clients',      index=False)
        df_portf_fc.to_excel(          writer, sheet_name='Previsions_Portefeuille', index=False)
        df_metrics.to_excel(           writer, sheet_name='Metriques_MAPE',          index=False)
        alert_summary = df_forecasts_enriched.groupby(
            ['horizon_mois', 'alerte_prev']
        ).size().reset_index(name='nb_clients')
        alert_summary.to_excel(writer, sheet_name='Alertes_Prevision',       index=False)
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

if not df_metrics.empty:
    mape_h1 = df_metrics[
        (df_metrics['modele'] == model_used) & (df_metrics['horizon_mois'] == 1)
    ]['valeur']
    if len(mape_h1) > 0:
        print(f"  MAPE à 1 mois                 : {mape_h1.values[0]:.2f}%  (cible < 15%)")

alertes_3m = df_forecasts_enriched[
    df_forecasts_enriched['horizon_mois'] == 3
]['alerte_prev'].value_counts()
print(f"\n  Alertes prévisionnelles à 3 mois :")
for niveau, n in alertes_3m.items():
    print(f"    {niveau:<8} : {n} clients")

print(f"\n  Fichiers produits :")
for f in [OUTPUT_INDIV, OUTPUT_PORTF, OUTPUT_METRICS, OUTPUT_EXCEL]:
    if os.path.exists(f):
        size_kb = os.path.getsize(f) // 1024
        print(f"    ✓ {f}  ({size_kb} Ko)")

print("\n  Prêt pour M4 (Anomaly Detection) et M5 (Scoring Ensemble)")
print("=" * 65)
