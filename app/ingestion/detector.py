import json
from typing import List, Dict, Any, Union, Tuple
from app.ingestion.base import IngestionAdapter
from app.ingestion.gcp_adapter import GCPIngestionAdapter
from app.ingestion.aws_adapter import AWSIngestionAdapter
from app.ingestion.azure_adapter import AzureIngestionAdapter

ADAPTERS: Dict[str, IngestionAdapter] = {
    "gcp": GCPIngestionAdapter(),
    "aws": AWSIngestionAdapter(),
    "azure": AzureIngestionAdapter()
}

def detect_provider(raw_text: str) -> str:
    """
    Intelligently inspects headers or JSON attributes to infer cloud provider.
    Defaults to GCP if ambiguous (as this is primarily a GCP FinOps engine).
    """
    sample = raw_text[:4000].lower()

    # AWS indicators
    if any(k in sample for k in ["lineitem/unblendedcost", "lineitem/resourceid", "product/productname", "usageaccountid", "cur_"]):
        return "aws"

    # Azure indicators
    if any(k in sample for k in ["costinbillingcurrency", "consumedservice", "metercategory", "subscriptionid", "resourcelocation"]):
        return "azure"

    # GCP indicators
    if any(k in sample for k in ["service.description", "sku.description", "project.id", "billing_account_id", "gcp", "google"]):
        return "gcp"

    return "gcp"

def parse_billing_content(content: Union[str, bytes], provider: str = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Detects provider if not supplied, and returns (detected_provider, canonical_records).
    """
    if isinstance(content, bytes):
        raw_text = content.decode("utf-8", errors="replace")
    else:
        raw_text = content

    detected_prov = provider.lower() if provider and provider.lower() in ADAPTERS else detect_provider(raw_text)
    adapter = ADAPTERS.get(detected_prov, ADAPTERS["gcp"])
    records = adapter.parse_records(raw_text)
    return detected_prov, records
