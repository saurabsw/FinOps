import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import init_db, get_db
from app.db.models import CanonicalResource, CustomRule
from app.api.v1.health import router as health_router
from app.api.v1.billing import router as billing_router
from app.api.v1.optimizer import router as optimizer_router
from app.api.v1.rules import router as rules_router
from app.ingestion.detector import parse_billing_content

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API-first Multi-Cloud FinOps Cost Optimizer & Safe Remediation Engine with SQLite and UI Dashboard.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(billing_router, prefix=settings.API_V1_STR)
app.include_router(optimizer_router, prefix=settings.API_V1_STR)
app.include_router(rules_router, prefix=settings.API_V1_STR)

# Static files directory
static_dir = settings.STATIC_DIR
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", include_in_schema=False)
def serve_dashboard():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "FinOps API Engine is running. Visit /docs for OpenAPI documentation."}

@app.post(f"{settings.API_V1_STR}/billing/load-samples", tags=["Billing Ingestion"])
def load_sample_datasets(db: Session = Depends(get_db)):
    """
    Utility endpoint to populate SQLite with pre-packaged realistic cloud billing data
    containing active compute, unattached GCP persistent disks, idle external static IPs,
    stopped GCP VMs, and stale GCP snapshots.
    """
    samples_dir = settings.SAMPLES_DIR
    loaded_counts = {}

    for file_path in samples_dir.glob("*.*"):
        if file_path.suffix.lower() in [".csv", ".json"]:
            try:
                content = file_path.read_text(encoding="utf-8")
                detected_prov, records = parse_billing_content(content)
                for rec in records:
                    import json
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
                db.commit()
                loaded_counts[file_path.name] = len(records)
            except Exception as e:
                loaded_counts[file_path.name] = f"Error: {str(e)}"

    return {
        "status": "success",
        "loaded_samples": loaded_counts,
        "message": "Sample billing datasets loaded into SQLite."
    }
