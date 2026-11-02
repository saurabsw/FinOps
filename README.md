# Static FinOps Analyzer 

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135%2B-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.65-red.svg)](https://streamlit.io)
[![Tests](https://img.shields.io/badge/Tests-35%20Passed%20(85%25%20cov)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

An enterprise-grade, API-first FinOps optimization and safe remediation engine built in Python using a free embedded SQLite database, a decoupled FastAPI headless backend, and an interactive Streamlit in-page command center. Multi-Cloud FinOps Analyzer, safe remediation suggestions, and cost optimization across Google Cloud (GCP), Amazon Web Services (AWS), and Microsoft Azure.

---

## 🏛️ System Architecture & Decoupling

The platform is designed around strict architectural decoupling:

```text
               ┌────────────────────────────────────────────────────────┐
               │        Decoupled Frontend UI Layer                     │
               │  • Streamlit Command Center (frontend/app.py)          │
               │  • Native Web Dashboard (app/static/index.html)        │
               └──────────────┬───────────────────────────▲─────────────┘
             Upload (CSV/JSON)│                           │ REST API (JSON)
                              ▼                           │
               ┌──────────────────────────────────────────┴─────────────┐
               │        Headless Backend Layer (FastAPI)                │
               │        (backend/app/main.py)                           │
               │                                                        │
               │  ┌──────────────────────┐   ┌────────────────────────┐ │
               │  │ Ingestion Adapters   │   │ Two-Tier Rules Engine: │ │
               │  │ (GCP / AWS / Azure)  ├──►│ 1. Best Practices      │ │
               │  │                      │   │ 2. Custom Configurator │ │
               │  └──────────────────────┘   └───────────┬────────────┘ │
               │                                         │              │
               │  ┌──────────────────────┐   ┌───────────▼────────────┐ │
               │  │ SQLite Database      │◄──┤ Safe Remediation Engine│ │
               │  │ (SQLAlchemy 2.0 ORM) │   │ (Inspect + Confirm)    │ │
               │  └──────────────────────┘   └────────────────────────┘ │
               └────────────────────────────────────────────────────────┘
```

### Architectural Principles:
1. **Headless & Decoupled Backend**: The FastAPI backend exposes complete OpenAPI endpoints (`/api/v1`) and operates completely independently from the frontend.
2. **Zero-Subscription Storage**: Free, persistent, self-contained SQLite database managed via SQLAlchemy 2.0 ORM.
3. **Canonical Data Model**: Normalizes disparate cloud billing records (GCP Detailed Usage, AWS CUR, Azure Cost Export) into a unified `CanonicalBillingRecord` schema.
4. **Deterministic & Declarative Engines**: Combines hard-coded vendor best practices (Tier 1) with user-configurable dynamic policies (Tier 2).

---

## 🛡️ Enterprise "Inspect-then-Confirm" Safety Pattern

Enterprise cloud operations strictly prohibit uncontrolled, non-interactive batch deletions. A single mistagged resource or false positive can decommission a live database or drop production ingress IP traffic.

To address this, our Remediation Engine enforces a strict 2-step protocol:

```text
┌──────────────────────────┐         ┌──────────────────────────┐
│   Step 1: Inspection     │         │   Step 2: Remediation    │
│   (Read-Only Metadata)   ├────────►│   (Interactive Prompt)   │
│   gcloud compute disks   │ Human   │   gcloud compute disks   │
│   describe <id>          │ Review  │   delete <id>            │
│   [Shows size, tags,     │         │   [NO --quiet, -y, -f    │
│    attachment state]     │         │    Force flags forbidden]│
└──────────────────────────┘         └──────────────────────────┘
```

1. **Step 1: Read-Only Inspection CLI Command**:
   - Displays live tags, creation timestamps, and active bindings without altering resource state:
     ```bash
     gcloud compute disks describe disk-prod-replica --zone us-central1-a --project finops-prod-infra
     ```
2. **Step 2: Interactive Cleanup Command**:
   - Strictly strips destructive force flags (`--quiet`, `-q`, `-y`, `--yes`, `--force`, `-f`).
   - Ensures the native cloud provider CLI prompts the operator interactively:
     ```bash
     gcloud compute disks delete disk-prod-replica --zone us-central1-a --project finops-prod-infra
     ```
3. **Downloadable Bash Wrapper (`remediate_waste.sh`)**:
   - Features confirmation gates before every destructive command:
     ```bash
     read -r -p "Confirm decommission of <resource_id>? (yes/no): " CONFIRM_INPUT
     ```
   - Includes `--dry-run` flag support to safely preview commands without executing changes.

---

## ⚡ One-Command Startup Instructions

### 1. Launch FastAPI Backend Server
```powershell
py -3 run_server.py
```
> **Port Fallback**: If port `8000` is in use (e.g., by Docker Desktop), the server automatically falls back to port `8001`. You can also specify a port explicitly: `py -3 run_server.py --port 8001`.

- **Backend API URL**: [http://127.0.0.1:8001](http://127.0.0.1:8001) (or `8000`)
- **Interactive OpenAPI Docs**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- **Native Web Dashboard**: [http://127.0.0.1:8001/](http://127.0.0.1:8001/)

### 2. Launch Streamlit Decoupled Dashboard
In a separate terminal:
```powershell
py -3 -m streamlit run frontend/app.py
```
- **Streamlit UI**: [http://localhost:8501](http://localhost:8501)
*(The Streamlit frontend automatically detects the running backend port `8001` or `8000`)*

---

## 📡 API Specification (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status |
| `POST` | `/api/v1/billing/upload` | Ingests CSV/JSON billing file into SQLite |
| `POST` | `/api/v1/billing/load-samples` | One-click load of pre-packaged GCP, AWS, and Azure sample data |
| `GET` | `/api/v1/billing/records` | Query normalized canonical cloud resources |
| `DELETE` | `/api/v1/billing/clear` | Purges all resources and findings for clean benchmark |
| `POST` | `/api/v1/optimizer/scan` | Runs rules engine across canonical resources |
| `GET` | `/api/v1/optimizer/waste-items` | Returns waste findings with 2-step CLI snippets |
| `GET` | `/api/v1/optimizer/summary` | Aggregated FinOps KPIs & ROI metrics |
| `GET` | `/api/v1/optimizer/generate-script` | Generates and streams downloadable `remediate_waste.sh` |
| `POST` | `/api/v1/optimizer/remediate-action` | Tracks remediation status & audit logs |
| `GET` | `/api/v1/rules` | Lists built-in and custom policies |
| `POST` | `/api/v1/rules` | Registers a declarative custom policy |
| `PUT` | `/api/v1/rules/{id}` | Updates rule thresholds or logic |
| `PUT` | `/api/v1/rules/{id}/toggle` | Enables/disables policy rule |
| `DELETE` | `/api/v1/rules/{id}` | Deletes custom policy |

---

## 🧪 Certified Test Suite

Run the full certification suite:
```powershell
py -3 -m pytest tests/ --cov=backend.app -v
```

### Coverage & Test Suite Summary:
```text
======================== 32 passed in 0.67s ========================
Coverage:
- backend/app/rules/best_practices.py: 92%
- backend/app/rules/custom_evaluator.py: 86%
- backend/app/adapters/base_adapter.py: 90%
- backend/app/adapters/gcp_adapter.py: 82%
- backend/app/routers/optimizer.py: 88%
- backend/app/remediation.py: 83%
- TOTAL: 83%
```

All 32 unit and integration tests validate:
- Ingestion parser transformation for GCP, AWS, and Azure into `CanonicalBillingRecord`.
- Zero false positives on active attached resources.
- Strict omission of non-interactive force flags (`--quiet`, `-y`, `--yes`).
- Interactive confirmation gates in generated shell scripts.
- Declarative custom rule evaluation (`greater_than`, `less_than`, `equals`, `contains`, `AND`/`OR`).
- End-to-end multi-cloud upload, scan, finding retrieval, and script generation.

---

## 🔮 Phase 2 Roadmap

1. **Automated GCS / AWS S3 Bucket Sync**: Direct listener daemon fetching daily billing export CSV/Parquet files from Google Cloud Storage or S3 buckets without manual uploads.
2. **Scheduled Cron Scanning**: Periodic background worker evaluating newly arrived billing items and pushing alerts to Slack / PagerDuty / Microsoft Teams.
3. **Cloud SDK Live-Execution Mode**: Optional OAuth-authenticated mode allowing users with elevated IAM permissions to trigger cloud SDK execution directly from the dashboard after 2-factor confirmation.
4. **Anomaly Anomaly ML Forecasting**: Time-series ARIMA / Prophet cost trend projection to flag sudden spikes before the monthly billing cycle concludes.
