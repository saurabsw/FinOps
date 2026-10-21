Project: Multi-Cloud FinOps Cost Optimizer \& Safe Remediation Engine

1\. Executive Summary \& ObjectiveModern enterprise cloud environments silently accumulate orphaned, unattached, and idle resources (e.g., persistent disks detached after VM termination, unused static IPs, and stopped compute instances).   This project delivers a decoupled, standalone FinOps web platform that:Ingests raw cloud billing exports (GCP Detailed Usage CSV/JSON, AWS CUR, and Azure Cost Export).   Maps disparate billing lines into a standardized canonical resource schema.Evaluates spend using an out-of-the-box Deterministic Best Practice Engine, complemented by an optional Declarative Custom Rule Configurator.   Enforces an enterprise-grade 2-Step "Inspect-then-Confirm" Remediation Pattern via interactive CLI snippets and shell script exports.Operates via an independent, headless FastAPI service backend consumed by a decoupled dashboard.



2\. System ArchitecturePlaintext       ┌────────────────────────────────────────────────────────┐

&#x20;      │                Independent Frontend UI                 │

&#x20;      │     (Dashboard, Metrics, Table, Inspect/Remediate)     │

&#x20;      └──────────────┬───────────────────────────▲─────────────┘

&#x20;     Upload (CSV/JSON)│                           │ REST API (JSON)

&#x20;                     ▼                           │

&#x20;      ┌──────────────────────────────────────────┴─────────────┐

&#x20;      │            Headless Backend Layer (FastAPI)            │

&#x20;      │                                                        │

&#x20;      │  ┌────────────────────┐       ┌─────────────────────┐  │

&#x20;      │  │ Ingestion Adapters │       │ Engine Core:        │  │

&#x20;      │  │ (GCP / AWS / Azure)├──────►│ 1. Built-in Rules   │  │

&#x20;      │  └────────────────────┘       │ 2. Rule Configurator│  │

&#x20;      │                               └──────────┬──────────┘  │

&#x20;      │                                          │             │

&#x20;      │  ┌────────────────────┐       ┌──────────▼──────────┐  │

&#x20;      │  │ SQLite Database    │◄──────┤ Remediation Engine  │  │

&#x20;      │  │ (SQLAlchemy ORM)   │       │ (Inspect + Confirm) │  │

&#x20;      │  └────────────────────┘       └─────────────────────┘  │

&#x20;      └────────────────────────────────────────────────────────┘



3\. Core Modules \& Functional Specifications

3.1. Multi-Cloud Ingestion EngineInput Types: GCP Detailed Cost Export (CSV/JSON), AWS CUR (CSV/JSON), Azure Cost Export (CSV/JSON).   Canonical Schema:resource\_id: Cloud native identifier / URI / ARN.   resource\_name: Human-readable identifier.provider: gcp | aws | azure.resource\_type: disk | instance | ip | snapshot.region\_or\_zone: Cloud region or availability zone.   project\_or\_account\_id: GCP Project ID / AWS Account ID / Azure Subscription ID.   cost\_amount: Incurred monetary charge.currency: Currency code (USD, EUR, INR, etc.).   usage\_amount: Raw usage metric (GB-months, hours, etc.).   status\_hint: Derived indicator (unattached, idle, stale).



3.2. Two-Tier Rules EngineTier 1: Built-in Best Practices Engine (Base Engine)Pre-loaded, deterministic rules based on cloud vendor benchmarks:   Orphan Disks: GCP Persistent Disks, AWS EBS volumes, Azure Managed Disks incurring storage charges with 0 compute attachment hours.   Idle IPs: GCP External Reserved IPs, AWS Unassociated Elastic IPs, Azure Public IPs incurring idle reservation fees.   Idle VMs: Stopped instances accumulating persistent disk/IP fees with 0 compute hours.   Stale Snapshots: Backup snapshots older than 30–90 days with recurring charges.   Tier 2: User Rule Configurator (Add-on Feature)Declarative JSON/YAML rule builder.   Evaluates configurable conditions (cost\_monthly > X, tag == Y, idle\_days > Z).   Endpoints to list, create, toggle, and delete custom rules.   



3.3. Enterprise "Inspect-then-Confirm" Remediation EngineEvery waste finding yields a two-stage remediation protocol:Selection / Inspection Command: Read-only command displaying current live metadata, tags, and dependencies.Interactive Remediation Command: Execution command strictly excluding non-interactive force flags (--quiet, -y, --yes).Safety-Gated Script Generator: Downloadable bash script (remediate\_waste.sh) featuring confirmation gates (read -r -p "Delete resource? (yes/no)") before invoking each command.



3.4. API Specification (FastAPI)POST /api/v1/billing/upload — Ingests billing files and maps them to the canonical model.POST /api/v1/optimizer/scan — Runs the rules engine across ingested billing records.GET /api/v1/optimizer/waste-items — Returns detected waste findings, cost leakage, and 2-step CLI snippets.GET /api/v1/optimizer/generate-script — Streams a consolidated, interactive bash cleanup script.GET /api/v1/rules \& POST /api/v1/rules — Manages the custom rule catalog.   



3.5. Automated Quality \& Certification HarnessComplete pytest suite testing:Ingestion parser mapping for GCP, AWS, and Azure.   Built-in rule evaluations (ensuring 0 false positives on active resources).   CLI safety guards (ensuring absence of auto-delete flags and presence of inspection commands).Custom rule creation and evaluation logic.   End-to-end FastAPI endpoint lifecycles.

