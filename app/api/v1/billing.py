import json
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import CanonicalResource, WasteFinding
from app.ingestion.detector import parse_billing_content

router = APIRouter(prefix="/billing", tags=["Billing Ingestion"])

@router.post("/upload")
async def upload_billing_data(
    file: Optional[UploadFile] = File(None),
    provider: Optional[str] = Form(None),
    raw_payload: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Ingests raw cloud billing exports (GCP Detailed Usage CSV/JSON, AWS CUR, Azure Cost Export)
    and maps them into standardized CanonicalResource records in SQLite.
    """
    content = ""
    if file:
        file_bytes = await file.read()
        content = file_bytes.decode("utf-8", errors="replace")
    elif raw_payload:
        content = raw_payload
    else:
        raise HTTPException(status_code=400, detail="Either a file upload or raw_payload must be provided.")

    if not content.strip():
        raise HTTPException(status_code=400, detail="Uploaded billing file or payload is empty.")

    try:
        detected_provider, records = parse_billing_content(content, provider=provider)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse billing file: {str(e)}")

    if not records:
        raise HTTPException(status_code=422, detail="No valid billing records could be extracted from payload.")

    # Save to SQLite DB
    created_count = 0
    total_cost = 0.0

    for rec in records:
        db_res = CanonicalResource(
            resource_id=rec["resource_id"],
            resource_name=rec["resource_name"],
            provider=rec["provider"],
            resource_type=rec["resource_type"],
            region_or_zone=rec["region_or_zone"],
            project_or_account_id=rec["project_or_account_id"],
            cost_amount=rec["cost_amount"],
            currency=rec["currency"],
            usage_amount=rec["usage_amount"],
            usage_unit=rec["usage_unit"],
            status_hint=rec["status_hint"],
            tags_json=json.dumps(rec.get("tags", {})),
            metadata_json=json.dumps(rec.get("metadata", {}))
        )
        db.add(db_res)
        total_cost += rec["cost_amount"]
        created_count += 1

    db.commit()

    return {
        "status": "success",
        "provider_detected": detected_provider,
        "records_ingested": created_count,
        "total_spend_ingested": round(total_cost, 2),
        "message": f"Successfully ingested {created_count} canonical resources for provider '{detected_provider}'."
    }

@router.get("/records")
def list_canonical_records(
    provider: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status_hint: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(CanonicalResource)
    if provider:
        query = query.filter(CanonicalResource.provider == provider.lower())
    if resource_type:
        query = query.filter(CanonicalResource.resource_type == resource_type.lower())
    if status_hint:
        query = query.filter(CanonicalResource.status_hint == status_hint.lower())

    total = query.count()
    items = query.order_by(CanonicalResource.cost_amount.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [item.to_dict() for item in items]
    }

@router.delete("/clear")
def clear_all_records(db: Session = Depends(get_db)):
    """Deletes all canonical resources and waste findings to allow fresh benchmarking."""
    db.query(WasteFinding).delete()
    db.query(CanonicalResource).delete()
    db.commit()
    return {"status": "success", "message": "All billing resources and findings have been purged."}
