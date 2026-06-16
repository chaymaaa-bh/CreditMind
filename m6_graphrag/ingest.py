#!/usr/bin/env python3
"""
CreditMind M6 — Ingestion pipeline : CSV + Excel → Neo4j

Fichiers attendus (DATA_PATH ou répertoire courant) :
  dataset_combined_real_synth.csv   (M1 output — 21 637 lignes)
  m2_gnn_scores.csv                 (M2 output — 21 637 lignes)
  SolvAI_Dataset_Nettoye.xlsx       (optionnel — ajoute code_responsable sur les réels)

Usage :
  python ingest.py
  python ingest.py --data-path ./data/raw
  python ingest.py --wipe          # vide le graphe avant ingestion
  python ingest.py --no-contagion  # saute les arêtes de contagion
"""

import argparse
import logging
import os
from io import StringIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

load_dotenv()
log = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement '{name}' manquante. "
            "Vérifiez votre fichier .env (NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)."
        )
    return value


# ─── Config ────────────────────────────────────────────────────────────────────

NEO4J_URI      = _require_env("NEO4J_URI")
NEO4J_USER     = _require_env("NEO4J_USERNAME")
NEO4J_PASSWORD = _require_env("NEO4J_PASSWORD")
DATA_PATH      = Path(os.getenv("DATA_PATH", "."))
BATCH_SIZE     = 500
N_REAL         = 1_637   # lignes réelles dans le combined CSV (les premières)

# ─── Lookup tables (encodage alphabétique depuis nettoyer_data.py) ─────────────

GOUVERNORAT = {
     0: ("ARIANA",     "GRAND_TUNIS"),
     1: ("BEN AROUS",  "GRAND_TUNIS"),
     2: ("BIZERTE",    "NORD"),
     3: ("BÉJA",       "NORD"),
     4: ("EXPORT",     "EXPORT"),
     5: ("GABÈS",      "SUD"),
     6: ("GAFSA",      "SUD"),
     7: ("JENDOUBA",   "NORD"),
     8: ("KAIROUAN",   "CENTRE_OUEST"),
     9: ("KASSERINE",  "CENTRE_OUEST"),
    10: ("KÉBILLI",    "SUD"),
    11: ("LE KEF",     "NORD"),
    12: ("MAHDIA",     "CENTRE_EST"),
    13: ("MANNOUBA",   "GRAND_TUNIS"),
    14: ("MONASTIR",   "CENTRE_EST"),
    15: ("MÉDENINE",   "SUD"),
    16: ("NABEUL",     "CAP_BON"),
    17: ("SFAX",       "CENTRE_EST"),
    18: ("SIDI BOUZID","CENTRE_OUEST"),
    19: ("SILIANA",    "NORD"),
    20: ("SOUSSE",     "CENTRE_EST"),
    21: ("TATAOUINE",  "SUD"),
    22: ("TOZEUR",     "SUD"),
    23: ("TUNIS",      "GRAND_TUNIS"),
    24: ("ZAGHOUAN",   "CAP_BON"),
}

SEGMENT = {
     0: ("ALFAPACK",       "AUTRE"),
     1: ("CHALLENGERA",    "CHALLENGER"),
     2: ("CHALLENGERB",    "CHALLENGER"),
     3: ("CHALLENGERC",    "CHALLENGER"),
     4: ("CHALLENGERD",    "CHALLENGER"),
     5: ("DET",            "AUTRE"),
     6: ("ETATIQUE",       "PUBLIC"),
     7: ("EXPORT",         "EXPORT"),
     8: ("EXPORTINDIRECT", "EXPORT"),
     9: ("GEM",            "GRAND_COMPTE"),
    10: ("GMS",            "GRAND_COMPTE"),
    11: ("GRN",            "GRAND_COMPTE"),
    12: ("GRO",            "GRAND_COMPTE"),
    13: ("MCN",            "AUTRE"),
    14: ("NEGOCE",         "AUTRE"),
    15: ("OUTSIDER",       "AUTRE"),
    16: ("PAN",            "AUTRE"),
    17: ("PERSONNEL",      "PUBLIC"),
    18: ("PHN",            "AUTRE"),
    19: ("PREMIUM",        "GRAND_COMPTE"),
    20: ("SCN",            "AUTRE"),
    21: ("SPN",            "AUTRE"),
    22: ("STEG",           "PUBLIC"),
}

# Vérification empirique depuis SolvAI_Dataset_Nettoye.xlsx :
# sorted unique modes → 0=DTRT, 1=ECAI, 2=ECHQ, 3=ERET, 4=ETRC, 5=ETRT, 6=EVIRL, 7=INCONNU
MODE_PAIEMENT = {
    0: ("DTRT",    "Dépôt Traite"),
    1: ("ECAI",    "Encaissement Caisse"),
    2: ("ECHQ",    "Encaissement Chèque"),
    3: ("ERET",    "Effet Retour"),
    4: ("ETRC",    "Effet Traite / Crédit documentaire"),
    5: ("ETRT",    "Effet Traite"),
    6: ("EVIRL",   "Encaissement Virement"),
    7: ("INCONNU", "Mode inconnu — aucun règlement enregistré"),
}

CONCEPTS = [
    {
        "nom": "Absence de règlement",
        "description": (
            "Client sans aucun règlement enregistré. "
            "Indicateur fort de non-paiement : taux de risque 100 %."
        ),
        "seuils": "nb_reglements = 0 → label_risque=1 ; mode=INCONNU → taux=100 %",
        "signal_column": "nb_reglements",
    },
    {
        "nom": "Retard de paiement grave",
        "description": (
            "Retard supérieur à 30 jours sur au moins un règlement. "
            "Critère direct de label_risque=1."
        ),
        "seuils": "retard_max_jours > 30 → label_risque=1",
        "signal_column": "retard_max_jours",
    },
    {
        "nom": "Taux de retard élevé",
        "description": (
            "Plus de 50 % des paiements effectués en retard. "
            "Critère direct de label_risque=1."
        ),
        "seuils": "taux_retard > 0.5 → label_risque=1",
        "signal_column": "taux_retard",
    },
    {
        "nom": "Contagion réseau",
        "description": (
            "Risque propagé via le réseau de clients partageant "
            "le même gouvernorat ou le même responsable commercial. "
            "Capturé par le score_contagion du modèle GraphSAGE (M2)."
        ),
        "seuils": "score_contagion > 50 → contribution significative au score_final_m2",
        "signal_column": "score_contagion",
    },
    {
        "nom": "Faible encaissement",
        "description": (
            "Montant total réglé très inférieur au montant facturé. "
            "Signal d'alerte de solvabilité."
        ),
        "seuils": "ratio_encaissement < 0.5 → signal d'alerte",
        "signal_column": "ratio_encaissement",
    },
    {
        "nom": "Segment haute exposition",
        "description": (
            "Segments commerciaux présentant un taux de défaut "
            "historiquement supérieur à la moyenne (5.1 %). "
            "GEM/DET/STEG → 100 % ; GMS/GRO → 50 % ; EXPORT → 83 %."
        ),
        "seuils": "taux_risque_segment > 0.05",
        "signal_column": "nature_client_code",
    },
    {
        "nom": "Zone géographique à risque",
        "description": (
            "Gouvernorats avec taux de défaut supérieur à la moyenne nationale (5.1 %). "
            "EXPORT 83 % ; TATAOUINE 10 % ; ARIANA 9.5 % ; BIZERTE 8.2 %."
        ),
        "seuils": "taux_risque_gouvernorat > 0.05",
        "signal_column": "gouvernorat_code",
    },
    {
        "nom": "Client récent",
        "description": (
            "Ancienneté faible — historique insuffisant pour une évaluation fiable. "
            "Médiane du portefeuille : 673 jours."
        ),
        "seuils": "anciennete_jours < 180",
        "signal_column": "anciennete_jours",
    },
]

REGLES = [
    {
        "regle_id": "R01",
        "description": "label_risque = 1 si aucun règlement (nb_reglements = 0)",
        "condition_cypher": "c.nb_reglements = 0",
        "action": "label_risque = 1",
        "source": "M1/nettoyer_data.py:L122",
        "concepts": ["Absence de règlement"],
    },
    {
        "regle_id": "R02",
        "description": "label_risque = 1 si retard max > 30 jours",
        "condition_cypher": "c.retard_max_jours > 30",
        "action": "label_risque = 1",
        "source": "M1/nettoyer_data.py:L123",
        "concepts": ["Retard de paiement grave"],
    },
    {
        "regle_id": "R03",
        "description": "label_risque = 1 si taux_retard > 50 %",
        "condition_cypher": "c.taux_retard > 0.5",
        "action": "label_risque = 1",
        "source": "M1/nettoyer_data.py:L124",
        "concepts": ["Taux de retard élevé"],
    },
    {
        "regle_id": "R04",
        "description": "Alerte ROUGE si score_final_m2 > 70",
        "condition_cypher": "c.score_final_m2 > 70",
        "action": "alerte = ROUGE",
        "source": "M2/m2_gnn.py:L349",
        "concepts": [],
    },
    {
        "regle_id": "R05",
        "description": "Alerte ORANGE si 30 ≤ score_final_m2 ≤ 70",
        "condition_cypher": "c.score_final_m2 >= 30 AND c.score_final_m2 <= 70",
        "action": "alerte = ORANGE",
        "source": "M2/m2_gnn.py:L349",
        "concepts": [],
    },
    {
        "regle_id": "R06",
        "description": "score_final_m2 = 0.7 × score_gnn + 0.3 × score_contagion",
        "condition_cypher": None,
        "action": "score_final_m2 = 0.7*score_gnn + 0.3*score_contagion",
        "source": "M2/m2_gnn.py:L344",
        "concepts": ["Contagion réseau"],
    },
]

# ─── Chargement des données ─────────────────────────────────────────────────

def _find_file(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Aucun fichier trouvé parmi : {[str(p) for p in candidates]}"
    )


def load_data(data_path: Path) -> pd.DataFrame:
    """Charge et fusionne combined CSV + M2 scores + responsables (si dispo)."""

    combined_path = _find_file([
        data_path / "dataset_combined_real_synth.csv",
        Path("dataset_combined_real_synth.csv"),
    ])
    scores_path = _find_file([
        data_path / "m2_gnn_scores.csv",
        Path("m2_gnn_scores.csv"),
    ])

    log.info("Lecture %s", combined_path)
    df = pd.read_csv(combined_path)
    log.info("  → %d lignes, %d colonnes", *df.shape)

    log.info("Lecture %s", scores_path)
    scores = pd.read_csv(scores_path)[
        ["client_index", "score_gnn", "score_contagion", "score_final_m2", "alerte"]
    ]
    df.index = range(len(df))   # index entier garanti avant le merge
    df = df.merge(scores, left_index=True, right_on="client_index", how="left")
    df["client_index"] = df["client_index"].astype(int)

    # Identifiants
    df["client_id"] = df["client_index"].apply(
        lambda i: f"R_{i}" if i < N_REAL else f"S_{i}"
    )
    df["source"] = df["client_index"].apply(
        lambda i: "REEL" if i < N_REAL else "SYNTHETIQUE"
    )

    # Responsables : depuis le Excel nettoyé si disponible
    excel_candidates = [
        data_path / "SolvAI_Dataset_Nettoye.xlsx",
        Path("SolvAI_Dataset_Nettoye.xlsx"),
    ]
    try:
        excel_path = _find_file(excel_candidates)
        log.info("Lecture responsables depuis %s", excel_path)
        df_excel = pd.ExcelFile(excel_path).parse(
            "clients_features", usecols=["code_responsable"]
        )
        df_excel["code_responsable"] = (
            df_excel["code_responsable"].astype(str).str.strip()
        )
        df.loc[df["client_index"] < N_REAL, "code_responsable"] = (
            df_excel["code_responsable"].values
        )
    except FileNotFoundError:
        log.warning("SolvAI_Dataset_Nettoye.xlsx non trouvé — "
                    "arêtes CONTAGION_PORTEFEUILLE désactivées")
        df["code_responsable"] = None

    # Noms décodés (pour propriétés lisibles sur les nœuds Client)
    df["gouvernorat_nom"]  = df["gouvernorat_code"].map(lambda c: GOUVERNORAT.get(c, ("?",))[0])
    df["segment_nom"]      = df["nature_client_code"].map(lambda c: SEGMENT.get(c, ("?",))[0])
    df["mode_mnemonique"]  = df["mode_paiement_code"].map(lambda c: MODE_PAIEMENT.get(c, ("?",))[0])

    # Scores par défaut si M2 absent
    for col in ["score_gnn", "score_contagion", "score_final_m2"]:
        df[col] = df[col].fillna(0.0).round(2)
    df["alerte"] = df["alerte"].fillna("VERT")

    log.info("Dataset prêt : %d clients (%d réels, %d synthétiques)",
             len(df), (df.source == "REEL").sum(), (df.source == "SYNTHETIQUE").sum())
    return df


# ─── Neo4j Loader ──────────────────────────────────────────────────────────────

class Neo4jLoader:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _run(self, session, query: str, **params):
        return session.run(query, **params)

    def _batch(self, session, query: str, rows: list[dict], desc: str):
        for start in tqdm(range(0, len(rows), BATCH_SIZE), desc=desc, unit="batch"):
            batch = rows[start : start + BATCH_SIZE]
            session.run(query, batch=batch)

    # ── Schéma ───────────────────────────────────────────────────────────────

    def apply_schema(self):
        constraints = [
            "CREATE CONSTRAINT client_id       IF NOT EXISTS FOR (c:Client)        REQUIRE c.client_id    IS UNIQUE",
            "CREATE CONSTRAINT gouvernorat_nom  IF NOT EXISTS FOR (g:Gouvernorat)   REQUIRE g.nom          IS UNIQUE",
            "CREATE CONSTRAINT segment_nom      IF NOT EXISTS FOR (s:SegmentClient) REQUIRE s.nom          IS UNIQUE",
            "CREATE CONSTRAINT mode_mnemonique  IF NOT EXISTS FOR (m:ModePaiement)  REQUIRE m.mnemonique   IS UNIQUE",
            "CREATE CONSTRAINT commercial_code  IF NOT EXISTS FOR (r:Commercial)    REQUIRE r.code         IS UNIQUE",
            "CREATE CONSTRAINT alerte_niveau    IF NOT EXISTS FOR (a:AlerteRisque)  REQUIRE a.niveau       IS UNIQUE",
            "CREATE CONSTRAINT concept_nom      IF NOT EXISTS FOR (k:ConceptRisque) REQUIRE k.nom          IS UNIQUE",
            "CREATE CONSTRAINT regle_id         IF NOT EXISTS FOR (r:RegleDecision) REQUIRE r.regle_id     IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX client_label    IF NOT EXISTS FOR (c:Client) ON (c.label_risque)",
            "CREATE INDEX client_score    IF NOT EXISTS FOR (c:Client) ON (c.score_final_m2)",
            "CREATE INDEX client_alerte   IF NOT EXISTS FOR (c:Client) ON (c.alerte)",
            "CREATE INDEX client_anciennete IF NOT EXISTS FOR (c:Client) ON (c.anciennete_jours)",
            "CREATE INDEX client_taux     IF NOT EXISTS FOR (c:Client) ON (c.taux_retard)",
            "CREATE INDEX client_source   IF NOT EXISTS FOR (c:Client) ON (c.source)",
            "CREATE INDEX gouvernorat_code IF NOT EXISTS FOR (g:Gouvernorat) ON (g.code)",
            "CREATE INDEX segment_code    IF NOT EXISTS FOR (s:SegmentClient) ON (s.code)",
        ]
        fulltext = [
            ("CREATE FULLTEXT INDEX concept_text IF NOT EXISTS "
             "FOR (k:ConceptRisque) ON EACH [k.nom, k.description, k.seuils]"),
            ("CREATE FULLTEXT INDEX regle_text IF NOT EXISTS "
             "FOR (r:RegleDecision) ON EACH [r.regle_id, r.description, r.condition_cypher]"),
        ]
        with self._driver.session() as s:
            for q in constraints + indexes + fulltext:
                s.run(q)
        log.info("Schéma appliqué (%d contraintes, %d index, 2 fulltext)",
                 len(constraints), len(indexes))

    # ── Wipe ─────────────────────────────────────────────────────────────────

    def wipe(self):
        with self._driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        log.info("Graphe vidé")

    # ── Couche 1 : nœuds de référence ────────────────────────────────────────

    def ingest_reference_nodes(self, df: pd.DataFrame):
        with self._driver.session() as s:

            # Gouvernorat
            gouv_rows = [
                {
                    "code": code,
                    "nom":    nom,
                    "region": region,
                    "nb_clients": int((df.gouvernorat_code == code).sum()),
                    "taux_risque": round(
                        df.loc[df.gouvernorat_code == code, "label_risque"].mean() or 0.0, 4
                    ),
                }
                for code, (nom, region) in GOUVERNORAT.items()
            ]
            s.run(
                "UNWIND $batch AS r "
                "MERGE (g:Gouvernorat {nom: r.nom}) "
                "SET g.code = r.code, g.region = r.region, "
                "    g.nb_clients = r.nb_clients, g.taux_risque = r.taux_risque",
                batch=gouv_rows,
            )
            log.info("  Gouvernorat : %d nœuds", len(gouv_rows))

            # SegmentClient
            seg_rows = [
                {
                    "code": code,
                    "nom":     nom,
                    "famille": famille,
                    "nb_clients": int((df.nature_client_code == code).sum()),
                    "taux_risque": round(
                        df.loc[df.nature_client_code == code, "label_risque"].mean() or 0.0, 4
                    ),
                }
                for code, (nom, famille) in SEGMENT.items()
            ]
            s.run(
                "UNWIND $batch AS r "
                "MERGE (s:SegmentClient {nom: r.nom}) "
                "SET s.code = r.code, s.famille = r.famille, "
                "    s.nb_clients = r.nb_clients, s.taux_risque = r.taux_risque",
                batch=seg_rows,
            )
            log.info("  SegmentClient : %d nœuds", len(seg_rows))

            # ModePaiement
            mode_rows = [
                {
                    "code":      code,
                    "mnemonique": mnem,
                    "libelle":   libelle,
                    "nb_clients": int((df.mode_paiement_code == code).sum()),
                    "taux_risque": round(
                        df.loc[df.mode_paiement_code == code, "label_risque"].mean() or 0.0, 4
                    ),
                }
                for code, (mnem, libelle) in MODE_PAIEMENT.items()
            ]
            s.run(
                "UNWIND $batch AS r "
                "MERGE (m:ModePaiement {mnemonique: r.mnemonique}) "
                "SET m.code = r.code, m.libelle = r.libelle, "
                "    m.nb_clients = r.nb_clients, m.taux_risque = r.taux_risque",
                batch=mode_rows,
            )
            log.info("  ModePaiement : %d nœuds", len(mode_rows))

            # Commercial (uniquement les clients réels avec responsable connu)
            resp_series = df.loc[
                (df.source == "REEL") & df.code_responsable.notna(), "code_responsable"
            ]
            resp_groups = df.loc[resp_series.index].groupby("code_responsable")
            resp_rows = [
                {
                    "code": str(code).strip(),
                    "nb_clients": int(grp.shape[0]),
                    "taux_risque": round(grp["label_risque"].mean(), 4),
                }
                for code, grp in resp_groups
                if str(code).strip()
            ]
            if resp_rows:
                s.run(
                    "UNWIND $batch AS r "
                    "MERGE (c:Commercial {code: r.code}) "
                    "SET c.nb_clients = r.nb_clients, c.taux_risque = r.taux_risque",
                    batch=resp_rows,
                )
            log.info("  Commercial : %d nœuds", len(resp_rows))

            # AlerteRisque (3 nœuds fixes)
            s.run(
                "UNWIND [{niveau:'VERT',smin:0,smax:30},"
                "        {niveau:'ORANGE',smin:30,smax:70},"
                "        {niveau:'ROUGE',smin:70,smax:100}] AS r "
                "MERGE (a:AlerteRisque {niveau: r.niveau}) "
                "SET a.seuil_min = r.smin, a.seuil_max = r.smax"
            )
            log.info("  AlerteRisque : 3 nœuds")

    # ── Couche 3 : knowledge base ─────────────────────────────────────────────

    def ingest_knowledge_base(self):
        with self._driver.session() as s:
            # ConceptRisque
            s.run(
                "UNWIND $batch AS r "
                "MERGE (k:ConceptRisque {nom: r.nom}) "
                "SET k.description = r.description, "
                "    k.seuils = r.seuils, "
                "    k.signal_column = r.signal_column",
                batch=CONCEPTS,
            )
            log.info("  ConceptRisque : %d nœuds", len(CONCEPTS))

            # RegleDecision
            regle_rows = [
                {k: v for k, v in r.items() if k != "concepts"}
                for r in REGLES
            ]
            s.run(
                "UNWIND $batch AS r "
                "MERGE (rd:RegleDecision {regle_id: r.regle_id}) "
                "SET rd.description = r.description, "
                "    rd.condition_cypher = r.condition_cypher, "
                "    rd.action = r.action, "
                "    rd.source = r.source",
                batch=regle_rows,
            )
            log.info("  RegleDecision : %d nœuds", len(regle_rows))

            # (ConceptRisque)-[:DEFINI_PAR]->(RegleDecision)
            for regle in REGLES:
                for concept_nom in regle["concepts"]:
                    s.run(
                        "MATCH (k:ConceptRisque {nom: $cn}), "
                        "      (r:RegleDecision {regle_id: $rid}) "
                        "MERGE (k)-[:DEFINI_PAR]->(r)",
                        cn=concept_nom, rid=regle["regle_id"],
                    )

            # Liens sémantiques : SegmentClient → ConceptRisque (segments à risque élevé)
            HIGH_RISK_SEGMENTS = {"GEM", "DET", "STEG", "GMS", "GRO", "EXPORT"}
            for code, (nom, _) in SEGMENT.items():
                if nom in HIGH_RISK_SEGMENTS:
                    s.run(
                        "MATCH (seg:SegmentClient {nom: $nom}), "
                        "      (k:ConceptRisque {nom: 'Segment haute exposition'}) "
                        "MERGE (seg)-[:ASSOCIE_AU_CONCEPT]->(k)",
                        nom=nom,
                    )

            # Liens sémantiques : ModePaiement → ConceptRisque
            s.run(
                "MATCH (m:ModePaiement {mnemonique: 'INCONNU'}), "
                "      (k:ConceptRisque {nom: 'Absence de règlement'}) "
                "MERGE (m)-[:SIGNAL_DE]->(k)"
            )
            s.run(
                "MATCH (m:ModePaiement {mnemonique: 'ETRT'}), "
                "      (k:ConceptRisque {nom: 'Retard de paiement grave'}) "
                "MERGE (m)-[:SIGNAL_DE]->(k)"
            )

            # Liens sémantiques : Gouvernorat → ConceptRisque (taux > moyenne)
            HIGH_RISK_GOUV = {
                "EXPORT", "TATAOUINE", "ARIANA", "BIZERTE",
                "MANNOUBA", "SOUSSE", "TUNIS", "KAIROUAN",
            }
            for _, (nom, _) in GOUVERNORAT.items():
                if nom in HIGH_RISK_GOUV:
                    s.run(
                        "MATCH (g:Gouvernorat {nom: $nom}), "
                        "      (k:ConceptRisque {nom: 'Zone géographique à risque'}) "
                        "MERGE (g)-[:ASSOCIE_AU_CONCEPT]->(k)",
                        nom=nom,
                    )

    # ── Client nodes ─────────────────────────────────────────────────────────

    def ingest_clients(self, df: pd.DataFrame):
        FLOAT_COLS = [
            "montant_ttc_total", "montant_ttc_moyen", "montant_ttc_max", "montant_ttc_std",
            "ratio_avoirs", "montant_reg_total", "montant_reg_moyen",
            "retard_moyen_jours", "retard_max_jours", "taux_retard",
            "ratio_encaissement", "score_gnn", "score_contagion", "score_final_m2",
        ]
        INT_COLS = [
            "nb_factures", "nb_avoirs", "anciennete_jours", "nb_reglements",
            "nb_retards_positifs", "nb_retards_graves", "nb_modes_distincts",
            "gouvernorat_code", "nature_client_code", "mode_paiement_code", "label_risque",
        ]

        def _row(r):
            row = {
                "client_id":         r["client_id"],
                "source":            r["source"],
                "gouvernorat_nom":   r["gouvernorat_nom"],
                "segment_nom":       r["segment_nom"],
                "mode_mnemonique":   r["mode_mnemonique"],
                "alerte":            r["alerte"],
            }
            for c in FLOAT_COLS:
                v = r.get(c, 0.0)
                row[c] = float(v) if pd.notna(v) else 0.0
            for c in INT_COLS:
                v = r.get(c, 0)
                row[c] = int(v) if pd.notna(v) else 0
            resp = r.get("code_responsable")
            row["code_responsable"] = str(resp).strip() if pd.notna(resp) else None
            return row

        rows = [_row(r) for _, r in df.iterrows()]

        query = (
            "UNWIND $batch AS r "
            "MERGE (c:Client {client_id: r.client_id}) "
            "SET c.source              = r.source, "
            "    c.gouvernorat_nom     = r.gouvernorat_nom, "
            "    c.segment_nom         = r.segment_nom, "
            "    c.mode_mnemonique     = r.mode_mnemonique, "
            "    c.alerte              = r.alerte, "
            "    c.nb_factures         = r.nb_factures, "
            "    c.montant_ttc_total   = r.montant_ttc_total, "
            "    c.montant_ttc_moyen   = r.montant_ttc_moyen, "
            "    c.montant_ttc_max     = r.montant_ttc_max, "
            "    c.montant_ttc_std     = r.montant_ttc_std, "
            "    c.nb_avoirs           = r.nb_avoirs, "
            "    c.ratio_avoirs        = r.ratio_avoirs, "
            "    c.anciennete_jours    = r.anciennete_jours, "
            "    c.nb_reglements       = r.nb_reglements, "
            "    c.montant_reg_total   = r.montant_reg_total, "
            "    c.montant_reg_moyen   = r.montant_reg_moyen, "
            "    c.retard_moyen_jours  = r.retard_moyen_jours, "
            "    c.retard_max_jours    = r.retard_max_jours, "
            "    c.nb_retards_positifs = r.nb_retards_positifs, "
            "    c.nb_retards_graves   = r.nb_retards_graves, "
            "    c.taux_retard         = r.taux_retard, "
            "    c.nb_modes_distincts  = r.nb_modes_distincts, "
            "    c.ratio_encaissement  = r.ratio_encaissement, "
            "    c.gouvernorat_code    = r.gouvernorat_code, "
            "    c.nature_client_code  = r.nature_client_code, "
            "    c.mode_paiement_code  = r.mode_paiement_code, "
            "    c.label_risque        = r.label_risque, "
            "    c.score_gnn           = r.score_gnn, "
            "    c.score_contagion     = r.score_contagion, "
            "    c.score_final_m2      = r.score_final_m2, "
            "    c.code_responsable    = r.code_responsable"
        )
        with self._driver.session() as s:
            self._batch(s, query, rows, desc="Client nodes")
        log.info("  Client : %d nœuds créés/mis à jour", len(rows))

    # ── Relations clients → entités ───────────────────────────────────────────

    def ingest_client_relationships(self, df: pd.DataFrame):
        ids = df["client_id"].tolist()

        def rows_from_col(col_name):
            return [
                {"client_id": r["client_id"], "val": r[col_name]}
                for _, r in df[[col_name, "client_id"]].iterrows()
                if pd.notna(r[col_name])
            ]

        with self._driver.session() as s:

            # → Gouvernorat
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (c:Client {client_id: r.client_id}), "
                "      (g:Gouvernorat {nom: r.val}) "
                "MERGE (c)-[:SITUE_DANS]->(g)",
                rows_from_col("gouvernorat_nom"),
                desc="SITUE_DANS",
            )

            # → SegmentClient
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (c:Client {client_id: r.client_id}), "
                "      (s:SegmentClient {nom: r.val}) "
                "MERGE (c)-[:APPARTIENT_AU_SEGMENT]->(s)",
                rows_from_col("segment_nom"),
                desc="APPARTIENT_AU_SEGMENT",
            )

            # → ModePaiement
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (c:Client {client_id: r.client_id}), "
                "      (m:ModePaiement {mnemonique: r.val}) "
                "MERGE (c)-[:PAIE_VIA {nb_modes_distincts: 1}]->(m)",
                rows_from_col("mode_mnemonique"),
                desc="PAIE_VIA",
            )

            # → Commercial (réels uniquement)
            resp_rows = [
                {"client_id": r["client_id"], "code": str(r["code_responsable"]).strip()}
                for _, r in df.iterrows()
                if r["source"] == "REEL" and pd.notna(r.get("code_responsable"))
                and str(r.get("code_responsable", "")).strip()
            ]
            if resp_rows:
                self._batch(
                    s,
                    "UNWIND $batch AS r "
                    "MATCH (c:Client {client_id: r.client_id}), "
                    "      (com:Commercial {code: r.code}) "
                    "MERGE (c)-[:SUIVI_PAR]->(com)",
                    resp_rows,
                    desc="SUIVI_PAR",
                )

            # → AlerteRisque
            alerte_rows = [
                {
                    "client_id":       r["client_id"],
                    "niveau":          r["alerte"],
                    "score_gnn":       float(r["score_gnn"]),
                    "score_contagion": float(r["score_contagion"]),
                    "score_final_m2":  float(r["score_final_m2"]),
                }
                for _, r in df.iterrows()
            ]
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (c:Client {client_id: r.client_id}), "
                "      (a:AlerteRisque {niveau: r.niveau}) "
                "MERGE (c)-[rel:CLASSIFIE_COMME]->(a) "
                "SET rel.score_gnn        = r.score_gnn, "
                "    rel.score_contagion  = r.score_contagion, "
                "    rel.score_final_m2   = r.score_final_m2",
                alerte_rows,
                desc="CLASSIFIE_COMME",
            )

            # → ConceptRisque dynamique (clients vérifiant les seuils des règles)
            concept_rows = []
            for _, r in df.iterrows():
                concepts = []
                if r["nb_reglements"] == 0:
                    concepts.append("Absence de règlement")
                if r["retard_max_jours"] > 30:
                    concepts.append("Retard de paiement grave")
                if r["taux_retard"] > 0.5:
                    concepts.append("Taux de retard élevé")
                if r["score_contagion"] > 50:
                    concepts.append("Contagion réseau")
                if r["ratio_encaissement"] < 0.5 and r["nb_reglements"] > 0:
                    concepts.append("Faible encaissement")
                if r["anciennete_jours"] < 180:
                    concepts.append("Client récent")
                for c in concepts:
                    concept_rows.append({"client_id": r["client_id"], "concept": c})

            if concept_rows:
                self._batch(
                    s,
                    "UNWIND $batch AS r "
                    "MATCH (c:Client {client_id: r.client_id}), "
                    "      (k:ConceptRisque {nom: r.concept}) "
                    "MERGE (c)-[:PRESENTE]->(k)",
                    concept_rows,
                    desc="PRESENTE",
                )

        log.info("Relations client → entités créées")

    # ── Arêtes de contagion (réplique exacte du graphe M2) ───────────────────

    def ingest_contagion_edges(self, df: pd.DataFrame):
        """
        TERRITOIRE : clients du même gouvernorat, max 5 voisins en ordre d'index
        PORTEFEUILLE : clients du même responsable, max 3 voisins en ordre d'index
        Reproduit la logique de m2_gnn.py (L.82-96).
        """

        def build_edges(groups: dict, max_neighbors: int) -> list[dict]:
            edges = []
            for key, idx_list in groups.items():
                for i, src in enumerate(idx_list):
                    for dst in idx_list[i + 1 : i + 1 + max_neighbors]:
                        edges.append({"src": src, "dst": dst})
            return edges

        with self._driver.session() as s:

            # TERRITOIRE
            gouv_groups = (
                df.groupby("gouvernorat_code")["client_id"]
                .apply(list)
                .to_dict()
            )
            terr_edges = build_edges(gouv_groups, max_neighbors=5)
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (a:Client {client_id: r.src}), (b:Client {client_id: r.dst}) "
                "MERGE (a)-[:CONTAGION_TERRITOIRE]->(b) "
                "MERGE (b)-[:CONTAGION_TERRITOIRE]->(a)",
                terr_edges,
                desc="CONTAGION_TERRITOIRE",
            )
            log.info("  CONTAGION_TERRITOIRE : %d paires", len(terr_edges))

            # PORTEFEUILLE (réels uniquement)
            real_resp = df[
                (df.source == "REEL") & df.code_responsable.notna()
                & (df.code_responsable.astype(str).str.strip() != "")
            ]
            if real_resp.empty:
                log.warning("  CONTAGION_PORTEFEUILLE : ignorée (pas de responsables)")
                return

            resp_groups = (
                real_resp.groupby(real_resp.code_responsable.astype(str).str.strip())["client_id"]
                .apply(list)
                .to_dict()
            )
            port_edges = build_edges(resp_groups, max_neighbors=3)
            self._batch(
                s,
                "UNWIND $batch AS r "
                "MATCH (a:Client {client_id: r.src}), (b:Client {client_id: r.dst}) "
                "MERGE (a)-[:CONTAGION_PORTEFEUILLE]->(b) "
                "MERGE (b)-[:CONTAGION_PORTEFEUILLE]->(a)",
                port_edges,
                desc="CONTAGION_PORTEFEUILLE",
            )
            log.info("  CONTAGION_PORTEFEUILLE : %d paires", len(port_edges))

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self):
        checks = [
            ("Nœuds par label",
             "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total "
             "ORDER BY total DESC"),
            ("Relations par type",
             "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS total "
             "ORDER BY total DESC"),
            ("Alertes ROUGE",
             "MATCH (c:Client)-[:CLASSIFIE_COMME]->(a:AlerteRisque {niveau:'ROUGE'}) "
             "RETURN count(c) AS rouge"),
            ("Clients ROUGE dans SFAX",
             "MATCH (c:Client {alerte:'ROUGE'})-[:SITUE_DANS]->(g:Gouvernorat {nom:'SFAX'}) "
             "RETURN count(c) AS rouge_sfax"),
            ("Concepts les plus présents",
             "MATCH (c:Client)-[:PRESENTE]->(k:ConceptRisque) "
             "RETURN k.nom, count(c) AS n ORDER BY n DESC"),
        ]
        print("\n" + "═" * 60)
        print("  VALIDATION")
        print("═" * 60)
        with self._driver.session() as s:
            for title, query in checks:
                print(f"\n── {title} ──")
                for record in s.run(query):
                    print("  ", dict(record))

    # ── Orchestrateur principal ───────────────────────────────────────────────

    def run(self, df: pd.DataFrame, wipe: bool = False, no_contagion: bool = False):
        if wipe:
            self.wipe()

        log.info("=== Étape 1/5 : Schéma ===")
        self.apply_schema()

        log.info("=== Étape 2/5 : Nœuds de référence ===")
        self.ingest_reference_nodes(df)

        log.info("=== Étape 3/5 : Knowledge base ===")
        self.ingest_knowledge_base()

        log.info("=== Étape 4/5 : Clients (%d nœuds) ===", len(df))
        self.ingest_clients(df)

        log.info("=== Étape 4b/5 : Relations clients ===")
        self.ingest_client_relationships(df)

        if not no_contagion:
            log.info("=== Étape 5/5 : Arêtes de contagion ===")
            self.ingest_contagion_edges(df)
        else:
            log.info("=== Étape 5/5 : Arêtes de contagion (ignorées) ===")

        self.validate()


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CreditMind M6 — Ingestion Neo4j")
    parser.add_argument("--data-path",    default=str(DATA_PATH), help="Dossier des CSV/Excel")
    parser.add_argument("--wipe",         action="store_true",    help="Vider le graphe avant ingestion")
    parser.add_argument("--no-contagion", action="store_true",    help="Ignorer les arêtes de contagion")
    parser.add_argument("--neo4j-uri",    default=NEO4J_URI)
    parser.add_argument("--neo4j-user",   default=NEO4J_USER)
    parser.add_argument("--neo4j-password", default=NEO4J_PASSWORD)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    df = load_data(Path(args.data_path))

    with Neo4jLoader(args.neo4j_uri, args.neo4j_user, args.neo4j_password) as loader:
        loader.run(df, wipe=args.wipe, no_contagion=args.no_contagion)

    log.info("Ingestion terminée.")


if __name__ == "__main__":
    main()
