import json
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import CustomRule
from app.engine.built_in_rules import BUILT_IN_RULES

router = APIRouter(prefix="/rules", tags=["Rule Catalog & Configurator"])

class ConditionModel(BaseModel):
    field: str
    operator: str = Field(..., description=">, >=, <, <=, ==, !=, in, contains, regex")
    value: Any

class CreateCustomRuleSchema(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    provider: str = Field(default="*")
    resource_type: str = Field(default="*")
    conditions: List[ConditionModel]
    severity: str = Field(default="HIGH")
    inspect_template: Optional[str] = None
    remediation_template: Optional[str] = None

@router.get("")
def list_rules(db: Session = Depends(get_db)):
    """Lists both Tier 1 Built-in Best Practice Rules and Tier 2 Custom Rules."""
    built_in = [
        {
            "id": r.rule_id,
            "name": r.name,
            "category": r.category,
            "severity": r.severity,
            "tier": "Tier 1: Built-in Best Practice",
            "provider": "Multi-Cloud (GCP / AWS / Azure)",
            "enabled": True,
            "is_custom": False
        }
        for r in BUILT_IN_RULES
    ]

    custom_rules = db.query(CustomRule).all()
    custom = [
        {
            **r.to_dict(),
            "tier": "Tier 2: User Configured Policy",
            "is_custom": True
        }
        for r in custom_rules
    ]

    return {
        "total_rules": len(built_in) + len(custom),
        "built_in_rules": built_in,
        "custom_rules": custom
    }

@router.post("")
def create_custom_rule(payload: CreateCustomRuleSchema, db: Session = Depends(get_db)):
    """Creates a new declarative custom rule in SQLite."""
    rule_id = payload.id or f"custom-{uuid.uuid4().hex[:8]}"

    existing = db.query(CustomRule).filter(CustomRule.id == rule_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rule with id '{rule_id}' already exists.")

    new_rule = CustomRule(
        id=rule_id,
        name=payload.name,
        description=payload.description,
        provider=payload.provider.lower(),
        resource_type=payload.resource_type.lower(),
        conditions_json=json.dumps([c.model_dump() for c in payload.conditions]),
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
        "message": f"Custom rule '{payload.name}' successfully registered."
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
        "message": f"Custom rule '{rule_id}' deleted."
    }
