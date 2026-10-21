# Audit Log - User Prompts

## Entry 1 - 2026-10-19 21:43:18 +05:30
```text
Lead Architect mode: ON. We are building a Python-based, API-first GCP Cloud Cost Optimizer & Remediation Engine using a free database and a dashboard.
Rules:
● No Manual Edits: You provide all logic and fixes. I will not edit any code.
● Audit Log: You must maintain a file named prompts.md. After every turn, update that file (or provide the text block) with the prompt I just used.
● Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed Time' at the end of every response. Acknowledge and let's start.
```

## Entry 2 - 2026-10-19 21:59:54 +05:30
```text
Step 2: Implement Multi-Cloud Ingestion Adapters and the File Upload Endpoint.

Requirements:
1. Create backend/app/adapters/:
   - gcp_adapter.py: Parses GCP billing CSV/JSON, extracts SKU, project ID, zone, resource name, cost, and usage. Identifies unattached disk and idle IP indicators.
   - aws_adapter.py: Parses AWS CUR CSV/JSON, mapping line items to canonical records.
   - azure_adapter.py: Parses Azure Cost Export CSV/JSON, mapping line items to canonical records.
   - base_adapter.py: Adapter factory returning the correct parser based on cloud_provider parameter.
2. Create backend/app/routers/billing.py with:
   - POST /api/v1/billing/upload: Accepts file upload (multipart/form-data) and cloud_provider string. Normalizes rows, validates against Pydantic schema, saves records to SQLite, and returns ingestion summary (total records, total spend, detected providers).
3. Connect router to backend/app/main.py.
4. Create tests/test_unit/test_adapters.py certifying that each parser correctly transforms sample CSV rows into CanonicalBillingRecord entries without data loss. Run pytest to certify.
5. Update prompts.md and report Elapsed Time.

Step 3: Implement the Built-in FinOps Rules Engine and the 2-Step Safe Remediation Generator.

Requirements:
1. Create backend/app/rules/best_practices.py with deterministic rules:
   - GCP: Orphaned Persistent Disk (unattached storage charges), Unused Reserved External IP (idle static address charges), Idle Compute VM.
   - AWS: Unattached EBS Volume, Unassociated Elastic IP.
   - Azure: Unattached Managed Disk, Unassociated Public IP.
2. Create backend/app/remediation.py:
   - For every flagged waste resource, generate TWO distinct CLI commands:
     a) Inspection Command: Read-only command (e.g., 'gcloud compute disks describe <id> --zone <zone> --project <proj>').
     b) Remediation Command: Interactive deletion command strictly omitting quiet/yes flags (e.g., 'gcloud compute disks delete <id> --zone <zone> --project <proj>') to force native CLI confirmation prompts.
   - Generate interactive shell script wrapper with a user confirmation gate:
     read -r -p "Confirm decommission of <resource_id>? (yes/no): "
3. Create backend/app/routers/optimizer.py:
   - POST /api/v1/optimizer/scan: Runs rules against ingested records, records WasteFindings in DB, and returns scan summary.
   - GET /api/v1/optimizer/waste-items: Returns all waste findings with inspection and cleanup commands.
   - GET /api/v1/optimizer/generate-script: Generates and streams a downloadable remediate_waste.sh bash script.
4. Connect router to main.py.
5. Create tests/test_unit/test_rules_remediation.py:
   - Verify all rules identify waste and ignore active resources.
   - Assert that no generated remediation command contains '--quiet', '-y', or '--yes'.
   - Assert inspection commands are properly formatted. Run pytest to certify.
6. Update prompts.md and report Elapsed Time.

Step 4: Implement the Declarative Custom Rule Configurator as an add-on feature.

Requirements:
1. Create backend/app/rules/custom_evaluator.py:
   - Evaluates user-defined rules stored in SQLite against CanonicalBillingRecord items.
   - Supports condition fields: cost_amount, resource_type, status_hint, region_or_zone.
   - Supports operators: greater_than, less_than, equals, contains.
   - Combines conditions using logical AND ('all') or OR ('any').
   - Generates templated inspect and interactive cleanup commands based on custom rule definitions.
2. Create backend/app/routers/custom_rules.py:
   - GET /api/v1/rules: List all active rules (built-in indicators + custom rules).
   - POST /api/v1/rules: Create and store a new custom rule with validation.
   - PUT /api/v1/rules/{rule_id}: Enable/disable or edit rule thresholds.
   - DELETE /api/v1/rules/{rule_id}: Delete a custom rule.
3. Update POST /api/v1/optimizer/scan to evaluate both built-in best practices and active custom rules.
4. Create tests/test_unit/test_custom_rules.py certifying custom rule registration, validation, condition evaluation, and execution. Run pytest to certify.
5. Update prompts.md and report Elapsed Time.


Step 5: Build the Decoupled Frontend Dashboard.

Requirements:
1. Build frontend/app.py using Streamlit (or a decoupled static web app) communicating exclusively via HTTP with the FastAPI backend at http://localhost:8000.
2. Dashboard Features:
   - Top Header & Cloud Provider Selector (GCP, AWS, Azure, All).
   - Ingestion Panel: File uploader accepting CSV/JSON with a trigger to POST /api/v1/billing/upload, plus a "Load Sample Dataset" button for instant demo evaluation.
   - KPI Summary Cards: Total Spend, Total Detected Monthly Waste ($), Identified Orphan Resources Count, Potential Savings (%).
   - Waste Breakdown Visualizations: Bar/Donut charts grouping waste by resource type and project/account.
   - Actionable Inventory Table:
     * Displays Provider, Resource Name, Type, Monthly Waste, Rationale.
     * Expandable Drawer / Column showing:
       1) Step 1: Inspection CLI command (with 1-click Copy button).
       2) Step 2: Interactive Cleanup CLI command (with 1-click Copy button).
   - Export Button: Download complete 'remediate_waste.sh' executable bash script.
   - Rule Configurator Tab: Interface to view active rules, toggle their state, and create custom condition rules via an interactive form.
3. Update prompts.md and report Elapsed Time.


Step 6: Complete End-to-End Integration Tests, Run System Verification, and Polish Documentation.

Requirements:
1. Create tests/test_integration/test_full_workflow.py:
   - Upload sample GCP, AWS, and Azure billing files via FastAPI TestClient.
   - Execute the /scan endpoint.
   - Assert all expected orphaned persistent disks, unassociated IPs, and idle compute instances are flagged.
   - Assert API contracts for /waste-items and /generate-script.
   - Create and execute a custom rule through the API and certify its detection.
2. Run full pytest suite across all unit and integration tests and ensure 100% pass rate.
3. Create README.md containing:
   - Architecture diagram and decoupling explanation.
   - One-command startup instructions (FastAPI backend + Streamlit dashboard).
   - "Inspect-then-Confirm" enterprise safety rationale.
   - Testing certification command (pytest).
   - Phase 2 roadmap (automated GCS/S3 bucket sync, scheduled cron scanning, SDK live-execution mode).
4. Update prompts.md with final prompt entry and report final Elapsed Time.
```
