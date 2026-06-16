// ═══════════════════════════════════════════════════════════════════════════
//  CreditMind M6 — Schéma Neo4j
//  3 couches : données métier · classification risque · concepts GraphRAG
// ═══════════════════════════════════════════════════════════════════════════

// ── CONTRAINTES D'UNICITÉ ───────────────────────────────────────────────────

CREATE CONSTRAINT client_id         IF NOT EXISTS FOR (c:Client)        REQUIRE c.client_id         IS UNIQUE;
CREATE CONSTRAINT gouvernorat_nom   IF NOT EXISTS FOR (g:Gouvernorat)   REQUIRE g.nom               IS UNIQUE;
CREATE CONSTRAINT segment_nom       IF NOT EXISTS FOR (s:SegmentClient) REQUIRE s.nom               IS UNIQUE;
CREATE CONSTRAINT mode_mnemonique   IF NOT EXISTS FOR (m:ModePaiement)  REQUIRE m.mnemonique        IS UNIQUE;
CREATE CONSTRAINT commercial_code   IF NOT EXISTS FOR (r:Commercial)    REQUIRE r.code              IS UNIQUE;
CREATE CONSTRAINT alerte_niveau     IF NOT EXISTS FOR (a:AlerteRisque)  REQUIRE a.niveau            IS UNIQUE;
CREATE CONSTRAINT concept_nom       IF NOT EXISTS FOR (k:ConceptRisque) REQUIRE k.nom               IS UNIQUE;
CREATE CONSTRAINT regle_id          IF NOT EXISTS FOR (r:RegleDecision) REQUIRE r.regle_id          IS UNIQUE;

// ── INDEX DE PERFORMANCE ────────────────────────────────────────────────────

CREATE INDEX client_label_risque   IF NOT EXISTS FOR (c:Client) ON (c.label_risque);
CREATE INDEX client_score_final    IF NOT EXISTS FOR (c:Client) ON (c.score_final_m2);
CREATE INDEX client_alerte         IF NOT EXISTS FOR (c:Client) ON (c.alerte);
CREATE INDEX client_anciennete     IF NOT EXISTS FOR (c:Client) ON (c.anciennete_jours);
CREATE INDEX client_taux_retard    IF NOT EXISTS FOR (c:Client) ON (c.taux_retard);
CREATE INDEX gouvernorat_code      IF NOT EXISTS FOR (g:Gouvernorat) ON (g.code);
CREATE INDEX segment_code          IF NOT EXISTS FOR (s:SegmentClient) ON (s.code);

// ── INDEX FULLTEXT (pour GraphRAG / LlamaIndex) ─────────────────────────────

CREATE FULLTEXT INDEX concept_text IF NOT EXISTS
  FOR (k:ConceptRisque) ON EACH [k.nom, k.description, k.seuils];

CREATE FULLTEXT INDEX regle_text   IF NOT EXISTS
  FOR (r:RegleDecision) ON EACH [r.regle_id, r.description, r.condition_cypher];

// ═══════════════════════════════════════════════════════════════════════════
//  COUCHE 1 — ENTITÉS MÉTIER
// ═══════════════════════════════════════════════════════════════════════════

// ── Nœud :Client ────────────────────────────────────────────────────────────
// Un nœud par client (21 637 = 1 637 réels + 20 000 synthétiques)
//
// MERGE (:Client {
//   client_id           : STRING,   // CODE_CLIENT (réels) ou "SYN_<i>" (synthétiques)
//   source              : STRING,   // "REEL" | "SYNTHETIQUE"
//   code_responsable    : INTEGER,
//
//   // ── Features factures ──
//   nb_factures         : INTEGER,
//   montant_ttc_total   : FLOAT,    // TND
//   montant_ttc_moyen   : FLOAT,
//   montant_ttc_max     : FLOAT,
//   montant_ttc_std     : FLOAT,
//   nb_avoirs           : INTEGER,
//   ratio_avoirs        : FLOAT,    // [0,1]
//   anciennete_jours    : INTEGER,
//
//   // ── Features règlements ──
//   nb_reglements       : INTEGER,
//   montant_reg_total   : FLOAT,
//   montant_reg_moyen   : FLOAT,
//   retard_moyen_jours  : FLOAT,
//   retard_max_jours    : FLOAT,    // >30 = retard grave
//   nb_retards_positifs : INTEGER,
//   nb_retards_graves   : INTEGER,
//   taux_retard         : FLOAT,    // [0,1]  >0.5 = à risque
//   nb_modes_distincts  : INTEGER,
//   ratio_encaissement  : FLOAT,    // montant_reg / montant_ttc
//
//   // ── Codes catégoriels (redondants avec relations, utiles pour GDS) ──
//   gouvernorat_code    : INTEGER,
//   nature_client_code  : INTEGER,
//   mode_paiement_code  : INTEGER,
//
//   // ── Labels et scores ──
//   label_risque        : INTEGER,  // 0=solvable | 1=à risque  (M1 règle métier)
//   score_gnn           : FLOAT,    // [0,100]  sortie GraphSAGE (M2)
//   score_contagion     : FLOAT,    // [0,100]  propagation réseau (M2)
//   score_final_m2      : FLOAT,    // [0,100]  0.7*score_gnn + 0.3*score_contagion
//   alerte              : STRING    // "VERT" | "ORANGE" | "ROUGE"
// })

// ── Nœud :Gouvernorat ───────────────────────────────────────────────────────
// 25 nœuds — 24 gouvernorats tunisiens + "EXPORT"
//
// MERGE (:Gouvernorat {
//   code            : INTEGER,   // encodage alphabétique (0=ARIANA … 24=ZAGHOUAN)
//   nom             : STRING,    // "SFAX", "TUNIS", …
//   nb_clients      : INTEGER,   // calculé à l'ingestion
//   taux_risque     : FLOAT,     // nb_risque / nb_clients
//   region          : STRING     // "NORD" | "CENTRE" | "SUD" | "GRAND_TUNIS" | "EXPORT"
// })

// ── Nœud :SegmentClient ─────────────────────────────────────────────────────
// 23 nœuds — portefeuilles commerciaux internes
//
// MERGE (:SegmentClient {
//   code            : INTEGER,
//   nom             : STRING,    // "OUTSIDER", "GRN", "CHALLENGERD", …
//   nb_clients      : INTEGER,
//   taux_risque     : FLOAT,
//   famille         : STRING     // "CHALLENGER" | "GRAND_COMPTE" | "EXPORT" | "AUTRE"
// })
//
// Familles déduites :
//   CHALLENGER  → CHALLENGERA/B/C/D
//   GRAND_COMPTE→ GRN, GRO, GEM, GMS, PREMIUM
//   EXPORT      → EXPORT, EXPORTINDIRECT
//   PUBLIC      → ETATIQUE, STEG, PERSONNEL
//   AUTRE       → OUTSIDER, PAN, SCN, SPN, PAN, ALFAPACK, DET, MCN, NEGOCE, PHN

// ── Nœud :ModePaiement ──────────────────────────────────────────────────────
// 9 nœuds (8 codes + INCONNU)
//
// MERGE (:ModePaiement {
//   code            : INTEGER,   // -1 pour INCONNU
//   mnemonique      : STRING,    // "ETRT", "ECAI", …
//   libelle         : STRING,    // "Effet Traite", "Encaissement Caisse", …
//   nb_utilisations : INTEGER,   // lignes dans reglements_clean
//   taux_risque     : FLOAT      // calculé sur clients dominants
// })
//
// Libellés décodés :
//   DCHQ  → "Dépôt Chèque"
//   DTRT  → "Dépôt Traite"
//   ECAI  → "Encaissement Caisse"
//   ECHQ  → "Encaissement Chèque"
//   ERET  → "Effet Retour"
//   ETRC  → "Effet Traite / Crédit documentaire"
//   ETRT  → "Effet Traite"
//   EVIRL → "Encaissement Virement"
//   INCONNU → "Mode inconnu (aucun règlement)"

// ── Nœud :Commercial ────────────────────────────────────────────────────────
// 22 nœuds — responsables commerciaux
//
// MERGE (:Commercial {
//   code            : INTEGER,
//   nb_clients      : INTEGER,
//   taux_risque     : FLOAT
// })

// ═══════════════════════════════════════════════════════════════════════════
//  COUCHE 2 — CLASSIFICATION RISQUE (sortie M2)
// ═══════════════════════════════════════════════════════════════════════════

// ── Nœud :AlerteRisque ──────────────────────────────────────────────────────
// 3 nœuds fixes
//
// MERGE (:AlerteRisque { niveau: "VERT",   seuil_min: 0,  seuil_max: 30  })
// MERGE (:AlerteRisque { niveau: "ORANGE", seuil_min: 30, seuil_max: 70  })
// MERGE (:AlerteRisque { niveau: "ROUGE",  seuil_min: 70, seuil_max: 100 })

// ═══════════════════════════════════════════════════════════════════════════
//  COUCHE 3 — KNOWLEDGE BASE (pour GraphRAG / LlamaIndex)
// ═══════════════════════════════════════════════════════════════════════════

// ── Nœud :ConceptRisque ─────────────────────────────────────────────────────
// Concepts métier indexés pour la récupération RAG
//
// Exemples :
// { nom: "Absence de règlement",
//   description: "Client sans aucun règlement enregistré. Indicateur fort de non-paiement.",
//   seuils: "nb_reglements = 0 → label_risque=1, mode=INCONNU → taux_risque=100%",
//   signal_column: "nb_reglements" }
//
// { nom: "Retard de paiement grave",
//   description: "Retard supérieur à 30 jours sur au moins un règlement.",
//   seuils: "retard_max_jours > 30 → label_risque=1",
//   signal_column: "retard_max_jours" }
//
// { nom: "Taux de retard élevé",
//   description: "Plus de 50% des paiements effectués en retard.",
//   seuils: "taux_retard > 0.5 → label_risque=1",
//   signal_column: "taux_retard" }
//
// { nom: "Contagion réseau",
//   description: "Risque propagé via le réseau de clients partageant un même gouvernorat ou responsable.",
//   seuils: "score_contagion > 50 → contribution significative au score_final_m2",
//   signal_column: "score_contagion" }
//
// { nom: "Faible encaissement",
//   description: "Montant total réglé très inférieur au montant facturé.",
//   seuils: "ratio_encaissement < 0.5 → signal d'alerte",
//   signal_column: "ratio_encaissement" }
//
// { nom: "Segment haute exposition",
//   description: "Segments commerciaux présentant un taux de défaut historiquement élevé.",
//   seuils: "GEM/DET/STEG → 100% risque | GMS/GRO → 50% | EXPORT → 83%",
//   signal_column: "nature_client_code" }
//
// { nom: "Zone géographique à risque",
//   description: "Gouvernorats avec taux de défaut supérieur à la moyenne (5.1%).",
//   seuils: "EXPORT 83% | TATAOUINE 10% | ARIANA 9.5% | BIZERTE 8.2%",
//   signal_column: "gouvernorat_code" }
//
// { nom: "Client récent",
//   description: "Ancienneté faible, historique limité pour évaluation fiable.",
//   seuils: "anciennete_jours < 180 → données insuffisantes",
//   signal_column: "anciennete_jours" }

// ── Nœud :RegleDecision ─────────────────────────────────────────────────────
//
// { regle_id: "R01",
//   description: "Label risque = 1 si aucun règlement (nb_reglements=0)",
//   condition_cypher: "c.nb_reglements = 0",
//   action: "label_risque=1",
//   source: "M1-nettoyer_data.py:L122" }
//
// { regle_id: "R02",
//   description: "Label risque = 1 si retard max > 30 jours",
//   condition_cypher: "c.retard_max_jours > 30",
//   action: "label_risque=1",
//   source: "M1-nettoyer_data.py:L123" }
//
// { regle_id: "R03",
//   description: "Label risque = 1 si plus de 50% des paiements en retard",
//   condition_cypher: "c.taux_retard > 0.5",
//   action: "label_risque=1",
//   source: "M1-nettoyer_data.py:L124" }
//
// { regle_id: "R04",
//   description: "Alerte ROUGE si score_final_m2 > 70",
//   condition_cypher: "c.score_final_m2 > 70",
//   action: "alerte=ROUGE",
//   source: "M2-m2_gnn.py:L349" }
//
// { regle_id: "R05",
//   description: "Alerte ORANGE si 30 <= score_final_m2 <= 70",
//   condition_cypher: "c.score_final_m2 >= 30 AND c.score_final_m2 <= 70",
//   action: "alerte=ORANGE",
//   source: "M2-m2_gnn.py:L349" }
//
// { regle_id: "R06",
//   description: "Score final M2 = 0.7 × score_gnn + 0.3 × score_contagion",
//   condition_cypher: null,
//   action: "score_final_m2 = 0.7*score_gnn + 0.3*score_contagion",
//   source: "M2-m2_gnn.py:L344" }

// ═══════════════════════════════════════════════════════════════════════════
//  RELATIONS
// ═══════════════════════════════════════════════════════════════════════════

// ── Couche 1 : données ──────────────────────────────────────────────────────

// (Client)-[:SITUE_DANS]->(Gouvernorat)
// Propriétés : aucune (déterministe — un client, un gouvernorat)

// (Client)-[:APPARTIENT_AU_SEGMENT]->(SegmentClient)
// Propriétés : aucune

// (Client)-[:PAIE_VIA]->(ModePaiement)
// Propriétés : { nb_modes_distincts: INTEGER }  // indique la diversité d'usage

// (Client)-[:SUIVI_PAR]->(Commercial)
// Propriétés : aucune

// ── Couche 2 : classification ────────────────────────────────────────────────

// (Client)-[:CLASSIFIE_COMME]->(AlerteRisque)
// Propriétés : {
//   score_gnn        : FLOAT,
//   score_contagion  : FLOAT,
//   score_final_m2   : FLOAT
// }

// ── Couche 2 : contagion réseau (graphe M2) ──────────────────────────────────
//
// Ces arêtes reproduisent le graphe construit dans m2_gnn.py pour le GNN.
// Elles permettent des requêtes de propagation de risque en Cypher.
//
// (Client)-[:CONTAGION_TERRITOIRE {poids: FLOAT}]->(Client)
//   → Clients dans le même gouvernorat (max 5 voisins par client dans M2)
//   poids = score_contagion moyen des deux clients / 100
//
// (Client)-[:CONTAGION_PORTEFEUILLE {poids: FLOAT}]->(Client)
//   → Clients gérés par le même responsable commercial (max 3 voisins dans M2)
//   poids = score_contagion moyen / 100

// ── Couche 3 : knowledge base ────────────────────────────────────────────────

// (ConceptRisque)-[:DEFINI_PAR]->(RegleDecision)
//   Concept "Retard de paiement grave" → R01, R02

// (SegmentClient)-[:ASSOCIE_AU_CONCEPT {taux_risque: FLOAT}]->(ConceptRisque)
//   Segments à risque élevé liés au concept correspondant

// (Gouvernorat)-[:ASSOCIE_AU_CONCEPT {taux_risque: FLOAT}]->(ConceptRisque)
//   Gouvernorats à risque élevé → "Zone géographique à risque"

// (ModePaiement)-[:SIGNAL_DE]->(ConceptRisque)
//   INCONNU → "Absence de règlement"
//   ETRT    → "Retard de paiement grave"  (taux_risque 2.1%)

// (Client)-[:PRESENTE]->(ConceptRisque)
//   Relation optionnelle : client exemplifie un concept
//   Créée dynamiquement à l'ingestion pour les clients vérifiant les seuils

// ═══════════════════════════════════════════════════════════════════════════
//  REQUÊTES DE VALIDATION (à lancer après ingestion)
// ═══════════════════════════════════════════════════════════════════════════

// Combien de nœuds par label ?
// MATCH (n) RETURN labels(n)[0] AS label, count(n) AS total ORDER BY total DESC;

// Clients ROUGE dans le gouvernorat de Sfax
// MATCH (c:Client)-[:CLASSIFIE_COMME]->(a:AlerteRisque {niveau:"ROUGE"})
//       -[:SITUE_DANS]->(g:Gouvernorat {nom:"SFAX"})  -- incorrect, corriger :
// MATCH (c:Client)-[:CLASSIFIE_COMME]->(a:AlerteRisque {niveau:"ROUGE"}),
//       (c)-[:SITUE_DANS]->(g:Gouvernorat {nom:"SFAX"})
// RETURN count(c);

// Propagation de risque à 2 sauts depuis un client ROUGE
// MATCH path = (c:Client {alerte:"ROUGE"})-[:CONTAGION_TERRITOIRE|CONTAGION_PORTEFEUILLE*1..2]->(voisin:Client)
// WHERE voisin.alerte <> "ROUGE"
// RETURN voisin.client_id, voisin.score_final_m2, voisin.alerte, length(path) AS distance
// ORDER BY voisin.score_final_m2 DESC LIMIT 20;

// Taux de risque par segment (requête analytique)
// MATCH (c:Client)-[:APPARTIENT_AU_SEGMENT]->(s:SegmentClient)
// RETURN s.nom, count(c) AS nb_clients,
//        sum(c.label_risque) AS nb_risque,
//        round(100.0 * sum(c.label_risque) / count(c), 1) AS taux_pct
// ORDER BY taux_pct DESC;
