from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from backend.app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Auto-migrate missing columns in existing SQLite tables
    with engine.connect() as conn:
        try:
            res = conn.exec_driver_sql("PRAGMA table_info(custom_rules)").fetchall()
            cols = [c[1] for c in res]
            if cols and "logic_operator" not in cols:
                conn.exec_driver_sql("ALTER TABLE custom_rules ADD COLUMN logic_operator VARCHAR(10) DEFAULT 'all'")
                conn.commit()
        except Exception:
            pass

    # Seed default Tier 2 Governance Rules if empty
    db = SessionLocal()
    try:
        from backend.app.db.models import CustomRule
        if db.query(CustomRule).count() == 0:
            default_rules = [
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
            for r in default_rules:
                db.add(r)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
