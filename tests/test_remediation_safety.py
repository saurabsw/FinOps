import pytest
from app.engine.remediation_generator import (
    sanitize_remediation_command,
    validate_remediation_safety,
    generate_commands_for_resource,
    build_safety_gated_bash_script,
    FORBIDDEN_FORCE_FLAGS
)

def test_forbidden_force_flags_sanitization():
    unsafe_commands = [
        "gcloud compute disks delete disk-1 --project=proj --zone=us-c1-a --quiet",
        "gcloud compute instances delete vm-1 -q",
        "gcloud compute addresses delete ip-1 -y",
        "aws ec2 delete-volume --volume-id vol-123 --yes",
        "az disk delete --name d1 -f --auto-approve"
    ]

    for raw_cmd in unsafe_commands:
        sanitized = sanitize_remediation_command(raw_cmd)
        assert validate_remediation_safety(sanitized), f"Command still contains force flag: {sanitized}"
        for flag in FORBIDDEN_FORCE_FLAGS:
            tokens = sanitized.split()
            assert flag not in tokens, f"Flag {flag} found in {sanitized}"

def test_generate_commands_includes_inspection():
    inspect_cmd, remediate_cmd = generate_commands_for_resource(
        provider="gcp",
        resource_type="disk",
        resource_id="projects/test/zones/us-central1-a/disks/test-disk",
        resource_name="test-disk",
        region_or_zone="us-central1-a",
        project_or_account_id="test-project"
    )

    # Inspection command must be read-only describe
    assert "gcloud compute disks describe" in inspect_cmd
    assert "--project=test-project" in inspect_cmd
    assert "--zone=us-central1-a" in inspect_cmd

    # Remediation command must delete interactively (no force flags)
    assert "gcloud compute disks delete" in remediate_cmd
    assert "--quiet" not in remediate_cmd
    assert "-y" not in remediate_cmd
    assert validate_remediation_safety(remediate_cmd)

def test_safety_gated_bash_script_generation():
    sample_findings = [
        {
            "resource_id": "projects/my-p/zones/us-c1-a/disks/disk-orphan-1",
            "resource_name": "disk-orphan-1",
            "provider": "gcp",
            "category": "Orphan Disk",
            "monthly_savings_estimate": 85.00,
            "currency": "USD",
            "reason": "Detached persistent disk",
            "inspect_command": "gcloud compute disks describe disk-orphan-1 --project=my-p --zone=us-c1-a",
            "remediation_command": "gcloud compute disks delete disk-orphan-1 --project=my-p --zone=us-c1-a"
        }
    ]

    script = build_safety_gated_bash_script(sample_findings)

    # Must contain bash header
    assert "#!/usr/bin/env bash" in script
    # Must support dry-run flag
    assert "DRY_RUN=false" in script
    assert "--dry-run" in script
    # Must contain inspection step
    assert "gcloud compute disks describe disk-orphan-1" in script
    # Must contain human confirmation gate
    assert 'read -r -p "Execute remediation for \'disk-orphan-1\'? (yes/no): "' in script
    # Must NOT contain forbidden flags
    for flag in FORBIDDEN_FORCE_FLAGS:
        assert flag not in script
