from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class CanonicalBillingRecord(BaseModel):
    """Canonical representation of normalized cloud billing items across GCP, AWS, and Azure."""
    resource_id: str = Field(..., description="Cloud native identifier or ARN")
    resource_name: str = Field(..., description="Human readable resource name")
    cloud_provider: str = Field(..., description="gcp, aws, or azure")
    resource_type: str = Field(..., description="disk, instance, ip, snapshot, etc.")
    region_or_zone: str = Field(default="us-central1-a", description="Cloud zone or region")
    project_id: str = Field(..., description="GCP project ID, AWS account ID, or Azure subscription ID")
    cost_amount: float = Field(default=0.0, ge=0.0, description="Incurred monetary cost")
    currency: str = Field(default="USD", description="Currency code")
    usage_amount: float = Field(default=0.0, description="Usage amount")
    usage_unit: str = Field(default="hours", description="Unit of measurement")
    status_hint: str = Field(default="active", description="unattached, idle, stopped, stale, active")
    tags: Dict[str, Any] = Field(default_factory=dict, description="Resource labels and tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Vendor metadata attributes")

    # Helper property for compatibility with provider attribute
    @property
    def provider(self) -> str:
        return self.cloud_provider

    @property
    def project_or_account_id(self) -> str:
        return self.project_id
