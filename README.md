# CreditMind 🧠

> **Agentic Credit Intelligence Platform** — Plateforme IA de bout en bout pour l'évaluation de la solvabilité commerciale, construite sur des données réelles tunisiennes.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![PyTorch](https://img.shields.io/badge/PyTorch-2.2+-orange?style=flat-square)
![LangGraph](https://img.shields.io/badge/LangGraph-0.1+-purple?style=flat-square)
![MLflow](https://img.shields.io/badge/MLflow-2.x-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🎯 Overview

**CreditMind** is an end-to-end AI platform that evaluates the solvability of commercial clients using state-of-the-art 2025 AI techniques. Built on real transactional data (invoices + payments), it predicts payment defaults before they happen, detects risk contagion across client networks, and provides explainable decisions to commercial managers.

### What it does

Given a client's invoice and payment history, CreditMind:
- Computes a **solvency score (0–100)** combining behavioral, temporal, and network signals
- **Predicts payment delays** up to 6 months in advance
- Detects **risk contagion** between clients sharing the same sales rep or region
- Triggers **real-time alerts** when anomalous payment behavior is detected
- Provides **explainable decisions** in plain language via LLM agents
- Simulates **crisis scenarios** and their portfolio impact in TND

---

## 🏗️ Architecture

```
Raw Data (Invoices + Payments)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                  CreditMind Pipeline                    │
│                                                         │
│  M1 Synthetic Data     →  Augment to 20k clients       │
│  M2 Graph Neural Net   →  Risk contagion detection     │
│  M3 Time Series (TFT)  →  6-month risk forecasting     │
│  M4 Anomaly Detection  →  Real-time behavior alerts    │
│  M5 Scoring Ensemble   →  Final score 0-100 + MLOps    │
│  M6 GraphRAG + LLM     →  Business knowledge graph     │
│  M7 LangGraph Agents   →  8 autonomous decision agents │
│  M8 XAI + Early Warning→  SHAP, DiCE, counterfactuals  │
│  M9 Stress Testing     →  Monte Carlo crisis scenarios │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
         Dashboard + REST API + Agent Chat
```

---

## 📦 Modules

| Module | Name | Key Tech | Owner |
|--------|------|----------|-------|
| M1 | Synthetic Data Engine | TabDDPM, Opacus, SDMetrics | Person A |
| M2 | Graph Neural Network | PyTorch Geometric, GraphSAGE, GAT | Person A |
| M3 | Time Series Forecaster | TFT, N-HiTS, Darts | Person A |
| M4 | Anomaly Detection | Isolation Forest, LSTM Autoencoder, River | Person A |
| M5 | Scoring Ensemble + MLOps | AutoGluon, XGBoost, MLflow, DVC, Evidently | Person A |
| M6 | GraphRAG + LLM Fine-tuning | Neo4j, LlamaIndex, Mistral-7B, LoRA | Person B |
| M7 | Multi-Agent LangGraph | LangGraph, LangSmith, Mem0 | Person B |
| M8 | XAI + Early Warning | SHAP, DiCE, Streamlit | Person B |
| M9 | Stress Testing | Monte Carlo, LangGraph, Plotly | Person B |

---

## 🗂️ Repository Structure

```
creditmind/
├── m1_synthetic_data/
│   ├── tabddpm/
│   ├── evaluation/
│   └── README.md
├── m2_gnn/
│   ├── graph_builder.py
│   ├── graphsage_model.py
│   ├── train.py
│   └── README.md
├── m3_time_series/
│   ├── tft_model.py
│   ├── nhits_model.py
│   ├── forecasting_pipeline.py
│   └── README.md
├── m4_anomaly_detection/
│   ├── isolation_forest.py
│   ├── lstm_autoencoder.py
│   ├── streaming_detector.py
│   └── README.md
├── m5_scoring/
│   ├── feature_engineering.py
│   ├── ensemble_model.py
│   ├── mlflow_tracking.py
│   ├── drift_monitoring.py
│   └── README.md
├── m6_graphrag/
│   ├── knowledge_graph/
│   ├── rag_engine.py
│   ├── llm_finetuning/
│   └── README.md
├── m7_agents/
│   ├── agents/
│   │   ├── behavior_agent.py
│   │   ├── network_agent.py
│   │   ├── forecast_agent.py
│   │   ├── anomaly_agent.py
│   │   ├── compliance_agent.py
│   │   ├── reasoning_agent.py
│   │   ├── decision_agent.py
│   │   └── report_agent.py
│   ├── orchestrator.py
│   └── README.md
├── m8_xai/
│   ├── shap_explainer.py
│   ├── dice_counterfactuals.py
│   ├── early_warning.py
│   ├── report_generator.py
│   └── README.md
├── m9_stress_testing/
│   ├── scenario_generator.py
│   ├── monte_carlo.py
│   ├── portfolio_impact.py
│   └── README.md
├── dashboard/
│   ├── app.py
│   ├── pages/
│   │   ├── portfolio.py
│   │   ├── client_detail.py
│   │   ├── network_view.py
│   │   ├── forecast_view.py
│   │   ├── agent_chat.py
│   │   └── stress_testing.py
│   └── README.md
├── api/
│   ├── main.py
│   ├── routers/
│   └── schemas/
├── data/
│   ├── raw/            ← gitignored
│   ├── processed/      ← gitignored
│   └── synthetic/      ← gitignored
├── notebooks/
│   ├── 00_eda.ipynb
│   ├── 01_feature_engineering.ipynb
│   ├── 02_labeling.ipynb
│   └── ...
├── tests/
├── docs/
│   └── cahier_des_charges.docx
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (dashboard)
- Docker & Docker Compose
- CUDA 11.8+ (recommended for GNN and LLM fine-tuning)

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/creditmind.git
cd creditmind

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```bash
# .env.example
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=creditmind

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=

MLFLOW_TRACKING_URI=http://localhost:5000
```

### Run with Docker

```bash
docker-compose up -d
```

Services started:
- `localhost:8501` — Streamlit Dashboard
- `localhost:8000` — FastAPI
- `localhost:5000` — MLflow UI
- `localhost:7474` — Neo4j Browser

---

## 📊 Data

The platform is built on real commercial transactional data:

| Source | Rows | Description |
|--------|------|-------------|
| Invoices (`Factures`) | 17,526 | Client purchases, amounts TTC, segments, regions |
| Payments (`Reglements`) | 25,640 | Payment dates, due dates, payment modes, delays |

**Data is not included in this repository.** Place your data files in `data/raw/` — they are gitignored.

---

## 🧪 Running the Pipeline

```bash
# Step 1 — Feature engineering
python m5_scoring/feature_engineering.py

# Step 2 — Generate synthetic data
python m1_synthetic_data/tabddpm/train.py

# Step 3 — Build client graph
python m2_gnn/graph_builder.py

# Step 4 — Train GNN
python m2_gnn/train.py

# Step 5 — Train time series models
python m3_time_series/forecasting_pipeline.py

# Step 6 — Train anomaly detector
python m4_anomaly_detection/streaming_detector.py

# Step 7 — Train scoring ensemble
python m5_scoring/ensemble_model.py

# Step 8 — Build knowledge graph
python m6_graphrag/knowledge_graph/build.py

# Step 9 — Launch dashboard
streamlit run dashboard/app.py
```

---

## 📈 Model Performance Targets

| Module | Metric | Target |
|--------|--------|--------|
| M1 Synthetic Data | Fidelity score (SDMetrics) | > 0.80 |
| M2 GNN | AUC-ROC default prediction | > 0.85 |
| M3 Time Series | MAPE payment delay | < 15% |
| M4 Anomaly Detection | Alert precision | > 80% |
| M5 Scoring | AUC-ROC final score | > 0.90 |
| M7 Agents | Task completion rate | > 95% |
| M8 Early Warning | At-risk client recall | > 90% |
| Global | Client scoring latency | < 3s |

---

## 🤖 AI Techniques Used

- **TabDDPM** — Diffusion model for tabular synthetic data generation
- **Differential Privacy (DP-SGD)** — Privacy-preserving synthetic data
- **GraphSAGE / GAT** — Graph Neural Networks for risk contagion
- **Temporal Fusion Transformer (TFT)** — State-of-the-art time series forecasting
- **N-HiTS** — Neural hierarchical time series forecasting
- **LSTM Autoencoder** — Unsupervised anomaly detection
- **River** — Online machine learning for streaming data
- **AutoGluon** — AutoML for scoring ensemble
- **GraphRAG + Neo4j** — Knowledge graph retrieval augmented generation
- **LoRA / QLoRA** — Efficient LLM fine-tuning on domain vocabulary
- **LangGraph** — Multi-agent autonomous orchestration
- **SHAP** — Model explainability
- **DiCE** — Counterfactual explanations

---

## 👥 Team

| Role | Responsibilities |
|------|-----------------|
| Person A — ML & Data Engineer | M1, M2, M3, M4, M5, Infrastructure |
| Person B — AI & LLM Engineer | M6, M7, M8, M9, Dashboard |

---

## 📅 Timeline

20-week project — MSc AI / Engineering double degree program, 2024–2025.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ — MSc AI × Engineering, PSTB Paris / ESPRIT Tunis</sub>
</div>
