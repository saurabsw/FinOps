import io
import pytest
from app.core.config import settings

def test_health_endpoint(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

def test_billing_upload_and_scan_lifecycle(client):
    # 1. Upload sample GCP billing CSV
    sample_file = settings.SAMPLES_DIR / "gcp_detailed_billing_sample.csv"
    with open(sample_file, "rb") as f:
        response = client.post(
            "/api/v1/billing/upload",
            files={"file": ("gcp_billing.csv", f, "text/csv")}
        )
    assert response.status_code == 200
    upload_res = response.json()
    assert upload_res["status"] == "success"
    assert upload_res["provider_detected"] == "gcp"
    assert upload_res["records_ingested"] > 0

    # 2. Check canonical records listing
    rec_res = client.get("/api/v1/billing/records?limit=50")
    assert rec_res.status_code == 200
    assert rec_res.json()["total"] > 0

    # 3. Trigger Optimizer Scan
    scan_res = client.post("/api/v1/optimizer/scan")
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["status"] == "success"
    assert scan_data["findings_detected"] > 0
    assert scan_data["potential_monthly_savings"] > 0

    # 4. Fetch Waste Items
    waste_res = client.get("/api/v1/optimizer/waste-items")
    assert waste_res.status_code == 200
    waste_data = waste_res.json()
    assert waste_data["total_findings"] > 0
    first_finding = waste_data["findings"][0]
    assert "inspect_command" in first_finding
    assert "remediation_command" in first_finding
    assert "--quiet" not in first_finding["remediation_command"]
    assert "-y" not in first_finding["remediation_command"]

    # 5. Fetch FinOps Summary KPIs
    summary_res = client.get("/api/v1/optimizer/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_resources"] > 0
    assert summary["total_waste_findings"] > 0
    assert summary["savings_percentage"] > 0
    assert "Orphan Disk" in summary["breakdown_by_category"]

    # 6. Generate and download script
    script_res = client.get("/api/v1/optimizer/generate-script")
    assert script_res.status_code == 200
    assert script_res.headers["content-type"].startswith("text/x-shellscript")
    script_text = script_res.text
    assert "read -r -p" in script_text
    assert "DRY_RUN" in script_text

    # 7. Perform Remediation Action
    f_id = first_finding["id"]
    action_res = client.post(f"/api/v1/optimizer/remediate-action?finding_id={f_id}&action=remediated")
    assert action_res.status_code == 200
    assert action_res.json()["new_status"] == "remediated"

def test_custom_rule_lifecycle(client):
    # 1. Create a declarative custom rule
    rule_payload = {
        "id": "test-custom-high-cost-disk",
        "name": "High Cost Detached Storage",
        "description": "Detached disk costing > $20",
        "provider": "gcp",
        "resource_type": "disk",
        "conditions": [
            {"field": "cost_amount", "operator": ">", "value": 20},
            {"field": "status_hint", "operator": "==", "value": "unattached"}
        ],
        "severity": "CRITICAL"
    }
    create_res = client.post("/api/v1/rules", json=rule_payload)
    assert create_res.status_code == 200
    assert create_res.json()["status"] == "success"

    # 2. List rules
    list_res = client.get("/api/v1/rules")
    assert list_res.status_code == 200
    rules = list_res.json()
    assert any(r["id"] == "test-custom-high-cost-disk" for r in rules["custom_rules"])

    # 3. Toggle rule
    toggle_res = client.put("/api/v1/rules/test-custom-high-cost-disk/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] is False

    # 4. Delete rule
    del_res = client.delete("/api/v1/rules/test-custom-high-cost-disk")
    assert del_res.status_code == 200

def test_load_samples_and_database_reset_lifecycle(client):
    # 1. Clear database first
    clear_res = client.post("/api/v1/billing/clear")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "success"

    # Verify 0 records
    rec_res = client.get("/api/v1/billing/records")
    assert rec_res.json()["total"] == 0

    # 2. Load samples
    load_res = client.post("/api/v1/billing/load-samples?clear_existing=true")
    assert load_res.status_code == 200
    first_count = load_res.json()["total_records_loaded"]
    assert first_count > 0

    # 3. Load samples AGAIN (should be idempotent with clear_existing=true)
    load_res_2 = client.post("/api/v1/billing/load-samples?clear_existing=true")
    assert load_res_2.status_code == 200
    second_count = load_res_2.json()["total_records_loaded"]
    assert second_count == first_count

    # Total in DB should still equal first_count (no duplicates added on top!)
    rec_res_2 = client.get("/api/v1/billing/records")
    assert rec_res_2.json()["total"] == first_count

    # 4. DELETE /billing/clear test
    del_clear = client.delete("/api/v1/billing/clear")
    assert del_clear.status_code == 200
    rec_res_3 = client.get("/api/v1/billing/records")
    assert rec_res_3.json()["total"] == 0

def test_expanded_rules_catalog(client):
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    data = res.json()
    assert data["total_rules"] >= 25
    assert data["tier_1_count"] >= 20
    assert data["tier_2_count"] >= 4
    # Certify components are populated
    for r in data["built_in_rules"]:
        assert "component" in r
        assert "provider" in r
        assert "description" in r

