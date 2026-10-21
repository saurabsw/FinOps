from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.db.database import init_db
from backend.app.routers.billing import router as billing_router
from backend.app.routers.optimizer import router as optimizer_router
from backend.app.routers.custom_rules import router as custom_rules_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API-First Multi-Cloud FinOps Cost Optimizer & Safe Remediation Engine.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(billing_router, prefix=settings.API_V1_STR)
app.include_router(optimizer_router, prefix=settings.API_V1_STR)
app.include_router(custom_rules_router, prefix=settings.API_V1_STR)

# Health endpoint
@app.get("/api/v1/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "sqlite_embedded"
    }

# Static files & dashboard serving
static_dir = settings.BASE_DIR / "app" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "FinOps API Engine is running. Visit /docs for OpenAPI specs."}
