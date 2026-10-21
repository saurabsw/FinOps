import json
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.models import CanonicalResource, WasteFinding
from backend.app.adapters.base_adapter import parse_billing_file, validate_billing_content
from backend.app.core.config import settings

router = APIRouter(prefix="/billing", tags=["Billing Ingestion"])

@router.post("/upload")
async def upload_billing_data(
    file: UploadFile = File(...),
    cloud_provider: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Accepts file upload (multipart/form-data) and optional cloud_provider string.
    Performs pre-validation, normalizes rows into CanonicalBillingRecord schema,
    saves records to SQLite, and returns an ingestion summary.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected for upload.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    # 50MB size limit check
    max_bytes = 50 * 1024 * 1024
    if len(file_bytes) > max_bytes:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File exceeds maximum allowed size of 50 MB ({size_mb:.1f} MB uploaded).")

    # Validate file content structure
    is_valid, validation_msg = validate_billing_content(file_bytes, cloud_provider)
    if not is_valid:
        raise HTTPException(status_code=422, detail=f"File validation failed: {validation_msg}")

    try:
        detected_provider, records = parse_billing_file(file_bytes, cloud_provider=cloud_provider)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse billing file: {str(e)}")

    if not records:
        raise HTTPException(status_code=422, detail="No valid billing records extracted from payload.")

    total_spend = 0.0
    saved_count = 0

    for rec in records:
        db_res = CanonicalResource(
            resource_id=rec.resource_id,
            resource_name=rec.resource_name,
            provider=rec.cloud_provider,
            resource_type=rec.resource_type,
            region_or_zone=rec.region_or_zone,
            project_or_account_id=rec.project_id,
            cost_amount=rec.cost_amount,
            currency=rec.currency,
            usage_amount=rec.usage_amount,
            usage_unit=rec.usage_unit,
            status_hint=rec.status_hint,
            tags_json=json.dumps(rec.tags),
            metadata_json=json.dumps(rec.metadata)
        )
        db.add(db_res)
        total_spend += rec.cost_amount
        saved_count += 1

    db.commit()

    return {
        "status": "success",
        "total_records": saved_count,
        "records_ingested": saved_count,
        "total_spend": round(total_spend, 2),
        "total_spend_ingested": round(total_spend, 2),
        "detected_providers": [detected_provider],
        "provider_detected": detected_provider,
        "cloud_provider": detected_provider,
        "filename": file.filename,
        "message": f"Successfully ingested {saved_count} records for provider '{detected_provider.upper()}'."
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
    if provider and provider != "all":
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

@router.get("/samples")
def list_available_samples():
    """Lists pre-packaged sample files available for immediate testing."""
    samples = [
        {
            "filename": "gcp_detailed_billing_sample.csv",
            "provider": "gcp",
            "format": "csv",
            "description": "GCP Detailed Usage export with active compute, orphan SSD disks, idle static IPs, and stopped VMs.",
            "download_url": "/api/v1/billing/samples/gcp_detailed_billing_sample.csv"
        },
        {
            "filename": "gcp_billing_sample.json",
            "provider": "gcp",
            "format": "json",
            "description": "GCP BigQuery export JSON format with orphan disks, unattached IPs, and idle staging instances.",
            "download_url": "/api/v1/billing/samples/gcp_billing_sample.json"
        },
        {
            "filename": "aws_cur_sample.csv",
            "provider": "aws",
            "format": "csv",
            "description": "AWS Cost and Usage Report (CUR) with unattached EBS volumes, unassociated Elastic IPs, and stopped EC2.",
            "download_url": "/api/v1/billing/samples/aws_cur_sample.csv"
        },
        {
            "filename": "azure_cost_export_sample.csv",
            "provider": "azure",
            "format": "csv",
            "description": "Azure Cost Export with unattached Managed Disks, idle Public IPs, and deallocated VMs.",
            "download_url": "/api/v1/billing/samples/azure_cost_export_sample.csv"
        }
    ]
    return {"samples": samples}

@router.get("/samples/{filename}")
def download_sample_file(filename: str):
    """Downloads a pre-packaged sample cloud billing file for testing."""
    file_path = settings.SAMPLES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample file '{filename}' not found.")

    media_type = "text/csv" if filename.endswith(".csv") else "application/json"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@router.post("/load-samples")
def load_sample_datasets(
    clear_existing: bool = Query(True, description="Clear existing database records before loading samples"),
    db: Session = Depends(get_db)
):
    """One-click loader for pre-packaged multi-cloud billing exports."""
    if clear_existing:
        db.query(WasteFinding).delete()
        db.query(CanonicalResource).delete()
        db.commit()

    samples_dir = settings.SAMPLES_DIR
    loaded = {}
    total_loaded = 0

    for p in sorted(samples_dir.glob("*.*")):
        if p.suffix.lower() in [".csv", ".json"]:
            try:
                content = p.read_bytes()
                prov, recs = parse_billing_file(content)
                for rec in recs:
                    db_res = CanonicalResource(
                        resource_id=rec.resource_id,
                        resource_name=rec.resource_name,
                        provider=rec.cloud_provider,
                        resource_type=rec.resource_type,
                        region_or_zone=rec.region_or_zone,
                        project_or_account_id=rec.project_id,
                        cost_amount=rec.cost_amount,
                        currency=rec.currency,
                        usage_amount=rec.usage_amount,
                        usage_unit=rec.usage_unit,
                        status_hint=rec.status_hint,
                        tags_json=json.dumps(rec.tags),
                        metadata_json=json.dumps(rec.metadata)
                    )
                    db.add(db_res)
                db.commit()
                loaded[p.name] = len(recs)
                total_loaded += len(recs)
            except Exception as e:
                loaded[p.name] = f"Error: {str(e)}"

    return {
        "status": "success",
        "total_records_loaded": total_loaded,
        "loaded_samples": loaded,
        "message": f"Successfully loaded {total_loaded} sample records across GCP, AWS, and Azure."
    }

@router.delete("/clear")
@router.post("/clear")
def clear_all_records(db: Session = Depends(get_db)):
    """Purges all canonical resources and waste findings for a clean state."""
    deleted_findings = db.query(WasteFinding).delete()
    deleted_resources = db.query(CanonicalResource).delete()
    db.commit()
    return {
        "status": "success",
        "message": f"Purged {deleted_resources} cloud resources and {deleted_findings} waste findings.",
        "deleted_resources": deleted_resources,
        "deleted_findings": deleted_findings
    }
