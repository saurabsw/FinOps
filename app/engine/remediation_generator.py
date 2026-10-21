import re
from typing import Dict, Any, List

# Forbidden non-interactive force flags that would bypass human confirmation
FORBIDDEN_FORCE_FLAGS = [
    "--quiet", "-q", "-y", "--yes", "--force", "-f",
    "--auto-approve", "--noconfirm"
]

def sanitize_remediation_command(cmd: str) -> str:
    """
    Enforces Rule Section 3.3:
    Removes any non-interactive flags (--quiet, -y, --yes, etc.)
    Ensures safe interactive execution requiring user confirmation.
    """
    cleaned = cmd
    for flag in FORBIDDEN_FORCE_FLAGS:
        # Match whole flag with boundary
        pattern = rf"(?<=\s){re.escape(flag)}(?=\s|$)"
        cleaned = re.sub(pattern, "", cleaned)
    # Clean redundant spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def validate_remediation_safety(cmd: str) -> bool:
    """Returns True if the command is free of automatic destructive flags."""
    tokens = cmd.split()
    for flag in FORBIDDEN_FORCE_FLAGS:
        if flag in tokens:
            return False
    return True

def generate_commands_for_resource(
    provider: str,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    region_or_zone: str,
    project_or_account_id: str,
    metadata: Dict[str, Any] = None
) -> (str, str):
    """
    Generates:
    1. Selection / Inspection Command: Read-only CLI inspection showing metadata/tags/dependencies.
    2. Interactive Remediation Command: Execution command strictly interactive without auto-delete flags.
    """
    metadata = metadata or {}
    zone = region_or_zone or "us-central1-a"
    # Derive region if zone is provided (e.g. us-central1-a -> us-central1)
    region = "-".join(zone.split("-")[:2]) if "-" in zone else zone

    clean_name = resource_name or (resource_id.split("/")[-1] if "/" in resource_id else resource_id)

    if provider == "gcp":
        if resource_type == "disk":
            inspect_cmd = f"gcloud compute disks describe {clean_name} --project={project_or_account_id} --zone={zone} --format='yaml(name,sizeGb,status,users,lastAttachTimestamp)'"
            remediate_cmd = f"gcloud compute disks delete {clean_name} --project={project_or_account_id} --zone={zone}"
        elif resource_type == "ip":
            inspect_cmd = f"gcloud compute addresses describe {clean_name} --project={project_or_account_id} --region={region} --format='yaml(name,address,status,users)'"
            remediate_cmd = f"gcloud compute addresses delete {clean_name} --project={project_or_account_id} --region={region}"
        elif resource_type == "instance":
            inspect_cmd = f"gcloud compute instances describe {clean_name} --project={project_or_account_id} --zone={zone} --format='yaml(name,status,machineType,disks,networkInterfaces)'"
            remediate_cmd = f"gcloud compute instances delete {clean_name} --project={project_or_account_id} --zone={zone}"
        elif resource_type == "snapshot":
            inspect_cmd = f"gcloud compute snapshots describe {clean_name} --project={project_or_account_id} --format='yaml(name,diskSizeGb,sourceDisk,creationTimestamp)'"
            remediate_cmd = f"gcloud compute snapshots delete {clean_name} --project={project_or_account_id}"
        else:
            inspect_cmd = f"gcloud resource-manager tags bindings list --parent={resource_id}"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name} in {project_or_account_id}"

    elif provider == "aws":
        if resource_type == "disk":
            inspect_cmd = f"aws ec2 describe-volumes --volume-ids {clean_name} --region {region}"
            remediate_cmd = f"aws ec2 delete-volume --volume-id {clean_name} --region {region}"
        elif resource_type == "ip":
            inspect_cmd = f"aws ec2 describe-addresses --allocation-ids {clean_name} --region {region}"
            remediate_cmd = f"aws ec2 release-address --allocation-id {clean_name} --region {region}"
        elif resource_type == "instance":
            inspect_cmd = f"aws ec2 describe-instances --instance-ids {clean_name} --region {region}"
            remediate_cmd = f"aws ec2 terminate-instances --instance-ids {clean_name} --region {region}"
        elif resource_type == "snapshot":
            inspect_cmd = f"aws ec2 describe-snapshots --snapshot-ids {clean_name} --region {region}"
            remediate_cmd = f"aws ec2 delete-snapshot --snapshot-id {clean_name} --region {region}"
        else:
            inspect_cmd = f"aws resourcegroupstaggingapi get-resources --resource-arn-list {resource_id}"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name}"

    elif provider == "azure":
        rg = metadata.get("resource_group") or "default-rg"
        if resource_type == "disk":
            inspect_cmd = f"az disk show --resource-group {rg} --name {clean_name} --output json"
            remediate_cmd = f"az disk delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "ip":
            inspect_cmd = f"az network public-ip show --resource-group {rg} --name {clean_name} --output json"
            remediate_cmd = f"az network public-ip delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "instance":
            inspect_cmd = f"az vm show --resource-group {rg} --name {clean_name} --output json"
            remediate_cmd = f"az vm delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "snapshot":
            inspect_cmd = f"az snapshot show --resource-group {rg} --name {clean_name} --output json"
            remediate_cmd = f"az snapshot delete --resource-group {rg} --name {clean_name}"
        else:
            inspect_cmd = f"az resource show --ids {resource_id} --output json"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name}"

    else:
        inspect_cmd = f"echo 'Inspect resource: {clean_name}'"
        remediate_cmd = f"echo 'Remediate resource: {clean_name}'"

    remediate_cmd = sanitize_remediation_command(remediate_cmd)
    return inspect_cmd, remediate_cmd

def build_safety_gated_bash_script(findings: List[Dict[str, Any]]) -> str:
    """
    Generates the enterprise-grade remediate_waste.sh script featuring:
    - Clear safety warnings and dry-run flag support
    - Step 1: Live inspection call
    - Step 2: Strict human confirmation gate (read -r -p "Delete resource? (yes/no)")
    - Zero auto-delete force flags
    """
    lines = [
        "#!/usr/bin/env bash",
        "# ==============================================================================",
        "# FinOps Safe Remediation Engine - Automated Interactive Cleanup Script",
        "# Generated by Multi-Cloud FinOps Cost Optimizer & Safe Remediation Engine",
        "# Safety Pattern: Enterprise 'Inspect-then-Confirm' 2-Step Gate",
        "# Non-interactive destructive override flags are strictly disallowed.",
        "# ==============================================================================",
        "set -euo pipefail",
        "",
        "DRY_RUN=false",
        "if [[ \"${1:-}\" == \"--dry-run\" ]]; then",
        "  DRY_RUN=true",
        "  echo \"[INFO] Running in DRY-RUN mode. No changes will be executed.\"",
        "fi",
        "",
        "echo \"=================================================================\"",
        "echo \" Starting Safe Remediation Session: " + str(len(findings)) + " findings to inspect \"",
        "echo \"=================================================================\"",
        ""
    ]

    for idx, f in enumerate(findings, start=1):
        r_name = f.get("resource_name") or f.get("resource_id")
        provider = f.get("provider", "gcp").upper()
        category = f.get("category", "Waste")
        savings = f.get("monthly_savings_estimate", 0.0)
        currency = f.get("currency", "USD")
        inspect = f.get("inspect_command", "")
        remediate = sanitize_remediation_command(f.get("remediation_command", ""))

        lines.extend([
            f"# ------------------------------------------------------------------------------",
            f"# Finding {idx}/{len(findings)}: [{provider}] {r_name} ({category})",
            f"# Estimated Monthly Savings: {savings:.2f} {currency}",
            f"# Reason: {f.get('reason', 'Detected waste')}",
            f"# ------------------------------------------------------------------------------",
            f"echo \"\"",
            f"echo \"==> [{idx}/{len(findings)}] Reviewing {category}: {r_name} (Est. Savings: {savings:.2f} {currency})\"",
            f"echo \"[STEP 1: INSPECTION] Running live read-only verification:\"",
            f"echo \"$ {inspect}\"",
            f"if [ \"$DRY_RUN\" = false ]; then",
            f"  eval \"{inspect}\" || echo \"[WARN] Inspection failed or resource not found.\"",
            f"fi",
            f"",
            f"echo \"[STEP 2: CONFIRMATION GATE]\"",
            f"if [ \"$DRY_RUN\" = true ]; then",
            f"  echo \"[DRY RUN] Would execute: {remediate}\"",
            f"else",
            f"  read -r -p \"Execute remediation for '{r_name}'? (yes/no): \" CONFIRM_INPUT",
            f"  if [[ \"$CONFIRM_INPUT\" =~ ^[Yy][Ee][Ss]$ ]]; then",
            f"    echo \"Executing: {remediate}\"",
            f"    eval \"{remediate}\"",
            f"    echo \"[SUCCESS] Remediated {r_name}\"",
            f"  else",
            f"    echo \"[SKIPPED] Remediation skipped for {r_name}.\"",
            f"  fi",
            f"fi",
            ""
        ])

    lines.extend([
        "echo \"=================================================================\"",
        "echo \" Remediation session complete. Review audit logs above.\"",
        "echo \"=================================================================\""
    ])

    return "\n".join(lines)
