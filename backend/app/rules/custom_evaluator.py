import re
from typing import Dict, Any, List, Optional
from backend.app.rules.best_practices import WasteEvaluationResult
from backend.app.remediation import sanitize_remediation_command, generate_resource_commands

class CustomRuleEvaluator:
    """Evaluates user-defined declarative rules against CanonicalBillingRecord items."""

    @staticmethod
    def evaluate(rule_dict: Dict[str, Any], res: Dict[str, Any]) -> Optional[WasteEvaluationResult]:
        """
        Evaluates rule_dict:
        {
            "id": "rule-id",
            "name": "Custom Waste Rule",
            "provider": "gcp" | "*" | "aws" | "azure",
            "resource_type": "disk" | "*" | ...,
            "logic_operator": "all" | "any", # all (AND) or any (OR)
            "conditions": [
                {"field": "cost_amount", "operator": "greater_than", "value": 50.0},
                {"field": "status_hint", "operator": "equals", "value": "unattached"}
            ],
            "severity": "HIGH",
            "inspect_template": "...",
            "remediation_template": "..."
        }
        """
        # 1. Filter by provider
        target_provider = (rule_dict.get("provider") or "*").lower()
        res_provider = (res.get("cloud_provider") or res.get("provider") or "").lower()
        if target_provider != "*" and target_provider != res_provider:
            return None

        # 2. Filter by resource type
        target_res_type = (rule_dict.get("resource_type") or "*").lower()
        res_type = (res.get("resource_type") or "").lower()
        if target_res_type != "*" and target_res_type != res_type:
            return None

        # 3. Evaluate conditions
        conditions = rule_dict.get("conditions") or []
        if not conditions:
            return None

        logic_op = (rule_dict.get("logic_operator") or "all").lower()

        eval_results = [CustomRuleEvaluator._eval_single_condition(cond, res) for cond in conditions]

        is_match = all(eval_results) if logic_op == "all" else any(eval_results)
        if not is_match:
            return None

        cost = float(res.get("cost_amount") or 0.0)
        currency = res.get("currency") or "USD"
        severity = rule_dict.get("severity") or "HIGH"
        rule_name = rule_dict.get("name") or "Custom FinOps Policy"
        rule_id = rule_dict.get("id") or "custom-rule"

        # Templates
        inspect_template = rule_dict.get("inspect_template")
        remediate_template = rule_dict.get("remediation_template")

        if inspect_template and remediate_template:
            ctx = {
                "resource_id": res.get("resource_id", ""),
                "resource_name": res.get("resource_name", ""),
                "project_id": res.get("project_id", res.get("project_or_account_id", "")),
                "region_or_zone": res.get("region_or_zone", ""),
                "cloud_provider": res_provider,
                "cost_amount": cost
            }
            inspect_cmd = CustomRuleEvaluator._interpolate(inspect_template, ctx)
            remediate_cmd = sanitize_remediation_command(CustomRuleEvaluator._interpolate(remediate_template, ctx))
        else:
            inspect_cmd, remediate_cmd = generate_resource_commands(
                provider=res_provider,
                resource_type=res_type or "other",
                resource_id=res.get("resource_id", ""),
                resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", "us-central1-a"),
                project_or_account_id=res.get("project_id", res.get("project_or_account_id", "")),
                metadata=res.get("metadata", {})
            )

        reason = rule_dict.get("description") or f"Resource met declarative policy criteria: {rule_name}"

        return WasteEvaluationResult(
            is_waste=True,
            rule_id=rule_id,
            rule_name=rule_name,
            category=rule_dict.get("category", "Custom Policy"),
            severity=severity,
            monthly_savings_estimate=round(cost, 2),
            currency=currency,
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )

    @staticmethod
    def _eval_single_condition(cond: Dict[str, Any], res: Dict[str, Any]) -> bool:
        field = cond.get("field", "")
        op = str(cond.get("operator", "equals")).lower()
        target_val = cond.get("value")

        actual_val = CustomRuleEvaluator._resolve_field(field, res)
        if actual_val is None:
            return False

        try:
            if op in ["greater_than", ">"]:
                return float(actual_val) > float(target_val)
            elif op in ["less_than", "<"]:
                return float(actual_val) < float(target_val)
            elif op in ["equals", "==", "eq"]:
                return str(actual_val).lower() == str(target_val).lower()
            elif op in ["not_equals", "!=", "neq"]:
                return str(actual_val).lower() != str(target_val).lower()
            elif op in ["contains", "in"]:
                if isinstance(target_val, list):
                    return str(actual_val).lower() in [str(x).lower() for x in target_val]
                return str(target_val).lower() in str(actual_val).lower()
        except (ValueError, TypeError):
            return False

        return False

    @staticmethod
    def _resolve_field(field_path: str, res: Dict[str, Any]) -> Any:
        # Handle field mappings
        if field_path == "project_id" and "project_id" not in res and "project_or_account_id" in res:
            return res.get("project_or_account_id")
        if field_path == "cloud_provider" and "cloud_provider" not in res and "provider" in res:
            return res.get("provider")

        parts = field_path.split(".")
        curr = res
        for p in parts:
            if isinstance(curr, dict):
                curr = curr.get(p)
            else:
                return None
        return curr

    @staticmethod
    def _interpolate(template: str, ctx: Dict[str, Any]) -> str:
        res = template
        for k, v in ctx.items():
            res = res.replace(f"<{k}>", str(v)).replace(f"{{{k}}}", str(v))
        return res
