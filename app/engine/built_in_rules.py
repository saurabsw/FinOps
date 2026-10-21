from typing import Optional, Dict, Any, List
from app.engine.rules_base import BaseRule, RuleEvaluationResult
from app.engine.remediation_generator import generate_commands_for_resource

class OrphanDiskRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "orphan-disk-detection"

    @property
    def name(self) -> str:
        return "Unattached / Orphan Persistent Disk"

    @property
    def category(self) -> str:
        return "Orphan Disk"

    @property
    def severity(self) -> str:
        return "HIGH"

    def evaluate(self, res: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        if res.get("resource_type") != "disk":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        attached_vm = metadata.get("attached_vm")

        # Zero false positives on active attached resources
        if status == "active" and attached_vm not in [None, "", "none", "null"]:
            return None

        is_orphan = (
            status in ["unattached", "orphan", "detached", "idle"] or
            (attached_vm in [None, "", "none", "null"] and float(res.get("usage_amount", 0.0)) == 0.0 and cost > 0)
        )

        if not is_orphan or cost <= 0:
            return None

        inspect_cmd, remediate_cmd = generate_commands_for_resource(
            provider=res.get("provider", "gcp"),
            resource_type="disk",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", ""),
            project_or_account_id=res.get("project_or_account_id", ""),
            metadata=metadata
        )

        idle_days = metadata.get("idle_days", 0)
        reason = f"Persistent disk is unattached with 0 compute attachment hours, incurring recurring charges."
        if idle_days:
            reason += f" Detached for {idle_days} days."

        return RuleEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )


class IdleStaticIPRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "idle-static-ip-detection"

    @property
    def name(self) -> str:
        return "Idle / Unassociated External Static IP"

    @property
    def category(self) -> str:
        return "Idle IP"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        if res.get("resource_type") != "ip":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}

        # If active and assigned, zero false positive
        if status == "active":
            return None

        is_idle = status in ["unattached", "unassigned", "idle"]

        if not is_idle or cost <= 0:
            return None

        inspect_cmd, remediate_cmd = generate_commands_for_resource(
            provider=res.get("provider", "gcp"),
            resource_type="ip",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", ""),
            project_or_account_id=res.get("project_or_account_id", ""),
            metadata=metadata
        )

        ip_addr = metadata.get("ip_address") or res.get("resource_name")
        reason = f"External IP ({ip_addr}) is reserved but unassociated, incurring idle reservation penalty fees."

        return RuleEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )


class IdleStoppedVMRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "stopped-vm-detection"

    @property
    def name(self) -> str:
        return "Stopped / Inactive Compute VM"

    @property
    def category(self) -> str:
        return "Idle VM"

    @property
    def severity(self) -> str:
        return "CRITICAL"

    def evaluate(self, res: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        if res.get("resource_type") != "instance":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        vm_state = str(metadata.get("vm_state", "")).upper()

        if status == "active" and vm_state not in ["STOPPED", "TERMINATED", "DEALLOCATED"]:
            return None

        is_stopped = status in ["stopped", "terminated", "idle"] or vm_state in ["STOPPED", "TERMINATED", "DEALLOCATED"]

        if not is_stopped or cost <= 0:
            return None

        inspect_cmd, remediate_cmd = generate_commands_for_resource(
            provider=res.get("provider", "gcp"),
            resource_type="instance",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", ""),
            project_or_account_id=res.get("project_or_account_id", ""),
            metadata=metadata
        )

        idle_days = metadata.get("idle_days", 0)
        reason = f"Instance is in stopped state but continues accumulating disk and network lease costs."
        if idle_days:
            reason += f" Inactive for {idle_days} days."

        return RuleEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )


class StaleSnapshotRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "stale-snapshot-detection"

    @property
    def name(self) -> str:
        return "Stale / Aged Storage Snapshot"

    @property
    def category(self) -> str:
        return "Stale Snapshot"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def evaluate(self, res: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        if res.get("resource_type") != "snapshot":
            return None

        status = str(res.get("status_hint", "")).lower()
        cost = float(res.get("cost_amount", 0.0))
        metadata = res.get("metadata", {}) or {}
        age_days = int(metadata.get("snapshot_age_days", 0))

        if status == "active" and age_days < 30:
            return None

        is_stale = status in ["stale", "aged"] or age_days >= 30

        if not is_stale or cost <= 0:
            return None

        inspect_cmd, remediate_cmd = generate_commands_for_resource(
            provider=res.get("provider", "gcp"),
            resource_type="snapshot",
            resource_id=res.get("resource_id", ""),
            resource_name=res.get("resource_name", ""),
            region_or_zone=res.get("region_or_zone", ""),
            project_or_account_id=res.get("project_or_account_id", ""),
            metadata=metadata
        )

        reason = f"Storage snapshot is {age_days or '>30'} days old, exceeding standard backup retention policy."

        return RuleEvaluationResult(
            is_waste=True,
            rule_id=self.rule_id,
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )

BUILT_IN_RULES: List[BaseRule] = [
    OrphanDiskRule(),
    IdleStaticIPRule(),
    IdleStoppedVMRule(),
    StaleSnapshotRule()
]
