import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import CanonicalResource, WasteFinding, CustomRule, RemediationAudit
from app.engine.built_in_rules import BUILT_IN_RULES
from app.engine.rule_configurator import CustomRuleEvaluator
from app.engine.remediation_generator import build_safety_gated_bash_script

router = APIRouter(prefix="/optimizer", tags=["Optimizer & Remediation Engine"])

@router.post("/scan")
def run_optimizer_scan(db: Session = Depends(get_db)):
    """
    Executes the Two-Tier FinOps Evaluation Engine:
    1. Built-in Deterministic Best Practices Engine (Orphan Disks, Idle IPs, Stopped VMs, Stale Snapshots)
    2. Declarative Custom Rules Engine
    Stores waste findings in SQLite database.
    """
    resources = db.query(CanonicalResource).all()
    if not resources:
        return {
            "status": "warning",
            "message": "No canonical resources found. Please upload billing data first via /api/v1/billing/upload.",
            "findings_count": 0,
            "potential_savings": 0.0
        }

    # Fetch active custom rules
    custom_rules = db.query(CustomRule).filter(CustomRule.enabled == True).all()

    # Clear previous pending findings to re-evaluate freshly
    db.query(WasteFinding).filter(WasteFinding.status == "pending").delete()

    created_findings = []
    total_savings = 0.0

    for res in resources:
        res_dict = res.to_dict()

        # 1. Evaluate Built-in Rules
        for rule in BUILT_IN_RULES:
            result = rule.evaluate(res_dict)
            if result and result.is_waste:
                finding = WasteFinding(
                    canonical_resource_id=res.id,
                    resource_id=res.resource_id,
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    category=result.category,
                    severity=result.severity,
                    monthly_savings_estimate=result.monthly_savings_estimate,
                    currency=result.currency,
                    reason=result.reason,
                    inspect_command=result.inspect_command,
                    remediation_command=result.remediation_command,
                    status="pending"
                )
                db.add(finding)
                created_findings.append(finding)
                total_savings += result.monthly_savings_estimate
                break  # avoid duplicate findings for the same resource from base rules

        # 2. Evaluate Custom Rules
        for cr in custom_rules:
            cr_dict = cr.to_dict()
            result = CustomRuleEvaluator.evaluate(cr_dict, res_dict)
            if result and result.is_waste:
                # Check if already caught by base rule
                if any(f.resource_id == res.resource_id for f in created_findings):
                    continue
                finding = WasteFinding(
                    canonical_resource_id=res.id,
                    resource_id=res.resource_id,
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    category=result.category,
                    severity=result.severity,
                    monthly_savings_estimate=result.monthly_savings_estimate,
                    currency=result.currency,
                    reason=result.reason,
                    inspect_command=result.inspect_command,
                    remediation_command=result.remediation_command,
                    status="pending"
                )
                db.add(finding)
                created_findings.append(finding)
                total_savings += result.monthly_savings_estimate

    db.commit()

    return {
        "status": "success",
        "scanned_resources": len(resources),
        "findings_detected": len(created_findings),
        "potential_monthly_savings": round(total_savings, 2),
        "message": f"Scan complete. Evaluated {len(resources)} resources and identified {len(created_findings)} waste findings."
    }

@router.get("/waste-items")
def get_waste_items(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query("pending"),
    db: Session = Depends(get_db)
):
    """
    Returns detected waste findings, cost leakage, and 2-step CLI snippets (Inspect & Remediate).
    """
    query = db.query(WasteFinding)
    if status and status != "all":
        query = query.filter(WasteFinding.status == status)
    if severity:
        query = query.filter(WasteFinding.severity == severity.upper())
    if category:
        query = query.filter(WasteFinding.category == category)

    findings = query.order_by(WasteFinding.monthly_savings_estimate.desc()).all()
    results = [f.to_dict() for f in findings]

    if provider:
        results = [r for r in results if r.get("provider") == provider.lower()]

    total_leakage = sum(r["monthly_savings_estimate"] for r in results)

    return {
        "total_findings": len(results),
        "total_cost_leakage": round(total_leakage, 2),
        "findings": results
    }

@router.get("/summary")
def get_finops_summary(db: Session = Depends(get_db)):
    """
    Aggregates enterprise FinOps KPIs:
    - Total Gross Cloud Spend
    - Identified Cost Leakage
    - Potential Monthly Savings & Percentage
    - Breakdown by Category, Provider, Severity
    """
    resources = db.query(CanonicalResource).all()
    findings = db.query(WasteFinding).filter(WasteFinding.status == "pending").all()

    total_gross_spend = sum(r.cost_amount for r in resources)
    total_leakage = sum(f.monthly_savings_estimate for f in findings)
    savings_pct = (total_leakage / total_gross_spend * 100) if total_gross_spend > 0 else 0.0

    # Categorical breakdown
    by_category = {}
    for f in findings:
        by_category[f.category] = round(by_category.get(f.category, 0.0) + f.monthly_savings_estimate, 2)

    # Provider breakdown
    by_provider = {}
    for r in resources:
        by_provider[r.provider] = round(by_provider.get(r.provider, 0.0) + r.cost_amount, 2)

    # Severity breakdown
    by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.severity.upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "total_resources": len(resources),
        "total_gross_spend": round(total_gross_spend, 2),
        "total_waste_findings": len(findings),
        "potential_monthly_savings": round(total_leakage, 2),
        "savings_percentage": round(savings_pct, 1),
        "breakdown_by_category": by_category,
        "breakdown_by_provider": by_provider,
        "breakdown_by_severity": by_severity
    }

@router.get("/generate-script")
def generate_remediation_script(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Generates and downloads the enterprise-grade remediate_waste.sh bash script
    strictly enforcing the 2-step 'Inspect-then-Confirm' pattern.
    """
    query = db.query(WasteFinding).filter(WasteFinding.status == "pending")
    if severity:
        query = query.filter(WasteFinding.severity == severity.upper())
    if category:
        query = query.filter(WasteFinding.category == category)

    findings = [f.to_dict() for f in query.order_by(WasteFinding.monthly_savings_estimate.desc()).all()]

    if provider:
        findings = [f for f in findings if f.get("provider") == provider.lower()]

    script_content = build_safety_gated_bash_script(findings)

    return Response(
        content=script_content,
        media_type="application/x-sh",
        headers={
            "Content-Disposition": 'attachment; filename="remediate_waste.sh"',
            "Content-Type": "text/x-shellscript; charset=utf-8"
        }
    )

@router.post("/remediate-action")
def update_remediation_status(
    finding_id: int,
    action: str = Query(..., pattern="^(remediated|ignored|pending)$"),
    notes: Optional[str] = None,
    operator: str = "finops_admin",
    db: Session = Depends(get_db)
):
    finding = db.query(WasteFinding).filter(WasteFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    finding.status = action

    # Record Audit Log
    audit = RemediationAudit(
        finding_id=finding.id,
        action_type=action,
        executed_command=finding.remediation_command if action == "remediated" else None,
        operator=operator,
        status="completed",
        notes=notes or f"Resource status updated to {action}"
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "finding_id": finding.id,
        "new_status": finding.status,
        "message": f"Finding {finding.id} marked as {action}."
    }
