import pytest
from app.engine.built_in_rules import (
    OrphanDiskRule,
    IdleStaticIPRule,
    IdleStoppedVMRule,
    StaleSnapshotRule
)
from app.engine.rule_configurator import CustomRuleEvaluator

def test_orphan_disk_rule_detects_waste():
    rule = OrphanDiskRule()
    unattached_disk = {
        "provider": "gcp",
        "resource_type": "disk",
        "resource_id": "projects/my-p/zones/us-central1-a/disks/disk-orphan",
        "resource_name": "disk-orphan",
        "region_or_zone": "us-central1-a",
        "project_or_account_id": "my-p",
        "cost_amount": 85.0,
        "currency": "USD",
        "usage_amount": 0.0,
        "status_hint": "unattached",
        "metadata": {"attached_vm": None, "idle_days": 40}
    }
    result = rule.evaluate(unattached_disk)
    assert result is not None
    assert result.is_waste is True
    assert result.monthly_savings_estimate == 85.0
    assert "gcloud compute disks delete" in result.remediation_command

def test_orphan_disk_zero_false_positive_on_active_disk():
    rule = OrphanDiskRule()
    active_disk = {
        "provider": "gcp",
        "resource_type": "disk",
        "resource_id": "projects/my-p/zones/us-central1-a/disks/disk-active",
        "resource_name": "disk-active",
        "region_or_zone": "us-central1-a",
        "project_or_account_id": "my-p",
        "cost_amount": 95.0,
        "currency": "USD",
        "usage_amount": 720.0,
        "status_hint": "active",
        "metadata": {"attached_vm": "vm-prod-01"}
    }
    result = rule.evaluate(active_disk)
    assert result is None, "Active attached disk should NOT be flagged as waste!"

def test_idle_ip_rule():
    rule = IdleStaticIPRule()
    idle_ip = {
        "provider": "gcp",
        "resource_type": "ip",
        "resource_id": "projects/my-p/regions/us-central1/addresses/ip-unassigned",
        "resource_name": "ip-unassigned",
        "region_or_zone": "us-central1",
        "project_or_account_id": "my-p",
        "cost_amount": 14.40,
        "currency": "USD",
        "usage_amount": 720.0,
        "status_hint": "unattached",
        "metadata": {"ip_address": "35.200.10.5"}
    }
    result = rule.evaluate(idle_ip)
    assert result is not None
    assert result.is_waste is True
    assert result.category == "Idle IP"

    # Active IP should NOT be flagged
    active_ip = dict(idle_ip, status_hint="active")
    assert rule.evaluate(active_ip) is None

def test_stopped_vm_rule():
    rule = IdleStoppedVMRule()
    stopped_vm = {
        "provider": "gcp",
        "resource_type": "instance",
        "resource_id": "projects/my-p/zones/us-central1-a/instances/vm-stopped",
        "resource_name": "vm-stopped",
        "region_or_zone": "us-central1-a",
        "project_or_account_id": "my-p",
        "cost_amount": 120.0,
        "currency": "USD",
        "usage_amount": 0.0,
        "status_hint": "stopped",
        "metadata": {"vm_state": "TERMINATED", "idle_days": 25}
    }
    result = rule.evaluate(stopped_vm)
    assert result is not None
    assert result.is_waste is True
    assert result.severity == "CRITICAL"

    # Active running VM should NOT be flagged
    running_vm = dict(stopped_vm, status_hint="active", metadata={"vm_state": "RUNNING"})
    assert rule.evaluate(running_vm) is None

def test_stale_snapshot_rule():
    rule = StaleSnapshotRule()
    stale_snap = {
        "provider": "gcp",
        "resource_type": "snapshot",
        "resource_id": "projects/my-p/global/snapshots/snap-old",
        "resource_name": "snap-old",
        "region_or_zone": "global",
        "project_or_account_id": "my-p",
        "cost_amount": 35.0,
        "currency": "USD",
        "usage_amount": 350.0,
        "status_hint": "stale",
        "metadata": {"snapshot_age_days": 120}
    }
    result = rule.evaluate(stale_snap)
    assert result is not None
    assert result.is_waste is True

    # Fresh snapshot (<30 days) should NOT be flagged
    fresh_snap = dict(stale_snap, status_hint="active", metadata={"snapshot_age_days": 5})
    assert rule.evaluate(fresh_snap) is None

def test_custom_rule_evaluator():
    custom_rule = {
        "id": "custom-dev-high-cost",
        "name": "High Cost Dev Resource",
        "description": "Dev resources exceeding $50/mo",
        "provider": "*",
        "resource_type": "*",
        "conditions": [
            {"field": "cost_amount", "operator": ">", "value": 50},
            {"field": "tags.env", "operator": "==", "value": "dev"}
        ],
        "severity": "HIGH",
        "inspect_template": "echo inspect {resource_name}",
        "remediation_template": "echo decommission {resource_name}"
    }

    matching_res = {
        "provider": "gcp",
        "resource_type": "disk",
        "resource_id": "res-123",
        "resource_name": "dev-expensive-disk",
        "project_or_account_id": "my-dev",
        "region_or_zone": "us-central1-a",
        "cost_amount": 80.0,
        "currency": "USD",
        "tags": {"env": "dev"}
    }

    result = CustomRuleEvaluator.evaluate(custom_rule, matching_res)
    assert result is not None
    assert result.is_waste is True
    assert result.rule_id == "custom-dev-high-cost"
    assert "echo decommission dev-expensive-disk" in result.remediation_command

    # Non-matching resource (cost < 50)
    low_cost_res = dict(matching_res, cost_amount=20.0)
    assert CustomRuleEvaluator.evaluate(custom_rule, low_cost_res) is None
