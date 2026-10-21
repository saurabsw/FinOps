from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from backend.app.remediation import generate_resource_commands

@dataclass
class WasteEvaluationResult:
    is_waste: bool
    rule_id: str
    rule_name: str
    category: str
    severity: str
    monthly_savings_estimate: float
    currency: str
    reason: str
    inspect_command: str
    remediation_command: str

class BestPracticeRule:
    """Base class for deterministic vendor FinOps rules."""
    @property
    def rule_id(self) -> str:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def category(self) -> str:
        raise NotImplementedError

    @property
    def severity(self) -> str:
        raise NotImplementedError

    @property
    def component(self) -> str:
        return "Compute & Storage"

    @property
    def provider(self) -> str:
        return "multi-cloud"

    @property
    def description(self) -> str:
        return "Deterministic multi-cloud FinOps best practice detection rule."

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        raise NotImplementedError

# 1. GCP Orphaned Persistent Disk
class GCPOrphanDiskRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-orphan-disk"

    @property
    def name(self) -> str:
        return "GCP Orphaned Persistent Disk"

    @property
    def category(self) -> str:
        return "Orphan Disk"

    @property
    def severity(self) -> str:
        return "HIGH"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "gcp" or res.get("resource_type") != "disk":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        attached_vm = metadata.get("attached_vm")

        # Zero false positives on active attached resources
        if status == "active" and attached_vm not in [None, "", "null", "none"]:
            return None

        is_orphan = (
            status in ["unattached", "orphan", "detached", "idle"] or
            (attached_vm in [None, "", "null", "none"] and float(res.get("usage_amount", 0.0)) == 0.0 and cost > 0)
        )
        if not is_orphan or cost <= 0:
            return None

        inspect, remediate = generate_resource_commands(
            provider="gcp",
            resource_type="disk",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-central1-a"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=metadata
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="Persistent disk is unattached with 0 compute attachment hours, incurring unattached storage charges.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 2. GCP Unused Reserved External IP
class GCPUnusedExternalIPRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-unused-external-ip"

    @property
    def name(self) -> str:
        return "GCP Unused Reserved External IP"

    @property
    def category(self) -> str:
        return "Idle IP"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "gcp" or res.get("resource_type") != "ip":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status == "active" or cost <= 0:
            return None

        is_idle = status in ["unattached", "unassigned", "idle"]
        if not is_idle:
            return None

        metadata = res.get("metadata", {}) or {}
        inspect, remediate = generate_resource_commands(
            provider="gcp",
            resource_type="ip",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-central1"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=metadata
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="External static IP is reserved but unassigned, incurring idle reservation address fees.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 3. GCP Idle Compute VM
class GCPIdleComputeInstanceRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-idle-compute-vm"

    @property
    def name(self) -> str:
        return "GCP Idle Compute VM"

    @property
    def category(self) -> str:
        return "Idle VM"

    @property
    def severity(self) -> str:
        return "CRITICAL"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "gcp" or res.get("resource_type") != "instance":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        vm_state = str(metadata.get("vm_state", "")).upper()

        if status == "active" and vm_state not in ["STOPPED", "TERMINATED"]:
            return None

        is_stopped = status in ["stopped", "terminated", "idle"] or vm_state in ["STOPPED", "TERMINATED"]
        if not is_stopped or cost <= 0:
            return None

        inspect, remediate = generate_resource_commands(
            provider="gcp",
            resource_type="instance",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-central1-a"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=metadata
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="Compute VM is in stopped state while continuing to accrue persistent disk and IP reservation costs.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 4. AWS Unattached EBS Volume
class AWSUnattachedEBSVolumeRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-unattached-ebs-volume"

    @property
    def name(self) -> str:
        return "AWS Unattached EBS Volume"

    @property
    def category(self) -> str:
        return "Orphan Disk"

    @property
    def severity(self) -> str:
        return "HIGH"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "aws" or res.get("resource_type") != "disk":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status == "active" or cost <= 0:
            return None

        is_unattached = status in ["unattached", "available", "orphan"]
        if not is_unattached:
            return None

        inspect, remediate = generate_resource_commands(
            provider="aws",
            resource_type="disk",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-east-1"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="EBS volume is unattached with status available, incurring continuous storage fees.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 5. AWS Unassociated Elastic IP
class AWSUnassociatedElasticIPRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-unassociated-elastic-ip"

    @property
    def name(self) -> str:
        return "AWS Unassociated Elastic IP"

    @property
    def category(self) -> str:
        return "Idle IP"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "aws" or res.get("resource_type") != "ip":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status == "active" or cost <= 0:
            return None

        if status not in ["unattached", "unassociated", "idle"]:
            return None

        inspect, remediate = generate_resource_commands(
            provider="aws",
            resource_type="ip",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-east-1"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="Elastic IP address is unassociated with any running instance or NAT gateway.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 6. Azure Unattached Managed Disk
class AzureUnattachedManagedDiskRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-unattached-managed-disk"

    @property
    def name(self) -> str:
        return "Azure Unattached Managed Disk"

    @property
    def category(self) -> str:
        return "Orphan Disk"

    @property
    def severity(self) -> str:
        return "HIGH"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "azure" or res.get("resource_type") != "disk":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status == "active" or cost <= 0:
            return None

        if status not in ["unattached", "unattached", "idle"]:
            return None

        inspect, remediate = generate_resource_commands(
            provider="azure",
            resource_type="disk",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "eastus"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="Managed Disk is unattached and accumulating storage reservation costs.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 7. Azure Unassociated Public IP
class AzureUnassociatedPublicIPRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-unassociated-public-ip"

    @property
    def name(self) -> str:
        return "Azure Unassociated Public IP"

    @property
    def category(self) -> str:
        return "Idle IP"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("provider", res.get("cloud_provider")) != "azure" or res.get("resource_type") != "ip":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status == "active" or cost <= 0:
            return None

        if status not in ["unattached", "unassociated", "idle"]:
            return None

        inspect, remediate = generate_resource_commands(
            provider="azure",
            resource_type="ip",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "eastus"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason="Azure Public IP address is not associated with any network interface or load balancer.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# Stale Snapshots (General)
class StaleSnapshotRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "stale-snapshot-rule"

    @property
    def name(self) -> str:
        return "Stale Storage Snapshot"

    @property
    def category(self) -> str:
        return "Stale Snapshot"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("resource_type") != "snapshot":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        age_days = int(metadata.get("snapshot_age_days") or 0)

        if status == "active" and age_days < 30:
            return None

        if status not in ["stale", "aged"] and age_days < 30:
            return None
        if cost <= 0:
            return None

        inspect, remediate = generate_resource_commands(
            provider=res.get("provider", res.get("cloud_provider", "gcp")),
            resource_type="snapshot",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "global"),
            project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=metadata
        )

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=f"Storage snapshot is {age_days or '>30'} days old, exceeding retention threshold.",
            inspect_command=inspect,
            remediation_command=remediate
        )

# 9. AWS Stopped EC2 Instance
class AWSStoppedEC2InstanceRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-stopped-ec2"
    @property
    def name(self) -> str:
        return "AWS Stopped EC2 Instance"
    @property
    def category(self) -> str:
        return "Stopped VM"
    @property
    def component(self) -> str:
        return "Compute"
    @property
    def provider(self) -> str:
        return "aws"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "EC2 virtual machine in stopped state continues incurring persistent EBS block storage charges."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "aws" or res.get("resource_type") != "instance":
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status not in ["stopped", "terminated", "idle"] or cost <= 0:
            return None
        inspect, remediate = generate_resource_commands(
            provider="aws", resource_type="instance",
            resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )
        return WasteEvaluationResult(
            is_waste=True, rule_id=self.rule_id, rule_name=self.name,
            category=self.category, severity=self.severity,
            monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
            reason="EC2 instance is stopped but continues accumulating EBS volume and allocation costs.",
            inspect_command=inspect, remediation_command=remediate
        )

# 10. Azure Stopped/Deallocated VM
class AzureDeallocatedVMRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-deallocated-vm"
    @property
    def name(self) -> str:
        return "Azure Stopped / Deallocated VM"
    @property
    def category(self) -> str:
        return "Stopped VM"
    @property
    def component(self) -> str:
        return "Compute"
    @property
    def provider(self) -> str:
        return "azure"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "Azure VM is deallocated while provisioned OS disks and network reservations continue accumulating cost."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "azure" or res.get("resource_type") != "instance":
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status not in ["stopped", "deallocated", "idle"] or cost <= 0:
            return None
        inspect, remediate = generate_resource_commands(
            provider="azure", resource_type="instance",
            resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", "eastus"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
            metadata=res.get("metadata", {})
        )
        return WasteEvaluationResult(
            is_waste=True, rule_id=self.rule_id, rule_name=self.name,
            category=self.category, severity=self.severity,
            monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
            reason="Deallocated VM retains provisioned OS disk without active computing workload.",
            inspect_command=inspect, remediation_command=remediate
        )

# 11. AWS Idle Load Balancer
class AWSIdleLoadBalancerRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-idle-load-balancer"
    @property
    def name(self) -> str:
        return "AWS Idle Application/Network Load Balancer"
    @property
    def category(self) -> str:
        return "Idle Load Balancer"
    @property
    def component(self) -> str:
        return "Networking"
    @property
    def provider(self) -> str:
        return "aws"
    @property
    def severity(self) -> str:
        return "HIGH"
    @property
    def description(self) -> str:
        return "ELB/ALB/NLB has 0 registered active targets or negligible request count over the billing cycle."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "aws" or res.get("resource_type") not in ["load_balancer", "lb"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["active"] and float(res.get("usage_amount", 0.0)) > 10.0:
            return None
        if (status in ["idle", "unattached", "empty", "no_targets"] or float(res.get("usage_amount", 0.0)) == 0.0) and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="aws", resource_type="load_balancer",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="Load balancer is provisioned with zero registered target instances or zero HTTP/TCP requests.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 12. GCP Idle Forwarding Rule
class GCPIdleForwardingRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-idle-forwarding-rule"
    @property
    def name(self) -> str:
        return "GCP Idle Forwarding Rule"
    @property
    def category(self) -> str:
        return "Idle Load Balancer"
    @property
    def component(self) -> str:
        return "Networking"
    @property
    def provider(self) -> str:
        return "gcp"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "GCP Cloud Load Balancing forwarding rule with 0 backend throughput or zero healthy backends."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "gcp" or res.get("resource_type") not in ["load_balancer", "lb", "forwarding_rule"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["active"] and float(res.get("usage_amount", 0.0)) > 5.0:
            return None
        if (status in ["idle", "unattached", "empty"] or float(res.get("usage_amount", 0.0)) == 0.0) and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="gcp", resource_type="load_balancer",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-central1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="Forwarding rule maintains hourly allocation charges without routing ingress network traffic.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 13. Azure Idle Load Balancer
class AzureIdleLoadBalancerRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-idle-load-balancer"
    @property
    def name(self) -> str:
        return "Azure Unused Load Balancer"
    @property
    def category(self) -> str:
        return "Idle Load Balancer"
    @property
    def component(self) -> str:
        return "Networking"
    @property
    def provider(self) -> str:
        return "azure"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "Azure Load Balancer provisioned with no backend pool members or 0 byte throughput."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "azure" or res.get("resource_type") not in ["load_balancer", "lb"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["active"] and float(res.get("usage_amount", 0.0)) > 5.0:
            return None
        if (status in ["idle", "unattached", "empty"] or float(res.get("usage_amount", 0.0)) == 0.0) and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="azure", resource_type="load_balancer",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "eastus"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="Azure Load Balancer has an empty backend pool while accumulating hourly deployment base fees.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 14. Cloud Idle NAT Gateway
class CloudIdleNATGatewayRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "cloud-idle-nat-gateway"
    @property
    def name(self) -> str:
        return "Idle Cloud NAT Gateway (0 GB Processed)"
    @property
    def category(self) -> str:
        return "Idle Gateway"
    @property
    def component(self) -> str:
        return "Networking"
    @property
    def provider(self) -> str:
        return "multi-cloud"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "Provisioned NAT Gateway incurring base hourly charges (~$32/mo) with zero egress bandwidth consumption."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("resource_type") not in ["nat_gateway", "nat"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if (status in ["idle", "unused"] or float(res.get("usage_amount", 0.0)) == 0.0) and cost > 0:
            prov = res.get("provider", res.get("cloud_provider", "aws"))
            inspect, remediate = generate_resource_commands(
                provider=prov, resource_type="nat_gateway",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="NAT Gateway incurring base hourly reservation cost with zero egress data processed.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 15. AWS S3 No Lifecycle Rule
class AWSS3NoLifecycleRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-s3-no-lifecycle"
    @property
    def name(self) -> str:
        return "AWS S3 Bucket Missing Lifecycle Expiration Policy"
    @property
    def category(self) -> str:
        return "Storage Lifecycle"
    @property
    def component(self) -> str:
        return "Storage & Backup"
    @property
    def provider(self) -> str:
        return "aws"
    @property
    def severity(self) -> str:
        return "LOW"
    @property
    def description(self) -> str:
        return "S3 standard storage bucket has no automated tiering to Glacier or expiration rule for old objects."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "aws" or res.get("resource_type") not in ["bucket", "storage"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["no_lifecycle", "unmanaged_storage"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="aws", resource_type="bucket",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost * 0.4, 2), currency=res.get("currency", "USD"),
                reason="S3 bucket stores objects indefinitely in standard tier; lifecycle policy can achieve ~40-70% savings.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 16. GCP Storage No Lifecycle Rule
class GCPStorageNoLifecycleRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-storage-no-lifecycle"
    @property
    def name(self) -> str:
        return "GCP Cloud Storage Lacking Lifecycle Rules"
    @property
    def category(self) -> str:
        return "Storage Lifecycle"
    @property
    def component(self) -> str:
        return "Storage & Backup"
    @property
    def provider(self) -> str:
        return "gcp"
    @property
    def severity(self) -> str:
        return "LOW"
    @property
    def description(self) -> str:
        return "Cloud Storage bucket does not auto-downgrade aged objects to Nearline, Coldline, or Archive."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "gcp" or res.get("resource_type") not in ["bucket", "storage"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["no_lifecycle", "unmanaged_storage"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="gcp", resource_type="bucket",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-central1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost * 0.4, 2), currency=res.get("currency", "USD"),
                reason="GCS bucket lacks automated tiering to Coldline or Archive storage classes.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 17. Azure Blob Cold Tier Rule
class AzureBlobColdTierRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-blob-no-tiering"
    @property
    def name(self) -> str:
        return "Azure Blob Storage Inactive on Hot Access Tier"
    @property
    def category(self) -> str:
        return "Storage Tiering"
    @property
    def component(self) -> str:
        return "Storage & Backup"
    @property
    def provider(self) -> str:
        return "azure"
    @property
    def severity(self) -> str:
        return "LOW"
    @property
    def description(self) -> str:
        return "Azure storage container retains historical data on Hot Tier without access tier lifecycle rules."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "azure" or res.get("resource_type") not in ["bucket", "storage"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["no_lifecycle", "hot_tier_inactive"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="azure", resource_type="bucket",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "eastus"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost * 0.5, 2), currency=res.get("currency", "USD"),
                reason="Azure storage account retains unaccessed data in Hot tier instead of Cool or Archive.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 18. AWS RDS Idle Instance
class AWSRDSIdleInstanceRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "aws-rds-idle-instance"
    @property
    def name(self) -> str:
        return "AWS RDS Idle Database Instance (0 Connections)"
    @property
    def category(self) -> str:
        return "Idle Database"
    @property
    def component(self) -> str:
        return "Databases & Caching"
    @property
    def provider(self) -> str:
        return "aws"
    @property
    def severity(self) -> str:
        return "HIGH"
    @property
    def description(self) -> str:
        return "RDS relational database instance running continuously with zero active client database connections."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "aws" or res.get("resource_type") not in ["database", "db", "rds"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["idle", "zero_connections", "stopped"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="aws", resource_type="database",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="RDS database running 24x7 with zero client connections detected over billing duration.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 19. GCP Cloud SQL Idle Instance
class GCPCloudSQLIdleInstanceRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "gcp-cloudsql-idle-instance"
    @property
    def name(self) -> str:
        return "GCP Cloud SQL Idle Database Instance"
    @property
    def category(self) -> str:
        return "Idle Database"
    @property
    def component(self) -> str:
        return "Databases & Caching"
    @property
    def provider(self) -> str:
        return "gcp"
    @property
    def severity(self) -> str:
        return "HIGH"
    @property
    def description(self) -> str:
        return "Cloud SQL database instance running without active connections or query execution."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "gcp" or res.get("resource_type") not in ["database", "db", "sql"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["idle", "zero_connections"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="gcp", resource_type="database",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-central1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="GCP Cloud SQL instance active without database client connections or transactions.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 20. Azure SQL Idle Database
class AzureSQLIdleDatabaseRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "azure-sql-idle-database"
    @property
    def name(self) -> str:
        return "Azure SQL Database with Zero Utilization"
    @property
    def category(self) -> str:
        return "Idle Database"
    @property
    def component(self) -> str:
        return "Databases & Caching"
    @property
    def provider(self) -> str:
        return "azure"
    @property
    def severity(self) -> str:
        return "HIGH"
    @property
    def description(self) -> str:
        return "Provisioned Azure SQL database with 0 DTU/vCore utilization over the billing cycle."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        prov = res.get("provider", res.get("cloud_provider"))
        if prov != "azure" or res.get("resource_type") not in ["database", "db", "sql"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["idle", "zero_connections"] and cost > 0:
            inspect, remediate = generate_resource_commands(
                provider="azure", resource_type="database",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "eastus"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="Azure SQL provisioned compute capacity running with 0 DTU consumption.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 21. Cloud Idle Redis Cache
class CloudIdleRedisCacheRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "cloud-idle-redis-cache"
    @property
    def name(self) -> str:
        return "Idle In-Memory Redis / Memcached Cluster"
    @property
    def category(self) -> str:
        return "Idle Cache"
    @property
    def component(self) -> str:
        return "Databases & Caching"
    @property
    def provider(self) -> str:
        return "multi-cloud"
    @property
    def severity(self) -> str:
        return "MEDIUM"
    @property
    def description(self) -> str:
        return "ElastiCache or Cloud Memorystore cluster running with 0 cache hits or 0 connected clients."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("resource_type") not in ["cache", "redis", "elasticache"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["idle", "zero_connections"] and cost > 0:
            prov = res.get("provider", res.get("cloud_provider", "aws"))
            inspect, remediate = generate_resource_commands(
                provider=prov, resource_type="cache",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-east-1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="In-memory cache cluster active without attached application workloads or read/write operations.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

# 22. Kubernetes Idle Node Pool
class K8sIdleNodepoolRule(BestPracticeRule):
    @property
    def rule_id(self) -> str:
        return "k8s-idle-nodepool"
    @property
    def name(self) -> str:
        return "Kubernetes Node Pool with Zero Scheduled Pods"
    @property
    def category(self) -> str:
        return "Idle Cluster"
    @property
    def component(self) -> str:
        return "Containers & Serverless"
    @property
    def provider(self) -> str:
        return "multi-cloud"
    @property
    def severity(self) -> str:
        return "HIGH"
    @property
    def description(self) -> str:
        return "GKE/EKS/AKS managed node pool provisioned with dedicated compute nodes but zero scheduled tenant workloads."
    def evaluate(self, res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        if res.get("resource_type") not in ["nodepool", "k8s_node", "cluster"]:
            return None
        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        if status in ["idle", "empty_pool"] and cost > 0:
            prov = res.get("provider", res.get("cloud_provider", "gcp"))
            inspect, remediate = generate_resource_commands(
                provider=prov, resource_type="instance",
                resource_id=res.get("resource_id", ""), resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-central1"), project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )
            return WasteEvaluationResult(
                is_waste=True, rule_id=self.rule_id, rule_name=self.name,
                category=self.category, severity=self.severity,
                monthly_savings_estimate=round(cost, 2), currency=res.get("currency", "USD"),
                reason="Dedicated Kubernetes node pool running without scheduled customer pods or jobs.",
                inspect_command=inspect, remediation_command=remediate
            )
        return None

BEST_PRACTICE_RULES: List[BestPracticeRule] = [
    GCPOrphanDiskRule(),
    GCPUnusedExternalIPRule(),
    GCPIdleComputeInstanceRule(),
    AWSUnattachedEBSVolumeRule(),
    AWSUnassociatedElasticIPRule(),
    AzureUnattachedManagedDiskRule(),
    AzureUnassociatedPublicIPRule(),
    StaleSnapshotRule(),
    AWSStoppedEC2InstanceRule(),
    AzureDeallocatedVMRule(),
    AWSIdleLoadBalancerRule(),
    GCPIdleForwardingRule(),
    AzureIdleLoadBalancerRule(),
    CloudIdleNATGatewayRule(),
    AWSS3NoLifecycleRule(),
    GCPStorageNoLifecycleRule(),
    AzureBlobColdTierRule(),
    AWSRDSIdleInstanceRule(),
    GCPCloudSQLIdleInstanceRule(),
    AzureSQLIdleDatabaseRule(),
    CloudIdleRedisCacheRule(),
    K8sIdleNodepoolRule()
]
