import datetime
import json
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

class CanonicalResource(Base):
    __tablename__ = "canonical_resources"

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(String(255), index=True, nullable=False)
    resource_name = Column(String(255), index=True, nullable=False)
    provider = Column(String(50), index=True, nullable=False)  # gcp | aws | azure
    resource_type = Column(String(50), index=True, nullable=False)  # disk | instance | ip | snapshot | sql | storage
    region_or_zone = Column(String(100), nullable=True)
    project_or_account_id = Column(String(100), index=True, nullable=False)
    cost_amount = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    usage_amount = Column(Float, default=0.0)
    usage_unit = Column(String(50), default="hours")
    status_hint = Column(String(50), default="active")  # unattached | idle | stale | active | stopped
    tags_json = Column(Text, default="{}")
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    findings = relationship("WasteFinding", back_populates="resource", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "provider": self.provider,
            "cloud_provider": self.provider,
            "resource_type": self.resource_type,
            "region_or_zone": self.region_or_zone,
            "project_id": self.project_or_account_id,
            "project_or_account_id": self.project_or_account_id,
            "cost_amount": self.cost_amount,
            "currency": self.currency,
            "usage_amount": self.usage_amount,
            "usage_unit": self.usage_unit,
            "status_hint": self.status_hint,
            "tags": json.loads(self.tags_json) if self.tags_json else {},
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class WasteFinding(Base):
    __tablename__ = "waste_findings"

    id = Column(Integer, primary_key=True, index=True)
    canonical_resource_id = Column(Integer, ForeignKey("canonical_resources.id", ondelete="CASCADE"), nullable=True)
    resource_id = Column(String(255), index=True, nullable=False)
    rule_id = Column(String(100), index=True, nullable=False)
    rule_name = Column(String(255), nullable=False)
    category = Column(String(100), index=True, nullable=False)
    severity = Column(String(20), index=True, default="HIGH")   # CRITICAL | HIGH | MEDIUM | LOW
    monthly_savings_estimate = Column(Float, default=0.0)
    currency = Column(String(10), default="USD")
    reason = Column(Text, nullable=False)
    inspect_command = Column(Text, nullable=False)
    remediation_command = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending | remediated | ignored
    detected_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    resource = relationship("CanonicalResource", back_populates="findings")
    audits = relationship("RemediationAudit", back_populates="finding", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "canonical_resource_id": self.canonical_resource_id,
            "resource_id": self.resource_id,
            "resource_name": self.resource.resource_name if self.resource else self.resource_id,
            "provider": self.resource.provider if self.resource else "gcp",
            "cloud_provider": self.resource.provider if self.resource else "gcp",
            "resource_type": self.resource.resource_type if self.resource else "unknown",
            "region_or_zone": self.resource.region_or_zone if self.resource else "unknown",
            "project_id": self.resource.project_or_account_id if self.resource else "unknown",
            "project_or_account_id": self.resource.project_or_account_id if self.resource else "unknown",
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "category": self.category,
            "severity": self.severity,
            "monthly_savings_estimate": self.monthly_savings_estimate,
            "currency": self.currency,
            "reason": self.reason,
            "inspect_command": self.inspect_command,
            "remediation_command": self.remediation_command,
            "status": self.status,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None
        }


class CustomRule(Base):
    __tablename__ = "custom_rules"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(String(50), default="*")  # gcp | aws | azure | *
    resource_type = Column(String(50), default="*")
    conditions_json = Column(Text, nullable=False, default="[]")
    logic_operator = Column(String(10), default="all")  # all (AND) | any (OR)
    severity = Column(String(20), default="HIGH")
    inspect_template = Column(Text, nullable=True)
    remediation_template = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "resource_type": self.resource_type,
            "conditions": json.loads(self.conditions_json) if self.conditions_json else [],
            "logic_operator": self.logic_operator,
            "severity": self.severity,
            "inspect_template": self.inspect_template,
            "remediation_template": self.remediation_template,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class RemediationAudit(Base):
    __tablename__ = "remediation_audits"

    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(Integer, ForeignKey("waste_findings.id", ondelete="CASCADE"), nullable=True)
    action_type = Column(String(50), nullable=False)
    executed_command = Column(Text, nullable=True)
    operator = Column(String(100), default="system_user")
    status = Column(String(50), default="completed")
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    finding = relationship("WasteFinding", back_populates="audits")

    def to_dict(self):
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "action_type": self.action_type,
            "executed_command": self.executed_command,
            "operator": self.operator,
            "status": self.status,
            "notes": self.notes,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
