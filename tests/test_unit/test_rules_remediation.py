import pytest
from backend.app.rules.best_practices import (
    GCPOrphanDiskRule,
    GCPUnusedExternalIPRule,
    GCPIdleComputeInstanceRule,
    AWSUnattachedEBSVolumeRule,
    AWSUnassociatedElasticIPRule,
    AzureUnattachedManagedDiskRule,
    AzureUnassociatedPublicIPRule,
    BEST_PRACTICE_RULES
)
from backend.app.remediation import (
    validate_remediation_safety,
    sanitize_remediation_command,
    generate_resource_commands,
    generate_bash_remediation_script,
    FORBIDDEN_FORCE_FLAGS
)

def test_all_rules_detect_waste():
    rules_and_inputs = [
        (GCPOrphanDiskRule(), {
            "cloud_provider": "gcp", "resource_type": "disk", "resource_id": "projects/p/zones/z/disks/d-orphan",
            "resource_name": "d-orphan", "region_or_zone": "us-central1-a", "project_id": "p",
            "cost_amount": 50.0, "status_hint": "unattached", "metadata": {"attached_vm": None}
        }),
        (GCPUnusedExternalIPRule(), {
            "cloud_provider": "gcp", "resource_type": "ip", "resource_id": "projects/p/regions/r/addresses/ip-idle",
            "resource_name": "ip-idle", "region_or_zone": "us-central1", "project_id": "p",
            "cost_amount": 14.40, "status_hint": "unattached", "metadata": {}
        }),
        (GCPIdleComputeInstanceRule(), {
            "cloud_provider": "gcp", "resource_type": "instance", "resource_id": "projects/p/zones/z/instances/vm-stopped",
            "resource_name": "vm-stopped", "region_or_zone": "us-central1-a", "project_id": "p",
            "cost_amount": 120.0, "status_hint": "stopped", "metadata": {"vm_state": "TERMINATED"}
        }),
        (AWSUnattachedEBSVolumeRule(), {
            "cloud_provider": "aws", "resource_type": "disk", "resource_id": "vol-12345",
            "resource_name": "vol-12345", "region_or_zone": "us-east-1", "project_id": "acc-1",
            "cost_amount": 45.0, "status_hint": "unattached", "metadata": {}
        }),
        (AWSUnassociatedElasticIPRule(), {
            "cloud_provider": "aws", "resource_type": "ip", "resource_id": "eipalloc-123",
            "resource_name": "eipalloc-123", "region_or_zone": "us-east-1", "project_id": "acc-1",
            "cost_amount": 7.20, "status_hint": "unattached", "metadata": {}
        }),
        (AzureUnattachedManagedDiskRule(), {
            "cloud_provider": "azure", "resource_type": "disk", "resource_id": "d-az-1",
            "resource_name": "d-az-1", "region_or_zone": "eastus", "project_id": "sub-1",
            "cost_amount": 60.0, "status_hint": "unattached", "metadata": {}
        }),
        (AzureUnassociatedPublicIPRule(), {
            "cloud_provider": "azure", "resource_type": "ip", "resource_id": "pip-az-1",
            "resource_name": "pip-az-1", "region_or_zone": "eastus", "project_id": "sub-1",
            "cost_amount": 8.0, "status_hint": "unattached", "metadata": {}
        })
    ]

    for rule, waste_input in rules_and_inputs:
        result = rule.evaluate(waste_input)
        assert result is not None, f"Rule {rule.name} failed to identify waste!"
        assert result.is_waste is True
        assert result.monthly_savings_estimate > 0
        assert validate_remediation_safety(result.remediation_command), f"Unsafe command: {result.remediation_command}"

def test_zero_false_positives_on_active_resources():
    active_gcp_disk = {
        "cloud_provider": "gcp", "resource_type": "disk", "resource_id": "projects/p/zones/z/disks/d-active",
        "resource_name": "d-active", "region_or_zone": "us-central1-a", "project_id": "p",
        "cost_amount": 95.0, "usage_amount": 720.0, "status_hint": "active",
        "metadata": {"attached_vm": "vm-prod-01"}
    }
    assert GCPOrphanDiskRule().evaluate(active_gcp_disk) is None

    active_gcp_ip = {
        "cloud_provider": "gcp", "resource_type": "ip", "resource_id": "ip-active",
        "resource_name": "ip-active", "region_or_zone": "us-central1", "project_id": "p",
        "cost_amount": 14.40, "status_hint": "active", "metadata": {}
    }
    assert GCPUnusedExternalIPRule().evaluate(active_gcp_ip) is None

    active_gcp_vm = {
        "cloud_provider": "gcp", "resource_type": "instance", "resource_id": "vm-active",
        "resource_name": "vm-active", "region_or_zone": "us-central1-a", "project_id": "p",
        "cost_amount": 150.0, "status_hint": "active", "metadata": {"vm_state": "RUNNING"}
    }
    assert GCPIdleComputeInstanceRule().evaluate(active_gcp_vm) is None

def test_remediation_omits_quiet_and_yes_flags():
    inspect_cmd, remediate_cmd = generate_resource_commands(
        provider="gcp",
        resource_type="disk",
        resource_id="projects/my-p/zones/us-central1-a/disks/my-disk",
        resource_name="my-disk",
        region_or_zone="us-central1-a",
        project_or_account_id="my-p"
    )

    # Assert inspection command formatting
    assert inspect_cmd.startswith("gcloud compute disks describe my-disk")
    assert "--zone us-central1-a" in inspect_cmd
    assert "--project my-p" in inspect_cmd

    # Assert remediation command formatting
    assert remediate_cmd.startswith("gcloud compute disks delete my-disk")
    assert "--quiet" not in remediate_cmd
    assert "-y" not in remediate_cmd
    assert "--yes" not in remediate_cmd
    assert "-q" not in remediate_cmd
    assert validate_remediation_safety(remediate_cmd)

def test_bash_script_confirmation_gate():
    findings = [
        {
            "resource_id": "projects/my-p/zones/us-central1-a/disks/disk-orphaned",
            "resource_name": "disk-orphaned",
            "provider": "gcp",
            "category": "Orphan Disk",
            "monthly_savings_estimate": 85.0,
            "currency": "USD",
            "inspect_command": "gcloud compute disks describe disk-orphaned --zone us-central1-a --project my-p",
            "remediation_command": "gcloud compute disks delete disk-orphaned --zone us-central1-a --project my-p"
        }
    ]

    script = generate_bash_remediation_script(findings)
    assert 'read -r -p "Confirm decommission of <projects/my-p/zones/us-central1-a/disks/disk-orphaned>? (yes/no): "' in script
    assert "DRY_RUN" in script
    for flag in FORBIDDEN_FORCE_FLAGS:
        assert flag not in script
