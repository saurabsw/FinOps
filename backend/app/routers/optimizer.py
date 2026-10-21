import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import CanonicalResource, WasteFinding, CustomRule, RemediationAudit
from backend.app.rules.best_practices import BEST_PRACTICE_RULES
from backend.app.rules.custom_evaluator import CustomRuleEvaluator
from backend.app.remediation import generate_bash_remediation_script

router = APIRouter(prefix="/optimizer", tags=["Optimizer & Safe Remediation Engine"])

@router.post("/scan")
def run_optimizer_scan(db: Session = Depends(get_db)):
    """
    Evaluates ingested CanonicalBillingRecord resources against:
    1) Built-in Deterministic Best Practices Engine
    2) Declarative Custom Rule Configurator
    Records WasteFindings in SQLite and returns scan summary.
    """
    resources = db.query(CanonicalResource).all()
    if not resources:
        return {
            "status": "warning",
            "message": "No canonical resources found. Upload billing files first.",
            "scanned_resources": 0,
            "findings_detected": 0,
            "potential_monthly_savings": 0.0
        }

    # Fetch enabled custom rules
    active_custom_rules = db.query(CustomRule).filter(CustomRule.enabled == True).all()

    # Clear pending findings for fresh scan
    db.query(WasteFinding).filter(WasteFinding.status == "pending").delete()

    created_findings = []
    total_savings = 0.0

    for res in resources:
        res_dict = res.to_dict()
        matched = False

        # 1. Evaluate Built-in Rules
        for rule in BEST_PRACTICE_RULES:
            res_eval = rule.evaluate(res_dict)
            if res_eval and res_eval.is_waste:
                finding = WasteFinding(
                    canonical_resource_id=res.id,
                    resource_id=res.resource_id,
                    rule_id=res_eval.rule_id,
                    rule_name=res_eval.rule_name,
                    category=res_eval.category,
                    severity=res_eval.severity,
                    monthly_savings_estimate=res_eval.monthly_savings_estimate,
                    currency=res_eval.currency,
                    reason=res_eval.reason,
                    inspect_command=res_eval.inspect_command,
                    remediation_command=res_eval.remediation_command,
                    status="pending"
                )
                db.add(finding)
                created_findings.append(finding)
                total_savings += res_eval.monthly_savings_estimate
                matched = True
                break

        if matched:
            continue

        # 2. Evaluate Declarative Custom Rules
        for cr in active_custom_rules:
            cr_dict = cr.to_dict()
            res_eval = CustomRuleEvaluator.evaluate(cr_dict, res_dict)
            if res_eval and res_eval.is_waste:
                finding = WasteFinding(
                    canonical_resource_id=res.id,
                    resource_id=res.resource_id,
                    rule_id=res_eval.rule_id,
                    rule_name=res_eval.rule_name,
                    category=res_eval.category,
                    severity=res_eval.severity,
                    monthly_savings_estimate=res_eval.monthly_savings_estimate,
                    currency=res_eval.currency,
                    reason=res_eval.reason,
                    inspect_command=res_eval.inspect_command,
                    remediation_command=res_eval.remediation_command,
                    status="pending"
                )
                db.add(finding)
                created_findings.append(finding)
                total_savings += res_eval.monthly_savings_estimate
                break

    db.commit()

    return {
        "status": "success",
        "scanned_resources": len(resources),
        "findings_detected": len(created_findings),
        "potential_monthly_savings": round(total_savings, 2),
        "message": f"Scan completed: {len(created_findings)} waste items identified."
    }

@router.get("/waste-items")
def get_waste_items(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query("pending"),
    db: Session = Depends(get_db)
):
    """Returns detected waste findings with 2-step inspect and remediation commands."""
    query = db.query(WasteFinding)
    if status and status != "all":
        query = query.filter(WasteFinding.status == status)
    if severity:
        query = query.filter(WasteFinding.severity == severity.upper())
    if category:
        query = query.filter(WasteFinding.category == category)

    findings = query.order_by(WasteFinding.monthly_savings_estimate.desc()).all()
    results = [f.to_dict() for f in findings]

    if provider and provider != "all":
        results = [r for r in results if r.get("provider") == provider.lower() or r.get("cloud_provider") == provider.lower()]

    total_leakage = sum(r["monthly_savings_estimate"] for r in results)

    return {
        "total_findings": len(results),
        "total_cost_leakage": round(total_leakage, 2),
        "findings": results
    }

@router.get("/summary")
def get_finops_summary(db: Session = Depends(get_db)):
    """Aggregated FinOps KPIs for executive reporting."""
    resources = db.query(CanonicalResource).all()
    findings = db.query(WasteFinding).filter(WasteFinding.status == "pending").all()

    total_spend = sum(r.cost_amount for r in resources)
    total_waste = sum(f.monthly_savings_estimate for f in findings)
    savings_pct = (total_waste / total_spend * 100) if total_spend > 0 else 0.0

    by_type = {}
    by_project = {}
    for f in findings:
        r_type = f.resource.resource_type if f.resource else "other"
        by_type[r_type] = round(by_type.get(r_type, 0.0) + f.monthly_savings_estimate, 2)

        proj = f.resource.project_or_account_id if f.resource else "default"
        by_project[proj] = round(by_project.get(proj, 0.0) + f.monthly_savings_estimate, 2)

    by_category = {}
    by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        by_category[f.category] = round(by_category.get(f.category, 0.0) + f.monthly_savings_estimate, 2)
        sev = f.severity.upper()
        by_severity[sev] = by_severity.get(sev, 0) + 1

    by_provider = {}
    for r in resources:
        by_provider[r.provider] = round(by_provider.get(r.provider, 0.0) + r.cost_amount, 2)

    return {
        "total_spend": round(total_spend, 2),
        "total_gross_spend": round(total_spend, 2),
        "total_detected_monthly_waste": round(total_waste, 2),
        "potential_monthly_savings": round(total_waste, 2),
        "identified_orphan_resources_count": len(findings),
        "total_waste_findings": len(findings),
        "total_resources": len(resources),
        "potential_savings_percentage": round(savings_pct, 1),
        "savings_percentage": round(savings_pct, 1),
        "waste_by_resource_type": by_type,
        "waste_by_project": by_project,
        "spend_by_provider": by_provider,
        "breakdown_by_category": by_category,
        "breakdown_by_provider": by_provider,
        "breakdown_by_severity": by_severity
    }

@router.get("/generate-script")
def stream_remediation_script(
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Generates and streams a downloadable remediate_waste.sh bash script."""
    query = db.query(WasteFinding).filter(WasteFinding.status == "pending")
    if severity:
        query = query.filter(WasteFinding.severity == severity.upper())
    if category:
        query = query.filter(WasteFinding.category == category)

    raw_items = [f.to_dict() for f in query.order_by(WasteFinding.monthly_savings_estimate.desc()).all()]

    if provider and provider != "all":
        raw_items = [f for f in raw_items if f.get("provider") == provider.lower() or f.get("cloud_provider") == provider.lower()]

    script_text = generate_bash_remediation_script(raw_items)

    return Response(
        content=script_text,
        media_type="application/x-sh",
        headers={
            "Content-Disposition": 'attachment; filename="remediate_waste.sh"',
            "Content-Type": "text/x-shellscript; charset=utf-8"
        }
    )

@router.post("/remediate-action")
def record_remediation_action(
    finding_id: int,
    action: str = Query(..., pattern="^(remediated|ignored|pending)$"),
    notes: Optional[str] = None,
    operator: str = "finops_engineer",
    db: Session = Depends(get_db)
):
    finding = db.query(WasteFinding).filter(WasteFinding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    finding.status = action

    audit = RemediationAudit(
        finding_id=finding.id,
        action_type=action,
        executed_command=finding.remediation_command if action == "remediated" else None,
        operator=operator,
        status="completed",
        notes=notes or f"Action {action} confirmed"
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "finding_id": finding.id,
        "new_status": finding.status
    }
