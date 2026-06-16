#!/usr/bin/env python3
"""
Génère des données de test minimalistes pour valider ingest.py + rag_engine.py.
Produit 50 clients (10 réels, 40 synthétiques) dans data/
"""
import random
import pandas as pd
from pathlib import Path

random.seed(42)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

N_REAL  = 10
N_SYNTH = 40
N_TOTAL = N_REAL + N_SYNTH

# Distributions volontairement variées pour couvrir les 3 requêtes de test :
#   Q1 → clients ROUGE à Sfax (gouvernorat_code=17)
#   Q2 → concept retard de paiement (retard_max_jours > 30)
#   Q3 → règles pour un client GRN (nature_client_code=11)

rows = []
for i in range(N_TOTAL):
    # Gouvernorat : forcer quelques clients à Sfax (code 17)
    if i in (0, 1, 2, 5):
        gouv = 17   # SFAX
    else:
        gouv = random.choice(list(range(25)))

    # Segment : forcer quelques GRN (code 11) dont un avec retard
    if i in (3, 4, 5):
        seg = 11    # GRN
    else:
        seg = random.choice(list(range(23)))

    mode = random.choice(list(range(8)))

    nb_regl     = random.randint(0, 20)
    retard_max  = round(random.uniform(0, 120), 1) if nb_regl > 0 else 0.0
    taux_retard = round(random.uniform(0, 1), 3)
    ratio_enc   = round(random.uniform(0.2, 1.0), 3) if nb_regl > 0 else 0.0
    anciennete  = random.randint(30, 2000)
    nb_fac      = random.randint(1, 50)
    nb_avoirs   = random.randint(0, 5)
    mttc_total  = round(random.uniform(1000, 500_000), 2)
    mttc_moyen  = round(mttc_total / nb_fac, 2)
    mttc_max    = round(mttc_moyen * random.uniform(1, 3), 2)
    mttc_std    = round(mttc_moyen * random.uniform(0.1, 0.5), 2)
    ratio_avoir = round(nb_avoirs / nb_fac, 3)
    mreg_total  = round(mttc_total * ratio_enc, 2)
    mreg_moyen  = round(mreg_total / max(nb_regl, 1), 2)
    retard_moy  = round(retard_max * 0.6, 1)
    nb_ret_pos  = random.randint(0, nb_regl)
    nb_ret_grav = random.randint(0, nb_ret_pos)
    nb_modes    = random.randint(1, 3)

    # label_risque selon règles M1
    label = 0
    if nb_regl == 0:
        label = 1
        mode = 7   # INCONNU
    elif retard_max > 30:
        label = 1
    elif taux_retard > 0.5:
        label = 1

    rows.append({
        "gouvernorat_code":    gouv,
        "nature_client_code":  seg,
        "mode_paiement_code":  mode,
        "nb_factures":         nb_fac,
        "nb_avoirs":           nb_avoirs,
        "ratio_avoirs":        ratio_avoir,
        "montant_ttc_total":   mttc_total,
        "montant_ttc_moyen":   mttc_moyen,
        "montant_ttc_max":     mttc_max,
        "montant_ttc_std":     mttc_std,
        "anciennete_jours":    anciennete,
        "nb_reglements":       nb_regl,
        "montant_reg_total":   mreg_total,
        "montant_reg_moyen":   mreg_moyen,
        "retard_moyen_jours":  retard_moy,
        "retard_max_jours":    retard_max,
        "nb_retards_positifs": nb_ret_pos,
        "nb_retards_graves":   nb_ret_grav,
        "taux_retard":         taux_retard,
        "nb_modes_distincts":  nb_modes,
        "ratio_encaissement":  ratio_enc,
        "label_risque":        label,
    })

df = pd.DataFrame(rows)
combined_path = OUT / "dataset_combined_real_synth.csv"
df.to_csv(combined_path, index=False)
print(f"dataset_combined_real_synth.csv  →  {len(df)} lignes")

# Scores M2 : score_final_m2 = 0.7*score_gnn + 0.3*score_contagion
score_rows = []
for i, r in df.iterrows():
    if r["label_risque"] == 1:
        score_gnn = round(random.uniform(55, 95), 1)
    else:
        score_gnn = round(random.uniform(5, 45), 1)
    score_cont = round(random.uniform(0, 60), 1)
    score_final = round(0.7 * score_gnn + 0.3 * score_cont, 1)
    # Forcer quelques ROUGE à Sfax pour Q1
    if i in (0, 1):
        score_gnn, score_cont, score_final = 88.0, 72.0, round(0.7*88+0.3*72, 1)
    alerte = "ROUGE" if score_final > 70 else ("ORANGE" if score_final >= 30 else "VERT")
    score_rows.append({
        "client_index": i,
        "score_gnn":        score_gnn,
        "score_contagion":  score_cont,
        "score_final_m2":   score_final,
        "alerte":           alerte,
    })

scores = pd.DataFrame(score_rows)
scores_path = OUT / "m2_gnn_scores.csv"
scores.to_csv(scores_path, index=False)
print(f"m2_gnn_scores.csv               →  {len(scores)} lignes")
print(f"  ROUGE: {(scores.alerte=='ROUGE').sum()}  ORANGE: {(scores.alerte=='ORANGE').sum()}  VERT: {(scores.alerte=='VERT').sum()}")
rouge_sfax = [(i, rows[i]['gouvernorat_code']) for i in range(N_TOTAL) if score_rows[i]['alerte']=='ROUGE' and rows[i]['gouvernorat_code']==17]
print(f"  Clients ROUGE à Sfax (gouv=17): {rouge_sfax}")
grn = [(i, score_rows[i]['alerte'], rows[i]['label_risque']) for i in range(N_TOTAL) if rows[i]['nature_client_code']==11]
print(f"  Clients GRN (seg=11): {grn}")
