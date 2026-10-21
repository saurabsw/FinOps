import re
from typing import Dict, Any, List, Optional
from app.engine.rules_base import RuleEvaluationResult
from app.engine.remediation_generator import sanitize_remediation_command, generate_commands_for_resource

class CustomRuleEvaluator:
    """Evaluates declarative custom rules against canonical resources."""

    @staticmethod
    def evaluate(rule: Dict[str, Any], res: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        """
        rule structure:
        {
            "id": "custom-rule-1",
            "name": "High Cost Idle Disk",
            "provider": "gcp" | "*"
            "resource_type": "disk" | "*"
            "conditions": [
                {"field": "cost_amount", "operator": ">", "value": 50},
                {"field": "status_hint", "operator": "==", "value": "idle"},
                {"field": "tags.environment", "operator": "==", "value": "dev"}
            ],
            "severity": "CRITICAL",
            "inspect_template": "...",
            "remediation_template": "..."
        }
        """
        # 1. Filter by provider
        target_provider = rule.get("provider", "*")
        if target_provider != "*" and target_provider.lower() != res.get("provider", "").lower():
            return None

        # 2. Filter by resource type
        target_res_type = rule.get("resource_type", "*")
        if target_res_type != "*" and target_res_type.lower() != res.get("resource_type", "").lower():
            return None

        # 3. Evaluate each condition
        conditions = rule.get("conditions", [])
        for cond in conditions:
            if not CustomRuleEvaluator._evaluate_condition(cond, res):
                return None

        # All conditions passed -> waste identified!
        cost = float(res.get("cost_amount", 0.0))
        severity = rule.get("severity", "HIGH")
        category = rule.get("category", "Custom Policy")

        # Command generation or interpolation
        inspect_template = rule.get("inspect_template")
        remediation_template = rule.get("remediation_template")

        if inspect_template and remediation_template:
            context = {
                "resource_id": res.get("resource_id", ""),
                "resource_name": res.get("resource_name", ""),
                "project_id": res.get("project_or_account_id", ""),
                "project_or_account_id": res.get("project_or_account_id", ""),
                "region_or_zone": res.get("region_or_zone", ""),
                "provider": res.get("provider", "gcp"),
                "cost": cost
            }
            inspect_cmd = CustomRuleEvaluator._interpolate(inspect_template, context)
            raw_remediate = CustomRuleEvaluator._interpolate(remediation_template, context)
            remediate_cmd = sanitize_remediation_command(raw_remediate)
        else:
            inspect_cmd, remediate_cmd = generate_commands_for_resource(
                provider=res.get("provider", "gcp"),
                resource_type=res.get("resource_type", "other"),
                resource_id=res.get("resource_id", ""),
                resource_name=res.get("resource_name", ""),
                region_or_zone=res.get("region_or_zone", ""),
                project_or_account_id=res.get("project_or_account_id", ""),
                metadata=res.get("metadata", {})
            )

        reason = rule.get("description") or f"Resource violated custom policy: {rule.get('name')}"

        return RuleEvaluationResult(
            is_waste=True,
            rule_id=rule.get("id"),
            rule_name=rule.get("name"),
            category=category,
            severity=severity,
            monthly_savings_estimate=round(cost, 2),
            currency=res.get("currency", "USD"),
            reason=reason,
            inspect_command=inspect_cmd,
            remediation_command=remediate_cmd
        )

    @staticmethod
    def _evaluate_condition(cond: Dict[str, Any], res: Dict[str, Any]) -> bool:
        field = cond.get("field", "")
        op = cond.get("operator", "==")
        target_val = cond.get("value")

        actual_val = CustomRuleEvaluator._resolve_field(field, res)
        if actual_val is None:
            return False

        try:
            if op == ">":
                return float(actual_val) > float(target_val)
            elif op == ">=":
                return float(actual_val) >= float(target_val)
            elif op == "<":
                return float(actual_val) < float(target_val)
            elif op == "<=":
                return float(actual_val) <= float(target_val)
            elif op in ["==", "eq"]:
                return str(actual_val).lower() == str(target_val).lower()
            elif op in ["!=", "neq"]:
                return str(actual_val).lower() != str(target_val).lower()
            elif op in ["contains", "in"]:
                if isinstance(target_val, list):
                    return actual_val in target_val or str(actual_val).lower() in [str(x).lower() for x in target_val]
                return str(target_val).lower() in str(actual_val).lower()
            elif op == "regex":
                return bool(re.search(str(target_val), str(actual_val), re.IGNORECASE))
        except (ValueError, TypeError):
            return False

        return False

    @staticmethod
    def _resolve_field(field_path: str, res: Dict[str, Any]) -> Any:
        parts = field_path.split(".")
        val = res
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return None
        return val

    @staticmethod
    def _interpolate(template: str, context: Dict[str, Any]) -> str:
        res = template
        for k, v in context.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res
