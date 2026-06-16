

# m6_graphrag — GraphRAG + LLM Knowledge Base

Système GraphRAG (Neo4j + LlamaIndex) pour la base de connaissances métier
sur le risque de crédit.

## Fichiers

| Fichier | Description |
|---------|-------------|
| `schema.cypher` | Schéma Neo4j complet (contraintes, index, nœuds, relations) |
| `ingest.py` | *(à créer)* Ingestion CSV → Neo4j |
| `rag_engine.py` | *(à créer)* LlamaIndex PropertyGraphIndex + requêtes |

## Schéma — vue d'ensemble

Voir `schema.cypher` pour le détail complet des propriétés et relations.

### 3 couches

```
COUCHE 1 · Données métier
  (:Client) ──[:SITUE_DANS]──► (:Gouvernorat)
  (:Client) ──[:APPARTIENT_AU_SEGMENT]──► (:SegmentClient)
  (:Client) ──[:PAIE_VIA]──► (:ModePaiement)
  (:Client) ──[:SUIVI_PAR]──► (:Commercial)

COUCHE 2 · Classification risque (M2)
  (:Client) ──[:CLASSIFIE_COMME {score_gnn, score_contagion, score_final_m2}]──► (:AlerteRisque)
  (:Client) ──[:CONTAGION_TERRITOIRE {poids}]──► (:Client)
  (:Client) ──[:CONTAGION_PORTEFEUILLE {poids}]──► (:Client)

COUCHE 3 · Knowledge base (GraphRAG)
  (:ConceptRisque) ──[:DEFINI_PAR]──► (:RegleDecision)
  (:SegmentClient) ──[:ASSOCIE_AU_CONCEPT {taux_risque}]──► (:ConceptRisque)
  (:Gouvernorat)   ──[:ASSOCIE_AU_CONCEPT {taux_risque}]──► (:ConceptRisque)
  (:ModePaiement)  ──[:SIGNAL_DE]──► (:ConceptRisque)
  (:Client)        ──[:PRESENTE]──► (:ConceptRisque)
```

### Cardinalités attendues

| Nœud | Nombre |
|------|--------|
| Client | 21 637 (1 637 réels + 20 000 synthétiques) |
| Gouvernorat | 25 |
| SegmentClient | 23 |
| ModePaiement | 9 (8 codes + INCONNU) |
| Commercial | 22 |
| AlerteRisque | 3 (VERT / ORANGE / ROUGE) |
| ConceptRisque | ~8 |
| RegleDecision | ~6 |
