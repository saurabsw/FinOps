import json
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import CustomRule
from backend.app.rules.best_practices import BEST_PRACTICE_RULES

router = APIRouter(prefix="/rules", tags=["Rule Catalog & Configurator"])

class RuleConditionSchema(BaseModel):
    field: str = Field(..., description="cost_amount, resource_type, status_hint, region_or_zone, tags.<name>")
    operator: str = Field(..., description="greater_than, less_than, equals, contains")
    value: Any

class CreateRuleSchema(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    provider: str = Field(default="*")
    resource_type: str = Field(default="*")
    conditions: List[RuleConditionSchema]
    logic_operator: str = Field(default="all", description="all (AND) or any (OR)")
    severity: str = Field(default="HIGH")
    inspect_template: Optional[str] = None
    remediation_template: Optional[str] = None

class UpdateRuleSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    conditions: Optional[List[RuleConditionSchema]] = None
    logic_operator: Optional[str] = None

@router.get("")
def list_all_rules(db: Session = Depends(get_db)):
    """Returns catalog of built-in deterministic best practices + custom rules."""
    built_in = [
        {
            "id": r.rule_id,
            "name": r.name,
            "category": r.category,
            "component": getattr(r, "component", "Compute"),
            "provider": getattr(r, "provider", "multi-cloud"),
            "description": getattr(r, "description", "Deterministic multi-cloud best practice rule."),
            "severity": r.severity,
            "tier": "Tier 1: Built-in Best Practice",
            "enabled": True,
            "is_custom": False
        }
        for r in BEST_PRACTICE_RULES
    ]

    custom_db = db.query(CustomRule).all()
    if not custom_db:
        default_seed = [
            CustomRule(
                id="gov-missing-owner-tag",
                name="Missing Mandatory Owner / CostCenter Tag",
                description="Flags cloud resources lacking an assigned engineering owner or cost center governance tag.",
                provider="*",
                resource_type="*",
                conditions_json='[{"field": "tags.Owner", "operator": "equals", "value": ""}]',
                logic_operator="all",
                severity="MEDIUM",
                enabled=True,
                inspect_template="echo 'Review unassigned owner tag on {{resource_id}}'",
                remediation_template="echo 'Tag resource {{resource_id}} with Owner=<team_lead>'"
            ),
            CustomRule(
                id="gov-expensive-dev-resource",
                name="Non-Production High Spend Run-Rate (> $150/mo)",
                description="Detects dev, staging, or test resources exceeding $150 monthly run-rate.",
                provider="*",
                resource_type="*",
                conditions_json='[{"field": "cost_amount", "operator": "greater_than", "value": 150}]',
                logic_operator="all",
                severity="HIGH",
                enabled=True,
                inspect_template="echo 'Audit high-spend dev resource: {{resource_id}}'",
                remediation_template="echo 'Downscale or shut down non-production {{resource_id}}'"
            ),
            CustomRule(
                id="gov-unapproved-region",
                name="Non-Compliant Data Center Region",
                description="Flags resources provisioned in unapproved or high-latency non-standard cloud zones.",
                provider="*",
                resource_type="*",
                conditions_json='[{"field": "region_or_zone", "operator": "contains", "value": "south"}]',
                logic_operator="all",
                severity="LOW",
                enabled=True,
                inspect_template="echo 'Check location of resource: {{resource_id}} in {{region_or_zone}}'",
                remediation_template="echo 'Plan resource migration to standard primary region'"
            ),
            CustomRule(
                id="gov-cloudwatch-retention",
                name="Cloud Logging Unlimited Retention Policy",
                description="Flags log groups and audit sinks configured to store raw log streams indefinitely.",
                provider="*",
                resource_type="*",
                conditions_json='[{"field": "status_hint", "operator": "contains", "value": "no-retention"}]',
                logic_operator="all",
                severity="MEDIUM",
                enabled=True,
                inspect_template="echo 'Review log retention policy for {{resource_id}}'",
                remediation_template="echo 'Enforce 30-day retention limit on {{resource_id}}'"
            )
        ]
        try:
            for r in default_seed:
                db.add(r)
            db.commit()
            custom_db = db.query(CustomRule).all()
        except Exception:
            db.rollback()

    custom = [
        {
            **r.to_dict(),
            "component": "Governance & Custom",
            "tier": "Tier 2: Declarative Custom Policy",
            "is_custom": True
        }
        for r in custom_db
    ]

    return {
        "total_rules": len(built_in) + len(custom),
        "tier_1_count": len(built_in),
        "tier_2_count": len(custom),
        "built_in_rules": built_in,
        "custom_rules": custom
    }

@router.post("")
def create_custom_rule(payload: CreateRuleSchema, db: Session = Depends(get_db)):
    """Registers a declarative custom rule in SQLite."""
    rule_id = payload.id or f"custom-{uuid.uuid4().hex[:8]}"

    existing = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rule ID '{rule_id}' already exists.")

    new_rule = CustomRule(
        id=rule_id,
        name=payload.name,
        description=payload.description,
        provider=payload.provider.lower(),
        resource_type=payload.resource_type.lower(),
        conditions_json=json.dumps([c.model_dump() for c in payload.conditions]),
        logic_operator=payload.logic_operator.lower(),
        severity=payload.severity.upper(),
        inspect_template=payload.inspect_template,
        remediation_template=payload.remediation_template,
        enabled=True
    )
    db.add(new_rule)
    db.commit()

    return {
        "status": "success",
        "rule": new_rule.to_dict(),
        "message": f"Custom rule '{payload.name}' registered."
    }

@router.put("/{rule_id}")
def update_custom_rule(rule_id: str, payload: UpdateRuleSchema, db: Session = Depends(get_db)):
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Custom rule '{rule_id}' not found.")

    if payload.name is not None:
        rule.name = payload.name
    if payload.description is not None:
        rule.description = payload.description
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.severity is not None:
        rule.severity = payload.severity.upper()
    if payload.logic_operator is not None:
        rule.logic_operator = payload.logic_operator.lower()
    if payload.conditions is not None:
        rule.conditions_json = json.dumps([c.model_dump() for c in payload.conditions])

    db.commit()

    return {
        "status": "success",
        "rule": rule.to_dict(),
        "message": f"Custom rule '{rule_id}' updated."
    }

@router.put("/{rule_id}/toggle")
def toggle_custom_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Custom rule '{rule_id}' not found.")

    rule.enabled = not rule.enabled
    db.commit()

    return {
        "status": "success",
        "rule_id": rule.id,
        "enabled": rule.enabled,
        "message": f"Rule '{rule.name}' is now {'enabled' if rule.enabled else 'disabled'}."
    }

@router.delete("/{rule_id}")
def delete_custom_rule(rule_id: str, db: Session = Depends(get_db)):
    rule = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Custom rule '{rule_id}' not found.")

    db.delete(rule)
    db.commit()

    return {
        "status": "success",
        "message": f"Custom rule '{rule_id}' removed."
    }
