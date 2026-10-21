import pytest
from backend.app.core.config import settings

def test_full_finops_workflow(backend_client):
    client = backend_client

    # 1. Health Check
    health_res = client.get("/api/v1/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # 2. Upload GCP Detailed Billing File
    gcp_path = settings.SAMPLES_DIR / "gcp_detailed_billing_sample.csv"
    with open(gcp_path, "rb") as f:
        res_gcp = client.post(
            "/api/v1/billing/upload",
            files={"file": ("gcp_billing.csv", f, "text/csv")},
            data={"cloud_provider": "gcp"}
        )
    assert res_gcp.status_code == 200
    data_gcp = res_gcp.json()
    assert data_gcp["status"] == "success"
    assert data_gcp["total_records"] > 0
    assert "gcp" in data_gcp["detected_providers"]

    # 3. Upload AWS CUR Billing File
    aws_path = settings.SAMPLES_DIR / "aws_cur_sample.csv"
    with open(aws_path, "rb") as f:
        res_aws = client.post(
            "/api/v1/billing/upload",
            files={"file": ("aws_cur.csv", f, "text/csv")},
            data={"cloud_provider": "aws"}
        )
    assert res_aws.status_code == 200
    data_aws = res_aws.json()
    assert data_aws["status"] == "success"
    assert data_aws["total_records"] == 4

    # 4. Upload Azure Cost Export File
    azure_path = settings.SAMPLES_DIR / "azure_cost_export_sample.csv"
    with open(azure_path, "rb") as f:
        res_azure = client.post(
            "/api/v1/billing/upload",
            files={"file": ("azure_export.csv", f, "text/csv")},
            data={"cloud_provider": "azure"}
        )
    assert res_azure.status_code == 200
    data_azure = res_azure.json()
    assert data_azure["status"] == "success"
    assert data_azure["total_records"] == 3

    # 5. Verify Canonical Records Endpoint
    rec_res = client.get("/api/v1/billing/records?limit=100")
    assert rec_res.status_code == 200
    all_recs = rec_res.json()["items"]
    assert len(all_recs) >= 15

    # 6. Execute /scan Endpoint
    scan_res = client.post("/api/v1/optimizer/scan")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["status"] == "success"
    assert scan_data["findings_detected"] > 0
    assert scan_data["potential_monthly_savings"] > 0

    # 7. Assert expected waste is flagged
    waste_res = client.get("/api/v1/optimizer/waste-items")
    assert waste_res.status_code == 200
    waste_data = waste_res.json()
    findings = waste_data["findings"]
    assert len(findings) > 0

    # Assert Orphaned persistent disks
    assert any(f["category"] == "Orphan Disk" and f["provider"] == "gcp" for f in findings)
    assert any(f["category"] == "Orphan Disk" and f["provider"] == "aws" for f in findings)
    assert any(f["category"] == "Orphan Disk" and f["provider"] == "azure" for f in findings)

    # Assert Unassociated IPs
    assert any(f["category"] == "Idle IP" and f["provider"] == "gcp" for f in findings)
    assert any(f["category"] == "Idle IP" and f["provider"] == "aws" for f in findings)
    assert any(f["category"] == "Idle IP" and f["provider"] == "azure" for f in findings)

    # Assert Idle Compute VMs
    assert any(f["category"] == "Idle VM" and f["provider"] == "gcp" for f in findings)

    # 8. Assert API Contracts for /waste-items
    for f in findings:
        assert "inspect_command" in f
        assert "remediation_command" in f
        assert "--quiet" not in f["remediation_command"]
        assert "-y" not in f["remediation_command"]
        assert "--yes" not in f["remediation_command"]
        assert f["monthly_savings_estimate"] > 0

    # 9. Assert API Contract for /generate-script
    script_res = client.get("/api/v1/optimizer/generate-script")
    assert script_res.status_code == 200
    assert script_res.headers["content-type"].startswith("text/x-shellscript")
    script_content = script_res.text
    assert "#!/usr/bin/env bash" in script_content
    assert "read -r -p" in script_content
    assert "DRY_RUN" in script_content

    # 10. Create and Execute Custom Rule via API
    custom_rule_payload = {
        "id": "e2e-high-cost-disk",
        "name": "E2E Detached Storage > $30",
        "description": "Flags detached disks costing more than 30",
        "provider": "*",
        "resource_type": "disk",
        "logic_operator": "all",
        "conditions": [
            {"field": "cost_amount", "operator": "greater_than", "value": 30.0},
            {"field": "status_hint", "operator": "equals", "value": "unattached"}
        ],
        "severity": "CRITICAL"
    }
    create_rule_res = client.post("/api/v1/rules", json=custom_rule_payload)
    assert create_rule_res.status_code == 200

    # Verify rule is listed
    rules_res = client.get("/api/v1/rules")
    assert rules_res.status_code == 200
    assert any(r["id"] == "e2e-high-cost-disk" for r in rules_res.json()["custom_rules"])

    # Re-run scan to verify custom rule execution
    rescan = client.post("/api/v1/optimizer/scan")
    assert rescan.status_code == 200
    assert rescan.json()["findings_detected"] > 0
