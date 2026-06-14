# =============================================================
#  CreditMind — M4 : Anomaly Detection
#
#  INSTRUCTIONS :
#  1. Place ce fichier dans :
#     C:\Users\Rahma Moalla\Desktop\CreditMind\
#  2. Assure-toi que ces fichiers existent (produits par M1/M3) :
#     - dataset_combined_real_synth.csv
#     - m3_forecasts_individual.csv
#  3. Installe les dépendances :
#     pip install scikit-learn torch river pandas numpy openpyxl matplotlib
#  4. Lance :
#     python m4_anomaly_detection.py
#
#  Résultats produits :
#     m4_anomaly_scores.csv          → score d'anomalie par client
#     m4_anomaly_alerts.csv          → alertes graduées (VERT/ORANGE/ROUGE)
#     m4_streaming_log.csv           → log des anomalies détectées en streaming
#     m4_results_summary.xlsx        → rapport Excel complet (5 feuilles)
# =============================================================

import pandas as pd
import numpy as np
import os, warnings, time
from datetime import datetime
warnings.filterwarnings('ignore')

# ─── CHEMINS ──────────────────────────────────────────────────────────────────
INPUT_COMBINED  = r'dataset_combined_real_synth.csv'
INPUT_M3        = r'm3_forecasts_individual.csv'
OUTPUT_SCORES   = r'm4_anomaly_scores.csv'
OUTPUT_ALERTS   = r'm4_anomaly_alerts.csv'
OUTPUT_STREAM   = r'm4_streaming_log.csv'
OUTPUT_EXCEL    = r'm4_results_summary.xlsx'

# ─── PARAMÈTRES ───────────────────────────────────────────────────────────────
CONTAMINATION     = 0.05    # proportion attendue d'anomalies (~5%)
IF_N_ESTIMATORS   = 300     # nombre d'arbres Isolation Forest
LSTM_HIDDEN       = 64      # taille couche LSTM
LSTM_LATENT       = 16      # dimension espace latent (bottleneck)
LSTM_EPOCHS       = 30      # epochs d'entraînement autoencoder
LSTM_SEQ_LEN      = 12      # longueur de séquence (12 mois)
THRESHOLD_PCT     = 95      # percentile pour le seuil de détection LSTM
N_STREAM_TRANS    = 200     # nombre de transactions simulées en streaming
RANDOM_SEED       = 42
np.random.seed(RANDOM_SEED)

print("=" * 65)
print("  CreditMind — M4 : Anomaly Detection")
print("=" * 65)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Chargement des données
# ══════════════════════════════════════════════════════════════════════
print("\n[1/8] Chargement des données...")

if not os.path.exists(INPUT_COMBINED):
    print(f"  ERREUR : {INPUT_COMBINED} introuvable.")
    print("  Lance d'abord m1_synthetic_data.py")
    exit()

df = pd.read_csv(INPUT_COMBINED)
print(f"  Dataset combiné   : {df.shape[0]} clients · {df.shape[1]} colonnes")

# Charger les prévisions M3 si disponibles
has_m3 = os.path.exists(INPUT_M3)
if has_m3:
    df_m3 = pd.read_csv(INPUT_M3)
    print(f"  Prévisions M3     : {df_m3.shape[0]} lignes disponibles")
else:
    print(f"  Prévisions M3     : non disponibles (M4 fonctionne en autonome)")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Construction des features comportementales (12 features)
# ══════════════════════════════════════════════════════════════════════
print("\n[2/8] Construction des features comportementales...")

# Features numériques disponibles dans le dataset
NUMERIC_BASE = [
    'nb_factures', 'montant_ttc_total', 'montant_ttc_moyen',
    'montant_ttc_max', 'montant_ttc_std',
    'nb_reglements', 'montant_reg_total', 'montant_reg_moyen',
    'retard_moyen_jours', 'retard_max_jours',
    'taux_retard', 'ratio_encaissement',
]

# Garder uniquement les colonnes disponibles
available_cols = [c for c in NUMERIC_BASE if c in df.columns]
df_feat = df[available_cols + ['label_risque']].copy()

# Compléter avec des proxies si colonnes manquantes
if 'montant_ttc_std' not in df_feat.columns:
    df_feat['montant_ttc_std'] = df_feat.get('montant_ttc_moyen', 10000) * 0.2

if 'retard_max_jours' not in df_feat.columns:
    df_feat['retard_max_jours'] = df_feat.get('retard_moyen_jours', 5).clip(lower=0) * 2

# Remplir les valeurs manquantes par la médiane
for col in available_cols:
    if col in df_feat.columns:
        df_feat[col] = df_feat[col].fillna(df_feat[col].median())

# Features finales pour Isolation Forest
FEATURE_COLS = [c for c in available_cols if c in df_feat.columns]
X = df_feat[FEATURE_COLS].values
y = df_feat['label_risque'].values

print(f"  Features utilisées        : {len(FEATURE_COLS)}")
print(f"  Clients (total)           : {len(X)}")
print(f"  Clients label_risque=1    : {y.sum()} ({y.mean():.1%})")
print(f"  Features : {FEATURE_COLS}")

# Normalisation
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Isolation Forest
# ══════════════════════════════════════════════════════════════════════
print("\n[3/8] Isolation Forest...")

from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, classification_report

print(f"  Entraînement IF ({IF_N_ESTIMATORS} arbres, contamination={CONTAMINATION})...")
t0 = time.time()

if_model = IsolationForest(
    n_estimators=IF_N_ESTIMATORS,
    contamination=CONTAMINATION,
    max_features=1.0,
    random_state=RANDOM_SEED,
    n_jobs=-1,
)
if_model.fit(X_scaled)

# Scores d'anomalie : négatif = plus anormal
# On normalise entre 0 et 1 (1 = très anormal)
if_scores_raw = if_model.score_samples(X_scaled)
if_scores_norm = 1 - (if_scores_raw - if_scores_raw.min()) / (if_scores_raw.max() - if_scores_raw.min())
if_predictions = (if_model.predict(X_scaled) == -1).astype(int)  # -1 = anomalie → 1

elapsed = time.time() - t0
print(f"  ✓ Entraîné en {elapsed:.1f}s")
print(f"  Anomalies détectées : {if_predictions.sum()} ({if_predictions.mean():.1%})")

# Évaluation
# Utiliser uniquement les clients réels pour l'évaluation (label connu)
mask_eval = y != -1
if mask_eval.sum() > 0 and y[mask_eval].sum() > 0:
    f1_if = f1_score(y[mask_eval], if_predictions[mask_eval], zero_division=0)
    prec_if = precision_score(y[mask_eval], if_predictions[mask_eval], zero_division=0)
    rec_if  = recall_score(y[mask_eval], if_predictions[mask_eval], zero_division=0)
    print(f"  Précision : {prec_if:.3f}  |  Rappel : {rec_if:.3f}  |  F1 : {f1_if:.3f}")
else:
    f1_if, prec_if, rec_if = 0.0, 0.0, 0.0
    print("  Évaluation non disponible (labels insuffisants)")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 4 — LSTM Autoencoder
# ══════════════════════════════════════════════════════════════════════
print("\n[4/8] LSTM Autoencoder...")

def build_sequences(X_scaled, seq_len=LSTM_SEQ_LEN):
    """
    Construit des séquences temporelles simulées par client.
    En production, ces séquences proviendraient de l'historique mensuel réel.
    Ici on simule en ajoutant du bruit progressif sur la fenêtre temporelle.
    """
    n_clients, n_features = X_scaled.shape
    sequences = np.zeros((n_clients, seq_len, n_features))

    for i in range(n_clients):
        base = X_scaled[i]
        for t in range(seq_len):
            noise_scale = 0.05 * (1 + t / seq_len)
            noise = np.random.normal(0, noise_scale, n_features)
            # Clients à risque : dégradation progressive sur la fenêtre
            if y[i] == 1:
                drift = np.linspace(0, 0.3, seq_len)[t]
            else:
                drift = 0.0
            sequences[i, t, :] = base + noise + drift
    return sequences.astype(np.float32)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    print("  PyTorch détecté — entraînement du LSTM Autoencoder...")

    # Construire les séquences
    print("  Construction des séquences temporelles...")
    sequences = build_sequences(X_scaled, LSTM_SEQ_LEN)
    n_features = sequences.shape[2]

    # Séparer train (clients SAIN) et test (tous les clients)
    idx_sain  = np.where(y == 0)[0]
    idx_all   = np.arange(len(y))

    X_train_lstm = torch.tensor(sequences[idx_sain],  dtype=torch.float32)
    X_all_lstm   = torch.tensor(sequences[idx_all],   dtype=torch.float32)

    train_loader = DataLoader(
        TensorDataset(X_train_lstm),
        batch_size=64, shuffle=True
    )

    # ─── Architecture LSTM Autoencoder ────────────────────────────────
    class LSTMAutoencoder(nn.Module):
        def __init__(self, n_features, hidden_size=LSTM_HIDDEN, latent_dim=LSTM_LATENT, seq_len=LSTM_SEQ_LEN):
            super().__init__()
            self.seq_len    = seq_len
            self.n_features = n_features
            self.hidden_size = hidden_size

            # Encodeur : 2 couches LSTM
            self.encoder_lstm1 = nn.LSTM(n_features,   hidden_size, batch_first=True)
            self.encoder_lstm2 = nn.LSTM(hidden_size,  latent_dim,  batch_first=True)
            self.encoder_drop  = nn.Dropout(0.2)

            # Décodeur : 2 couches LSTM symétriques
            self.decoder_lstm1 = nn.LSTM(latent_dim,  hidden_size, batch_first=True)
            self.decoder_lstm2 = nn.LSTM(hidden_size, n_features,  batch_first=True)

            # Couche de sortie linéaire
            self.output_layer  = nn.Linear(n_features, n_features)

        def forward(self, x):
            # Encodage
            out, _ = self.encoder_lstm1(x)
            out     = self.encoder_drop(out)
            encoded, _ = self.encoder_lstm2(out)

            # Décodage
            out, _ = self.decoder_lstm1(encoded)
            out, _ = self.decoder_lstm2(out)
            reconstructed = self.output_layer(out)
            return reconstructed

    model_lstm = LSTMAutoencoder(n_features=n_features)
    optimizer  = torch.optim.Adam(model_lstm.parameters(), lr=1e-3)
    criterion  = nn.MSELoss()

    # Entraînement
    print(f"  Entraînement sur {len(idx_sain)} clients SAIN — {LSTM_EPOCHS} epochs...")
    model_lstm.train()
    loss_history = []

    for epoch in range(LSTM_EPOCHS):
        epoch_loss = 0.0
        for (batch,) in train_loader:
            optimizer.zero_grad()
            reconstructed = model_lstm(batch)
            loss = criterion(reconstructed, batch)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        avg_loss = epoch_loss / len(train_loader)
        loss_history.append(avg_loss)

        if (epoch + 1) % 10 == 0:
            print(f"    Epoch {epoch+1:3d}/{LSTM_EPOCHS} — Loss: {avg_loss:.6f}")

    print(f"  ✓ LSTM Autoencoder entraîné")

    # Calcul des erreurs de reconstruction
    model_lstm.eval()
    with torch.no_grad():
        X_all_tensor  = X_all_lstm
        reconstructed = model_lstm(X_all_tensor)
        # Erreur MSE par client (moyenne sur tous les timesteps et features)
        lstm_errors   = ((X_all_tensor - reconstructed) ** 2).mean(dim=(1, 2)).numpy()

    # Calibration du seuil sur les clients SAIN
    errors_sain = lstm_errors[idx_sain]
    threshold_lstm = np.percentile(errors_sain, THRESHOLD_PCT)
    lstm_predictions = (lstm_errors > threshold_lstm).astype(int)

    # Normalisation des erreurs entre 0 et 1
    lstm_scores_norm = (lstm_errors - lstm_errors.min()) / (lstm_errors.max() - lstm_errors.min() + 1e-8)

    print(f"  Seuil de détection (P{THRESHOLD_PCT}) : {threshold_lstm:.6f}")
    print(f"  Anomalies détectées : {lstm_predictions.sum()} ({lstm_predictions.mean():.1%})")

    if y[mask_eval].sum() > 0:
        f1_lstm   = f1_score(y[mask_eval], lstm_predictions[mask_eval], zero_division=0)
        prec_lstm = precision_score(y[mask_eval], lstm_predictions[mask_eval], zero_division=0)
        rec_lstm  = recall_score(y[mask_eval], lstm_predictions[mask_eval], zero_division=0)
        print(f"  Précision : {prec_lstm:.3f}  |  Rappel : {rec_lstm:.3f}  |  F1 : {f1_lstm:.3f}")
    else:
        f1_lstm, prec_lstm, rec_lstm = 0.0, 0.0, 0.0

    lstm_available = True

except ImportError:
    print("  PyTorch non disponible — LSTM Autoencoder désactivé")
    print("  pip install torch  pour activer ce composant")
    lstm_scores_norm = np.zeros(len(X))
    lstm_predictions = np.zeros(len(X), dtype=int)
    f1_lstm, prec_lstm, rec_lstm = 0.0, 0.0, 0.0
    threshold_lstm = 0.0
    lstm_available = False

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 5 — Streaming avec River
# ══════════════════════════════════════════════════════════════════════
print("\n[5/8] Détection en streaming (River)...")

def simulate_streaming_transactions(df_feat, n_transactions=N_STREAM_TRANS):
    """
    Simule un flux de transactions de règlement en temps réel.
    Chaque transaction contient : client_id, montant, retard, mode_paiement.
    Environ 10% des transactions sont intentionnellement anormales.
    """
    transactions = []
    client_ids = df_feat.index.tolist()

    for i in range(n_transactions):
        cid   = np.random.choice(client_ids)
        row   = df_feat.iloc[cid]
        is_anomaly = np.random.random() < 0.10  # 10% d'anomalies simulées

        montant_base = float(row.get('montant_reg_moyen', 10000))
        retard_base  = float(row.get('retard_moyen_jours', 5))

        if is_anomaly:
            # Anomalies simulées : montant très bas ou retard très élevé
            anomaly_type = np.random.choice(['montant_chute', 'retard_spike', 'paiement_partiel'])
            if anomaly_type == 'montant_chute':
                montant = montant_base * np.random.uniform(0.05, 0.25)
                retard  = retard_base + np.random.uniform(5, 20)
            elif anomaly_type == 'retard_spike':
                montant = montant_base * np.random.uniform(0.8, 1.0)
                retard  = retard_base + np.random.uniform(30, 120)
            else:  # paiement partiel
                montant = montant_base * np.random.uniform(0.3, 0.6)
                retard  = retard_base + np.random.uniform(10, 45)
        else:
            montant = montant_base * np.random.normal(1.0, 0.08)
            retard  = max(0, retard_base + np.random.normal(0, 3))
            anomaly_type = None

        transactions.append({
            'transaction_id':  i,
            'client_id':       cid,
            'timestamp':       datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'montant':         round(max(0, montant), 2),
            'retard_jours':    round(max(0, retard), 1),
            'is_true_anomaly': int(is_anomaly),
            'anomaly_type':    anomaly_type if is_anomaly else 'normal',
        })

    return pd.DataFrame(transactions)

try:
    from river import anomaly, drift, stats, preprocessing as river_prep

    print("  River détecté — initialisation des modèles streaming...")

    # Modèle 1 : HalfSpaceTrees (détection d'anomalies en ligne)
    hst_model = anomaly.HalfSpaceTrees(
        n_trees=25,
        height=8,
        window_size=50,
        seed=RANDOM_SEED,
    )

    # Modèle 2 : ADWIN (détection de dérive sur les montants)
    adwin_montant = drift.ADWIN(delta=0.002)

    # Modèle 3 : KSWIN (dérive sur les retards)
    try:
        kswin_retard = drift.KSWIN(alpha=0.005, window_size=100, stat_size=30, seed=RANDOM_SEED)
        kswin_available = True
    except Exception:
        kswin_retard = drift.ADWIN(delta=0.005)
        kswin_available = False

    # Statistiques en ligne par client
    client_stats = {}

    print(f"  Simulation de {N_STREAM_TRANS} transactions en streaming...")
    df_transactions = simulate_streaming_transactions(df_feat, N_STREAM_TRANS)

    stream_log = []
    n_alerts   = 0
    latencies  = []

    for _, txn in df_transactions.iterrows():
        t_start = time.perf_counter()

        cid     = int(txn['client_id'])
        montant = float(txn['montant'])
        retard  = float(txn['retard_jours'])

        # Initialiser les stats client si nouveau
        if cid not in client_stats:
            client_stats[cid] = {
                'montant_mean': stats.Mean(),
                'montant_var':  stats.Var(),
                'retard_mean':  stats.Mean(),
                'n_txn':        0,
            }

        cs = client_stats[cid]

        # Features pour HalfSpaceTrees
        x_stream = {
            'montant':      montant,
            'retard':       retard,
            'montant_norm': montant / (cs['montant_mean'].get() + 1e-6) if cs['n_txn'] > 0 else 1.0,
            'retard_norm':  retard / (cs['retard_mean'].get() + 1e-6) if cs['n_txn'] > 0 else 1.0,
        }

        # Score HalfSpaceTrees (0=normal, 1=anomalie)
        # River : score_one() d'abord, puis learn_one() qui retourne None (modifie en place)
        hst_score = hst_model.score_one(x_stream)
        hst_model.learn_one(x_stream)   # ← NE PAS réassigner : learn_one modifie en place

        # Détection dérive ADWIN (montant)
        # River >= 0.21 : update() retourne None, l'alerte est dans adwin_montant.drift_detected
        adwin_montant.update(montant)
        adwin_alert = adwin_montant.drift_detected

        # Détection dérive KSWIN (retard)
        kswin_retard.update(retard)
        kswin_alert = kswin_retard.drift_detected

        # Décision globale streaming
        is_stream_anomaly = (
            hst_score > 0.7 or
            adwin_alert or
            kswin_alert
        )

        # Mise à jour stats client
        cs['montant_mean'].update(montant)
        cs['montant_var'].update(montant)
        cs['retard_mean'].update(retard)
        cs['n_txn'] += 1

        # Latence
        latency_ms = (time.perf_counter() - t_start) * 1000
        latencies.append(latency_ms)

        if is_stream_anomaly:
            n_alerts += 1
            alerte_type = []
            if hst_score > 0.7:  alerte_type.append('HST')
            if adwin_alert:      alerte_type.append('ADWIN_montant')
            if kswin_alert:      alerte_type.append('KSWIN_retard')

            stream_log.append({
                'transaction_id':   int(txn['transaction_id']),
                'client_id':        cid,
                'timestamp':        txn['timestamp'],
                'montant':          montant,
                'retard_jours':     retard,
                'hst_score':        round(hst_score, 4),
                'adwin_alerte':     int(adwin_alert),
                'kswin_alerte':     int(kswin_alert),
                'alerte_type':      '+'.join(alerte_type),
                'is_true_anomaly':  int(txn['is_true_anomaly']),
                'anomaly_type_reel':txn['anomaly_type'],
                'latence_ms':       round(latency_ms, 4),
            })

    df_stream_log = pd.DataFrame(stream_log) if stream_log else pd.DataFrame()

    avg_latency = np.mean(latencies)
    print(f"  ✓ {N_STREAM_TRANS} transactions traitées")
    print(f"  Alertes déclenchées   : {n_alerts} ({n_alerts/N_STREAM_TRANS:.1%})")
    print(f"  Latence moyenne       : {avg_latency:.3f} ms  (cible < 5 ms)")
    print(f"  Latence maximale      : {max(latencies):.3f} ms")

    # Évaluation streaming
    if len(df_stream_log) > 0:
        true_pos = df_stream_log['is_true_anomaly'].sum()
        print(f"  Vrais positifs détectés en streaming : {true_pos}/{df_transactions['is_true_anomaly'].sum()}")

    river_available = True

except ImportError:
    print("  River non disponible — pip install river")
    print("  Simulation du streaming désactivée")
    df_stream_log  = pd.DataFrame()
    river_available = False
    avg_latency    = 0.0

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Ensemble : vote majoritaire (IF + LSTM + River)
# ══════════════════════════════════════════════════════════════════════
print("\n[6/8] Combinaison par vote majoritaire (Ensemble)...")

# Score River agrégé par client (depuis le log streaming)
river_scores = np.zeros(len(df_feat))
if river_available and len(df_stream_log) > 0:
    river_by_client = df_stream_log.groupby('client_id')['hst_score'].mean()
    for cid, score in river_by_client.items():
        if cid < len(river_scores):
            river_scores[cid] = score

river_scores_norm = (river_scores - river_scores.min()) / (river_scores.max() - river_scores.min() + 1e-8)
river_predictions = (river_scores_norm > 0.6).astype(int)

# Vote majoritaire : anomalie si ≥ 2 composants sur 3 signalent une anomalie
votes_sum    = if_predictions + lstm_predictions + river_predictions
ensemble_pred = (votes_sum >= 2).astype(int)

# Score d'anomalie final : moyenne pondérée des trois scores normalisés
#   IF : 40%  |  LSTM : 40%  |  River : 20%
score_final = (
    0.40 * if_scores_norm +
    0.40 * lstm_scores_norm +
    0.20 * river_scores_norm
)

print(f"  Votes IF      : {if_predictions.sum()} anomalies")
print(f"  Votes LSTM    : {lstm_predictions.sum()} anomalies")
print(f"  Votes River   : {river_predictions.sum()} anomalies")
print(f"  Ensemble (≥2) : {ensemble_pred.sum()} anomalies ({ensemble_pred.mean():.1%})")

# Évaluation ensemble
if y[mask_eval].sum() > 0:
    f1_ens   = f1_score(y[mask_eval], ensemble_pred[mask_eval], zero_division=0)
    prec_ens = precision_score(y[mask_eval], ensemble_pred[mask_eval], zero_division=0)
    rec_ens  = recall_score(y[mask_eval], ensemble_pred[mask_eval], zero_division=0)
    print(f"\n  ┌─────────────────────────────────────────────┐")
    print(f"  │  ÉVALUATION ENSEMBLE                        │")
    print(f"  │  Précision : {prec_ens:.3f}  (cible > 0.75)       │")
    print(f"  │  Rappel    : {rec_ens:.3f}  (cible > 0.70)       │")
    print(f"  │  F1-score  : {f1_ens:.3f}  (cible > 0.75)       │")
    print(f"  │  Statut    : {'✓ OK' if f1_ens >= 0.75 else '✗ À améliorer'}                         │")
    print(f"  └─────────────────────────────────────────────┘")
else:
    f1_ens, prec_ens, rec_ens = 0.0, 0.0, 0.0

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 7 — Alertes graduées et enrichissement
# ══════════════════════════════════════════════════════════════════════
print("\n[7/8] Génération des alertes graduées...")

def get_alert_level(score, label, if_pred, lstm_pred, river_pred):
    """Détermine le niveau d'alerte selon les règles métier."""
    votes = if_pred + lstm_pred + river_pred
    if score > 0.75 or (votes == 3) or (label == 1 and score > 0.60):
        return 'ROUGE'
    elif score > 0.50 or (votes >= 2) or (label == 1 and score > 0.35):
        return 'ORANGE'
    elif score > 0.25 or votes == 1:
        return 'JAUNE'
    else:
        return 'VERT'

def get_anomaly_reason(row):
    """Identifie la raison principale de l'anomalie."""
    reasons = []
    montant_moyen = row.get('montant_ttc_moyen', 10000)
    retard        = row.get('retard_moyen_jours', 0)
    taux_retard   = row.get('taux_retard', 0)
    ratio_enc     = row.get('ratio_encaissement', 1.0)

    if retard > 30:
        reasons.append(f'Retard élevé ({retard:.0f}j)')
    if taux_retard > 0.15:
        reasons.append(f'Taux retard élevé ({taux_retard:.1%})')
    if ratio_enc < 0.80:
        reasons.append(f'Faible encaissement ({ratio_enc:.1%})')
    if row.get('nb_retards_graves', 0) > 2:
        reasons.append('Retards graves répétés')

    return ' | '.join(reasons) if reasons else 'Comportement statistiquement atypique'

# Construire le dataframe de résultats
results = []
for i in range(len(df_feat)):
    row       = df_feat.iloc[i]
    alert_lvl = get_alert_level(
        score_final[i],
        int(y[i]),
        int(if_predictions[i]),
        int(lstm_predictions[i]),
        int(river_predictions[i]),
    )
    reason = get_anomaly_reason(row)

    results.append({
        'client_id':          i,
        'label_risque':       int(y[i]),
        'score_anomalie_if':  round(float(if_scores_norm[i]), 4),
        'score_anomalie_lstm':round(float(lstm_scores_norm[i]), 4),
        'score_anomalie_river':round(float(river_scores_norm[i]), 4),
        'score_anomalie_final':round(float(score_final[i]), 4),
        'pred_isolation_forest': int(if_predictions[i]),
        'pred_lstm':           int(lstm_predictions[i]),
        'pred_river':          int(river_predictions[i]),
        'pred_ensemble':       int(ensemble_pred[i]),
        'nb_votes':            int(if_predictions[i] + lstm_predictions[i] + river_predictions[i]),
        'alerte':              alert_lvl,
        'raison_principale':   reason,
        'retard_moyen_jours':  float(row.get('retard_moyen_jours', 0)),
        'taux_retard':         float(row.get('taux_retard', 0)),
        'ratio_encaissement':  float(row.get('ratio_encaissement', 1.0)),
        'montant_ttc_moyen':   float(row.get('montant_ttc_moyen', 0)),
    })

df_results = pd.DataFrame(results)

# Distribution des alertes
alert_dist = df_results['alerte'].value_counts()
print(f"  Distribution des alertes :")
for level in ['ROUGE', 'ORANGE', 'JAUNE', 'VERT']:
    n = alert_dist.get(level, 0)
    pct = n / len(df_results) * 100
    bar = '█' * int(pct / 2)
    print(f"    {level:<8} : {n:5d} clients ({pct:5.1f}%)  {bar}")

# ══════════════════════════════════════════════════════════════════════
# ÉTAPE 8 — Sauvegarde des résultats
# ══════════════════════════════════════════════════════════════════════
print("\n[8/8] Sauvegarde des résultats...")

# CSV 1 : Scores d'anomalie
df_results.to_csv(OUTPUT_SCORES, index=False)
print(f"  ✓ {OUTPUT_SCORES}  ({len(df_results)} lignes)")

# CSV 2 : Alertes uniquement (ORANGE + ROUGE)
df_alerts = df_results[df_results['alerte'].isin(['ORANGE', 'ROUGE'])].copy()
df_alerts = df_alerts.sort_values('score_anomalie_final', ascending=False)
df_alerts.to_csv(OUTPUT_ALERTS, index=False)
print(f"  ✓ {OUTPUT_ALERTS}  ({len(df_alerts)} clients en alerte)")

# CSV 3 : Log streaming
if len(df_stream_log) > 0:
    df_stream_log.to_csv(OUTPUT_STREAM, index=False)
    print(f"  ✓ {OUTPUT_STREAM}  ({len(df_stream_log)} alertes streaming)")
else:
    pd.DataFrame().to_csv(OUTPUT_STREAM, index=False)
    print(f"  ✓ {OUTPUT_STREAM}  (vide — River non disponible)")

# Excel rapport complet
try:
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:

        # Feuille 1 : Tous les scores
        df_results.to_excel(writer, sheet_name='Scores_Anomalie', index=False)

        # Feuille 2 : Alertes ORANGE + ROUGE
        df_alerts.to_excel(writer, sheet_name='Alertes_Clients', index=False)

        # Feuille 3 : Log streaming
        if len(df_stream_log) > 0:
            df_stream_log.to_excel(writer, sheet_name='Log_Streaming', index=False)

        # Feuille 4 : Métriques d'évaluation
        metrics_data = {
            'Composant':  ['Isolation Forest', 'LSTM Autoencoder', 'River (streaming)', 'Ensemble (vote ≥2)'],
            'Précision':  [round(prec_if, 3), round(prec_lstm, 3), '—', round(prec_ens, 3)],
            'Rappel':     [round(rec_if, 3),  round(rec_lstm, 3),  '—', round(rec_ens, 3)],
            'F1-score':   [round(f1_if, 3),   round(f1_lstm, 3),   '—', round(f1_ens, 3)],
            'Seuil_cible_F1': ['> 0.70', '> 0.70', '> 0.65', '> 0.75'],
            'Statut':     [
                '✓' if f1_if   >= 0.70 else '✗',
                '✓' if f1_lstm >= 0.70 else '✗',
                '—',
                '✓' if f1_ens  >= 0.75 else '✗',
            ],
        }
        pd.DataFrame(metrics_data).to_excel(writer, sheet_name='Metriques_Evaluation', index=False)

        # Feuille 5 : Synthèse alertes par niveau
        synthese = df_results.groupby('alerte').agg(
            nb_clients=('client_id', 'count'),
            score_moyen=('score_anomalie_final', 'mean'),
            retard_moyen=('retard_moyen_jours', 'mean'),
            taux_retard_moyen=('taux_retard', 'mean'),
            clients_label_1=('label_risque', 'sum'),
        ).reset_index()
        synthese['score_moyen']        = synthese['score_moyen'].round(3)
        synthese['retard_moyen']       = synthese['retard_moyen'].round(1)
        synthese['taux_retard_moyen']  = synthese['taux_retard_moyen'].round(3)
        synthese.to_excel(writer, sheet_name='Synthese_Alertes', index=False)

    print(f"  ✓ {OUTPUT_EXCEL}  (5 feuilles)")
except Exception as e:
    print(f"  Rapport Excel non généré : {e}")

# ─── Résumé final ─────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RÉSUMÉ M4 — Anomaly Detection")
print("=" * 65)
print(f"  Composants actifs :")
print(f"    Isolation Forest       : ✓  ({IF_N_ESTIMATORS} arbres)")
print(f"    LSTM Autoencoder       : {'✓  (seuil P'+str(THRESHOLD_PCT)+' = '+str(round(threshold_lstm,4))+')' if lstm_available else '✗  (PyTorch requis)'}")
print(f"    River Streaming        : {'✓  ('+str(N_STREAM_TRANS)+' transactions, latence moy. '+str(round(avg_latency,3))+'ms)' if river_available else '✗  (river requis)'}")
print(f"\n  Clients analysés         : {len(df_results)}")
print(f"  Anomalies détectées      : {ensemble_pred.sum()} ({ensemble_pred.mean():.1%})")
print(f"\n  Distribution alertes :")
for level in ['ROUGE', 'ORANGE', 'JAUNE', 'VERT']:
    n = alert_dist.get(level, 0)
    print(f"    {level:<8} : {n} clients")
print(f"\n  Performance Ensemble :")
print(f"    F1-score  : {f1_ens:.3f}  (cible > 0.75)")
print(f"    Précision : {prec_ens:.3f}  (cible > 0.75)")
print(f"    Rappel    : {rec_ens:.3f}  (cible > 0.70)")
print(f"\n  Fichiers produits :")
for f in [OUTPUT_SCORES, OUTPUT_ALERTS, OUTPUT_STREAM, OUTPUT_EXCEL]:
    size = os.path.getsize(f) // 1024 if os.path.exists(f) else 0
    print(f"    ✓ {f}  ({size} Ko)")
print(f"\n  Prêt pour M5 (Scoring Ensemble)")
print("=" * 65)
