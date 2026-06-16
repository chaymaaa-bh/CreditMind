# =============================================================
#  CreditMind — M1 : Synthetic Data Engine
#
#  INSTRUCTIONS :
#  1. Place ce fichier dans :
#     C:\Users\Rahma Moalla\Desktop\CreditMind\
#  2. Installe les dépendances :
#     pip install tab-ddpm sdmetrics opacus torch pandas openpyxl
#  3. Lance :
#     python m1_synthetic_data.py
#
#  Résultat :
#     synthetic_clients_20000.csv  → 20 000 clients synthétiques
# =============================================================

import pandas as pd
import numpy as np
import os, warnings
warnings.filterwarnings('ignore')

# ─── CHEMIN VERS TA DATA NETTOYÉE ─────────────────────────────────────────────
INPUT = r'SolvAI_Dataset_Nettoye.xlsx'

if not os.path.exists(INPUT):
    print(f"ERREUR : fichier introuvable → {INPUT}")
    print("Lance d'abord nettoyer_data.py pour générer ce fichier.")
    exit()

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 1 — Lecture du dataset nettoyé
# ═══════════════════════════════════════════════════════════════
print("► Lecture du dataset nettoyé...")
df = pd.read_excel(INPUT, sheet_name='clients_features')
print(f"  Shape : {df.shape}")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 2 — Préparation des données pour TabDDPM
# ═══════════════════════════════════════════════════════════════
print("\n► Préparation des données...")

# Colonnes à garder pour la génération (features numériques + codes)
NUMERIC_COLS = [
    'nb_factures', 'montant_ttc_total', 'montant_ttc_moyen',
    'montant_ttc_max', 'montant_ttc_std', 'nb_avoirs', 'ratio_avoirs',
    'anciennete_jours', 'nb_reglements', 'montant_reg_total',
    'montant_reg_moyen', 'retard_moyen_jours', 'retard_max_jours',
    'nb_retards_positifs', 'nb_retards_graves', 'taux_retard',
    'nb_modes_distincts', 'ratio_encaissement',
]
CATEGORICAL_COLS = [
    'gouvernorat_code', 'nature_client_code', 'mode_paiement_code',
]
TARGET_COL = 'label_risque'

# Garder uniquement les colonnes utiles
cols_to_use = NUMERIC_COLS + CATEGORICAL_COLS + [TARGET_COL]
data = df[cols_to_use].copy()

# Remplir les valeurs manquantes
data[NUMERIC_COLS] = data[NUMERIC_COLS].fillna(data[NUMERIC_COLS].median())
data[CATEGORICAL_COLS] = data[CATEGORICAL_COLS].fillna(-1).astype(int)

print(f"  Colonnes numériques  : {len(NUMERIC_COLS)}")
print(f"  Colonnes catégorielles : {len(CATEGORICAL_COLS)}")
print(f"  Lignes après nettoyage : {len(data)}")
print(f"  Label risque=1 : {data[TARGET_COL].sum()} ({data[TARGET_COL].mean():.1%})")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 3 — Entraînement TabDDPM
# ═══════════════════════════════════════════════════════════════
print("\n► Entraînement TabDDPM...")

try:
    from tab_ddpm import GaussianMultinomialDiffusion
    from tab_ddpm.modules import MLPDiffusion
    import torch

    # Préparer les tensors
    X_num = torch.tensor(data[NUMERIC_COLS].values, dtype=torch.float32)
    X_cat = torch.tensor(data[CATEGORICAL_COLS].values, dtype=torch.long)
    y     = torch.tensor(data[TARGET_COL].values, dtype=torch.long)

    # Nombre de catégories par colonne catégorielle
    num_classes = [int(data[c].max()) + 2 for c in CATEGORICAL_COLS]

    # Modèle
    model = GaussianMultinomialDiffusion(
        num_classes=num_classes,
        num_numerical_features=len(NUMERIC_COLS),
        denoise_fn=MLPDiffusion(
            d_in=len(NUMERIC_COLS) + sum(num_classes),
            num_classes=2,        # label_risque binaire
            is_y_cond=True,
            rtdl_params={'d_layers': [256, 256, 256], 'dropout': 0.0},
        ),
        gaussian_loss_type='mse',
        scheduler='cosine',
        num_timesteps=1000,
    )

    # Entraînement (simplifiée — utilise le trainer intégré)
    from tab_ddpm.train import train
    train(
        model=model,
        X_num=X_num,
        X_cat=X_cat,
        y=y,
        num_epochs=500,
        lr=0.002,
        batch_size=64,
        verbose=True,
    )

    # ═══════════════════════════════════════════════════════════
    # ÉTAPE 4 — Génération 20 000 clients synthétiques
    # ═══════════════════════════════════════════════════════════
    print("\n► Génération de 20 000 clients synthétiques...")

    # Générer en respectant la distribution réelle du label
    n_total  = 20000
    real_risk_ratio = data[TARGET_COL].mean()
    n_risque = int(n_total * real_risk_ratio)
    n_safe   = n_total - n_risque
    print(f"  Distribution réelle → risque={real_risk_ratio:.1%} · synthétique : {n_risque} risque / {n_safe} solvable")

    X_num_gen_r, X_cat_gen_r = model.sample(n_risque, y_dist=torch.ones(n_risque, dtype=torch.long))
    X_num_gen_s, X_cat_gen_s = model.sample(n_safe,   y_dist=torch.zeros(n_safe,  dtype=torch.long))

    X_num_gen = torch.cat([X_num_gen_r, X_num_gen_s], dim=0).numpy()
    X_cat_gen = torch.cat([X_cat_gen_r, X_cat_gen_s], dim=0).numpy()
    y_gen     = np.array([1]*n_risque + [0]*n_safe)

    synth = pd.DataFrame(X_num_gen, columns=NUMERIC_COLS)
    for i, col in enumerate(CATEGORICAL_COLS):
        synth[col] = X_cat_gen[:, i]
    synth[TARGET_COL] = y_gen

except ImportError:
    # ─── FALLBACK : CTGAN (si tab-ddpm pas installé) ────────────────────────
    print("  tab-ddpm non trouvé → utilisation de CTGAN comme fallback")
    print("  (pip install ctgan  pour utiliser CTGAN)")

    try:
        from ctgan import CTGAN

        #model_ctgan = CTGAN(epochs=200, verbose=True)
        model_ctgan = CTGAN(epochs=500, verbose=True, batch_size=100)
        model_ctgan.fit(data, CATEGORICAL_COLS + [TARGET_COL])

        print("\n► Génération de 20 000 clients synthétiques (CTGAN)...")
        synth = model_ctgan.sample(20000)

    except ImportError:
        # ─── FALLBACK FINAL : Gaussian Copula (sdmetrics) ───────────────────
        print("  CTGAN non trouvé → utilisation de GaussianCopula (sdmetrics)")
        print("  pip install sdmetrics  pour l'utiliser")

        from sdv.single_table import GaussianCopulaSynthesizer
        from sdv.metadata import SingleTableMetadata

        metadata = SingleTableMetadata()
        metadata.detect_from_dataframe(data)
        for col in CATEGORICAL_COLS + [TARGET_COL]:
            metadata.update_column(col, sdtype='categorical')

        synth_model = GaussianCopulaSynthesizer(metadata)
        synth_model.fit(data)

        print("\n► Génération de 20 000 clients synthétiques (GaussianCopula)...")
        synth = synth_model.sample(num_rows=20000)

# ─── Post-traitement ──────────────────────────────────────────────────────────
# Forcer les contraintes métier sur les données générées
synth['nb_factures']       = synth['nb_factures'].clip(lower=1).round().astype(int)
synth['nb_reglements']     = synth['nb_reglements'].clip(lower=0).round().astype(int)
synth['montant_ttc_total'] = synth['montant_ttc_total'].clip(lower=0)
synth['taux_retard']       = synth['taux_retard'].clip(0, 1)
synth['ratio_encaissement']= synth['ratio_encaissement'].clip(0, 2)
synth[TARGET_COL]          = synth[TARGET_COL].round().astype(int).clip(0, 1)

# Arrondir
for col in NUMERIC_COLS:
    if col in synth.columns:
        synth[col] = synth[col].round(3)

print(f"\n  Clients synthétiques générés : {len(synth)}")
print(f"  Label risque=1 : {synth[TARGET_COL].sum()} ({synth[TARGET_COL].mean():.1%})")

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 5 — Évaluation qualité avec SDMetrics
# ═══════════════════════════════════════════════════════════════
print("\n► Évaluation de la qualité (SDMetrics)...")

try:
    from sdmetrics.reports.single_table import QualityReport

    report = QualityReport()
    report.generate(
        real_data=data,
        synthetic_data=synth[data.columns].head(len(data)),
        metadata={
            'columns': {
                **{c: {'sdtype': 'numerical'}   for c in NUMERIC_COLS},
                **{c: {'sdtype': 'categorical'} for c in CATEGORICAL_COLS},
                TARGET_COL: {'sdtype': 'categorical'},
            }
        }
    )

    score = report.get_score()
    print(f"\n  ╔══════════════════════════════╗")
    print(f"  ║  Fidelity Score : {score:.3f}      ║")
    print(f"  ║  Cible          : > 0.80      ║")
    print(f"  ║  Statut : {'✓ OK' if score >= 0.80 else '✗ À améliorer'}                ║")
    print(f"  ╚══════════════════════════════╝")

    if score < 0.80:
        print("\n  → Conseils pour améliorer le score :")
        print("    - Augmenter le nombre d'epochs (500 → 1000)")
        print("    - Réduire le learning rate (0.002 → 0.001)")
        print("    - Vérifier les colonnes avec valeurs extrêmes")

except Exception as e:
    print(f"  SDMetrics non disponible : {e}")
    print("  pip install sdmetrics  pour évaluer la qualité")

# ═══════════════════════════════════════════════════════════════
# SAUVEGARDE
# ═══════════════════════════════════════════════════════════════
OUTPUT_CSV      = r'synthetic_clients_20000.csv'
synth.to_csv(OUTPUT_CSV, index=False)
print(f"\n✓ Dataset synthétique sauvegardé : {OUTPUT_CSV}")
print(f"  {len(synth)} lignes · {len(synth.columns)} colonnes")

# Combiner real + synthetic pour M2/M3/M4
combined = pd.concat([data, synth[data.columns]], ignore_index=True)
OUTPUT_COMBINED = r'dataset_combined_real_synth.csv'
combined.to_csv(OUTPUT_COMBINED, index=False)
print(f"\n✓ Dataset combiné (réel + synthétique) : {OUTPUT_COMBINED}")
print(f"  {len(combined)} lignes au total")
print(f"  Prêt pour M2 (GNN), M3 (Time Series), M4 (Anomaly Detection)")
