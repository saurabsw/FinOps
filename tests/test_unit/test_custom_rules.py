import pytest
from backend.app.rules.custom_evaluator import CustomRuleEvaluator

def test_custom_rule_and_logic():
    rule = {
        "id": "rule-high-dev-disk",
        "name": "High Cost Dev Disks",
        "description": "Dev disks costing > $40",
        "provider": "gcp",
        "resource_type": "disk",
        "logic_operator": "all",
        "conditions": [
            {"field": "cost_amount", "operator": "greater_than", "value": 40.0},
            {"field": "status_hint", "operator": "equals", "value": "unattached"}
        ],
        "severity": "CRITICAL"
    }

    matching_res = {
        "cloud_provider": "gcp",
        "resource_type": "disk",
        "resource_id": "res-1",
        "resource_name": "dev-disk-1",
        "cost_amount": 65.0,
        "status_hint": "unattached",
        "region_or_zone": "us-central1-a",
        "project_id": "dev-proj"
    }

    result = CustomRuleEvaluator.evaluate(rule, matching_res)
    assert result is not None
    assert result.is_waste is True
    assert result.rule_id == "rule-high-dev-disk"
    assert result.severity == "CRITICAL"

    # Only one condition met (cost > 40, but status is active)
    active_res = dict(matching_res, status_hint="active")
    assert CustomRuleEvaluator.evaluate(rule, active_res) is None

def test_custom_rule_or_logic():
    rule = {
        "id": "rule-or-test",
        "name": "High Cost OR Stopped Instance",
        "provider": "*",
        "resource_type": "instance",
        "logic_operator": "any",
        "conditions": [
            {"field": "cost_amount", "operator": "greater_than", "value": 100.0},
            {"field": "status_hint", "operator": "equals", "value": "stopped"}
        ]
    }

    # Matches only condition 2 (cost is 20, but stopped)
    stopped_low_cost = {
        "cloud_provider": "gcp",
        "resource_type": "instance",
        "resource_id": "res-vm-1",
        "resource_name": "vm-1",
        "cost_amount": 20.0,
        "status_hint": "stopped",
        "project_id": "proj-1"
    }
    assert CustomRuleEvaluator.evaluate(rule, stopped_low_cost) is not None

def test_custom_rule_operators():
    # contains operator
    rule_contains = {
        "id": "rule-contains-zone",
        "name": "Specific Region Match",
        "provider": "*",
        "resource_type": "*",
        "logic_operator": "all",
        "conditions": [
            {"field": "region_or_zone", "operator": "contains", "value": "europe"}
        ]
    }

    eu_res = {"cloud_provider": "gcp", "resource_type": "disk", "region_or_zone": "europe-west1-b", "cost_amount": 10.0, "resource_id": "d1"}
    us_res = {"cloud_provider": "gcp", "resource_type": "disk", "region_or_zone": "us-central1-a", "cost_amount": 10.0, "resource_id": "d2"}

    assert CustomRuleEvaluator.evaluate(rule_contains, eu_res) is not None
    assert CustomRuleEvaluator.evaluate(rule_contains, us_res) is None

    # less_than operator
    rule_less = {
        "id": "rule-less",
        "name": "Small Waste",
        "provider": "*",
        "resource_type": "*",
        "logic_operator": "all",
        "conditions": [
            {"field": "cost_amount", "operator": "less_than", "value": 15.0}
        ]
    }
    assert CustomRuleEvaluator.evaluate(rule_less, {"cost_amount": 10.0, "resource_id": "r1"}) is not None
    assert CustomRuleEvaluator.evaluate(rule_less, {"cost_amount": 20.0, "resource_id": "r2"}) is None

def test_custom_rule_templated_commands():
    rule_template = {
        "id": "rule-templated",
        "name": "Custom Command Template",
        "provider": "gcp",
        "resource_type": "disk",
        "logic_operator": "all",
        "conditions": [{"field": "cost_amount", "operator": "greater_than", "value": 5.0}],
        "inspect_template": "gcloud compute disks describe <resource_name> --zone <region_or_zone>",
        "remediation_template": "gcloud compute disks delete <resource_name> --zone <region_or_zone> --quiet"
    }

    res = {
        "cloud_provider": "gcp",
        "resource_type": "disk",
        "resource_id": "res-123",
        "resource_name": "disk-custom-1",
        "region_or_zone": "us-central1-b",
        "cost_amount": 25.0
    }

    result = CustomRuleEvaluator.evaluate(rule_template, res)
    assert result is not None
    assert "gcloud compute disks describe disk-custom-1 --zone us-central1-b" in result.inspect_command
    # Notice that "--quiet" was passed in template, but MUST be sanitized out!
    assert "--quiet" not in result.remediation_command
    assert "gcloud compute disks delete disk-custom-1 --zone us-central1-b" == result.remediation_command
