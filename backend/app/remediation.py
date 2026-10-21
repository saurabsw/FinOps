import re
from typing import Dict, Any, List, Tuple

FORBIDDEN_FORCE_FLAGS = [
    "--quiet", "-q", "-y", "--yes", "--force", "-f",
    "--auto-approve", "--noconfirm"
]

def sanitize_remediation_command(cmd: str) -> str:
    """Removes destructive force flags, guaranteeing interactive confirmation."""
    cleaned = cmd
    for flag in FORBIDDEN_FORCE_FLAGS:
        pattern = rf"(?<=\s){re.escape(flag)}(?=\s|$)"
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def validate_remediation_safety(cmd: str) -> bool:
    """Certifies absence of automatic deletion flags."""
    tokens = cmd.split()
    return not any(flag in tokens for flag in FORBIDDEN_FORCE_FLAGS)

def generate_resource_commands(
    provider: str,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    region_or_zone: str,
    project_or_account_id: str,
    metadata: Dict[str, Any] = None
) -> Tuple[str, str]:
    """
    Generates:
    1) Inspection Command: Read-only live verification command.
    2) Remediation Command: Interactive deletion command strictly omitting force flags.
    """
    metadata = metadata or {}
    zone = region_or_zone or "us-central1-a"
    region = "-".join(zone.split("-")[:2]) if "-" in zone else zone
    clean_name = resource_name or (resource_id.split("/")[-1] if "/" in resource_id else resource_id)
    prov = (provider or "gcp").lower()

    if prov == "gcp":
        if resource_type == "disk":
            inspect_cmd = f"gcloud compute disks describe {clean_name} --zone {zone} --project {project_or_account_id}"
            remediate_cmd = f"gcloud compute disks delete {clean_name} --zone {zone} --project {project_or_account_id}"
        elif resource_type == "ip":
            inspect_cmd = f"gcloud compute addresses describe {clean_name} --region {region} --project {project_or_account_id}"
            remediate_cmd = f"gcloud compute addresses delete {clean_name} --region {region} --project {project_or_account_id}"
        elif resource_type == "instance":
            inspect_cmd = f"gcloud compute instances describe {clean_name} --zone {zone} --project {project_or_account_id}"
            remediate_cmd = f"gcloud compute instances delete {clean_name} --zone {zone} --project {project_or_account_id}"
        elif resource_type == "snapshot":
            inspect_cmd = f"gcloud compute snapshots describe {clean_name} --project {project_or_account_id}"
            remediate_cmd = f"gcloud compute snapshots delete {clean_name} --project {project_or_account_id}"
        elif resource_type in ["load_balancer", "lb", "forwarding_rule"]:
            inspect_cmd = f"gcloud compute forwarding-rules describe {clean_name} --region {region} --project {project_or_account_id}"
            remediate_cmd = f"gcloud compute forwarding-rules delete {clean_name} --region {region} --project {project_or_account_id}"
        elif resource_type in ["database", "db", "sql"]:
            inspect_cmd = f"gcloud sql instances describe {clean_name} --project {project_or_account_id}"
            remediate_cmd = f"gcloud sql instances delete {clean_name} --project {project_or_account_id}"
        elif resource_type in ["bucket", "storage"]:
            inspect_cmd = f"gcloud storage buckets describe gs://{clean_name}"
            remediate_cmd = f"gcloud storage buckets update gs://{clean_name} --lifecycle-file=lifecycle_policy.json"
        elif resource_type in ["cache", "redis"]:
            inspect_cmd = f"gcloud redis instances describe {clean_name} --region {region} --project {project_or_account_id}"
            remediate_cmd = f"gcloud redis instances delete {clean_name} --region {region} --project {project_or_account_id}"
        else:
            inspect_cmd = f"gcloud resource-manager tags bindings list --parent={resource_id}"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name} in {project_or_account_id}"

    elif prov == "aws":
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
        elif resource_type in ["load_balancer", "lb"]:
            inspect_cmd = f"aws elbv2 describe-load-balancers --names {clean_name} --region {region}"
            remediate_cmd = f"aws elbv2 delete-load-balancer --load-balancer-arn {resource_id} --region {region}"
        elif resource_type in ["database", "db", "rds"]:
            inspect_cmd = f"aws rds describe-db-instances --db-instance-identifier {clean_name} --region {region}"
            remediate_cmd = f"aws rds stop-db-instance --db-instance-identifier {clean_name} --region {region}"
        elif resource_type in ["bucket", "storage"]:
            inspect_cmd = f"aws s3api get-bucket-lifecycle-configuration --bucket {clean_name} --region {region}"
            remediate_cmd = f"aws s3api put-bucket-lifecycle-configuration --bucket {clean_name} --lifecycle-configuration file://lifecycle.json"
        elif resource_type in ["nat_gateway", "nat"]:
            inspect_cmd = f"aws ec2 describe-nat-gateways --nat-gateway-ids {clean_name} --region {region}"
            remediate_cmd = f"aws ec2 delete-nat-gateway --nat-gateway-id {clean_name} --region {region}"
        elif resource_type in ["cache", "elasticache"]:
            inspect_cmd = f"aws elasticache describe-cache-clusters --cache-cluster-id {clean_name} --region {region}"
            remediate_cmd = f"aws elasticache delete-cache-cluster --cache-cluster-id {clean_name} --region {region}"
        else:
            inspect_cmd = f"aws resourcegroupstaggingapi get-resources --resource-arn-list {resource_id}"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name}"

    elif prov == "azure":
        rg = metadata.get("resource_group") or "default-rg"
        if resource_type == "disk":
            inspect_cmd = f"az disk show --resource-group {rg} --name {clean_name}"
            remediate_cmd = f"az disk delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "ip":
            inspect_cmd = f"az network public-ip show --resource-group {rg} --name {clean_name}"
            remediate_cmd = f"az network public-ip delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "instance":
            inspect_cmd = f"az vm show --resource-group {rg} --name {clean_name}"
            remediate_cmd = f"az vm delete --resource-group {rg} --name {clean_name}"
        elif resource_type == "snapshot":
            inspect_cmd = f"az snapshot show --resource-group {rg} --name {clean_name}"
            remediate_cmd = f"az snapshot delete --resource-group {rg} --name {clean_name}"
        elif resource_type in ["load_balancer", "lb"]:
            inspect_cmd = f"az network lb show --resource-group {rg} --name {clean_name}"
            remediate_cmd = f"az network lb delete --resource-group {rg} --name {clean_name}"
        elif resource_type in ["database", "db", "sql"]:
            inspect_cmd = f"az sql db show --resource-group {rg} --server {clean_name}-srv --name {clean_name}"
            remediate_cmd = f"az sql db delete --resource-group {rg} --server {clean_name}-srv --name {clean_name}"
        elif resource_type in ["bucket", "storage"]:
            inspect_cmd = f"az storage account management-policy show --account-name {clean_name} --resource-group {rg}"
            remediate_cmd = f"az storage account management-policy create --account-name {clean_name} --resource-group {rg} --policy @policy.json"
        else:
            inspect_cmd = f"az resource show --ids {resource_id}"
            remediate_cmd = f"# Review and decommission {resource_type} {clean_name}"

    else:
        inspect_cmd = f"echo 'Inspect resource: {clean_name}'"
        remediate_cmd = f"echo 'Remediate resource: {clean_name}'"

    return inspect_cmd, sanitize_remediation_command(remediate_cmd)

def generate_bash_remediation_script(findings: List[Dict[str, Any]]) -> str:
    """
    Generates interactive shell script wrapper with a user confirmation gate:
    read -r -p "Confirm decommission of <resource_id>? (yes/no): "
    """
    lines = [
        "#!/usr/bin/env bash",
        "# ==============================================================================",
        "# FinOps 2-Step Safe Remediation Script",
        "# Auto-generated by Multi-Cloud FinOps Cost Optimizer & Safe Remediation Engine",
        "# Non-interactive destructive force flags are strictly omitted.",
        "# ==============================================================================",
        "set -euo pipefail",
        "",
        "DRY_RUN=false",
        "if [[ \"${1:-}\" == \"--dry-run\" ]]; then",
        "  DRY_RUN=true",
        "  echo \"[DRY-RUN] Simulating remediation session. No changes will occur.\"",
        "fi",
        "",
        f"echo \"Starting safe remediation for {len(findings)} detected waste items...\"",
        "echo \"\""
    ]

    for idx, f in enumerate(findings, start=1):
        r_id = f.get("resource_id") or f"res-{idx}"
        r_name = f.get("resource_name") or r_id
        prov = f.get("provider", "gcp").upper()
        cat = f.get("category", "Waste")
        savings = float(f.get("monthly_savings_estimate") or 0.0)
        curr = f.get("currency", "USD")
        inspect = f.get("inspect_command", "")
        remediate = sanitize_remediation_command(f.get("remediation_command", ""))

        lines.extend([
            f"# Item {idx}/{len(findings)}: [{prov}] {r_name} ({cat}) - Est. Savings: {savings:.2f} {curr}/mo",
            f"echo \"===================================================================\"",
            f"echo \"==> [{idx}/{len(findings)}] Reviewing {cat}: {r_name}\"",
            f"echo \"[Step 1: Inspect Live Metadata]\"",
            f"echo \"$ {inspect}\"",
            f"if [ \"$DRY_RUN\" = false ]; then",
            f"  eval \"{inspect}\" || echo \"[WARN] Inspection failed or resource not accessible.\"",
            f"fi",
            f"",
            f"echo \"[Step 2: Interactive Confirmation Gate]\"",
            f"if [ \"$DRY_RUN\" = true ]; then",
            f"  echo \"[DRY-RUN] Would prompt for: {remediate}\"",
            f"else",
            f"  read -r -p \"Confirm decommission of <{r_id}>? (yes/no): \" CONFIRM_INPUT",
            f"  if [[ \"$CONFIRM_INPUT\" =~ ^[Yy][Ee][Ss]$ ]]; then",
            f"    echo \"Executing: {remediate}\"",
            f"    eval \"{remediate}\"",
            f"    echo \"[SUCCESS] Remediated {r_name}\"",
            f"  else",
            f"    echo \"[SKIPPED] Remediation skipped for {r_name}.\"",
            f"  fi",
            f"fi",
            f"echo \"\"",
            ""
        ])

    lines.extend([
        "echo \"===================================================================\"",
        "echo \" Remediation session complete. Review audit logs above.\"",
        "echo \"=================================================================\""
    ])

    return "\n".join(lines)
