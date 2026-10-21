import json
import csv
import io
from typing import Optional, Union, List, Tuple
from backend.app.schemas.canonical import CanonicalBillingRecord
from backend.app.adapters.gcp_adapter import GCPBillingAdapter
from backend.app.adapters.aws_adapter import AWSBillingAdapter
from backend.app.adapters.azure_adapter import AzureBillingAdapter

ADAPTERS = {
    "gcp": GCPBillingAdapter(),
    "aws": AWSBillingAdapter(),
    "azure": AzureBillingAdapter()
}

RECOGNIZED_BILLING_SIGNATURES = {
    "aws": ["lineitem/unblendedcost", "lineitem/resourceid", "product/productname", "usageaccountid", "cur_"],
    "azure": ["costinbillingcurrency", "consumedservice", "metercategory", "subscriptionid", "resourcelocation"],
    "gcp": ["service.description", "sku.description", "project.id", "billing_account_id", "compute engine", "cloud storage", "cloud sql"]
}

def detect_cloud_provider(content: Union[str, bytes]) -> str:
    """Inspects raw payload to infer cloud provider."""
    raw = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    sample = raw[:5000].lower()

    if any(k in sample for k in RECOGNIZED_BILLING_SIGNATURES["aws"]):
        return "aws"
    if any(k in sample for k in RECOGNIZED_BILLING_SIGNATURES["azure"]):
        return "azure"
    if any(k in sample for k in RECOGNIZED_BILLING_SIGNATURES["gcp"]):
        return "gcp"

    return "gcp"

def validate_billing_content(content: Union[str, bytes], cloud_provider: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validates that uploaded file content is a non-empty, parseable CSV/JSON
    matching supported cloud billing exports (GCP, AWS, Azure).
    Returns (is_valid, error_or_format_message).
    """
    if not content or len(content.strip() if isinstance(content, (str, bytes)) else content) == 0:
        return False, "File is completely empty (0 bytes)."

    raw = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    sample = raw[:5000].strip()

    # 1. Check if valid JSON
    if sample.startswith("[") or sample.startswith("{"):
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, (list, dict)):
                return False, "JSON content must be a JSON array of rows or an object containing billing records."
            return True, "Valid JSON billing export format."
        except json.JSONDecodeError as e:
            return False, f"Malformed JSON syntax: {str(e)}"

    # 2. Check if valid CSV with recognized headers
    try:
        reader = csv.reader(io.StringIO(raw))
        header = next(reader, None)
        if not header:
            return False, "CSV file has no header row."

        header_str = " ".join([h.lower() for h in header])
        known_signatures = [
            "cost", "usage", "sku", "service", "lineitem", "product",
            "subscription", "meter", "resource", "billing"
        ]
        if not any(sig in header_str for sig in known_signatures):
            return False, (
                "Unrecognized CSV schema: File does not appear to be a cloud billing export. "
                "Expected headers such as 'service.description', 'lineItem/UnblendedCost', or 'CostInBillingCurrency'."
            )
        return True, "Valid CSV billing export format."
    except Exception as e:
        return False, f"Failed to parse CSV structure: {str(e)}"

def get_adapter(cloud_provider: Optional[str] = None, content: Optional[Union[str, bytes]] = None):
    """Adapter factory returning parser based on provider or inferred content."""
    provider_key = (cloud_provider or "").lower().strip()
    if not provider_key and content:
        provider_key = detect_cloud_provider(content)
    elif not provider_key:
        provider_key = "gcp"

    return ADAPTERS.get(provider_key, ADAPTERS["gcp"])

def parse_billing_file(content: Union[str, bytes], cloud_provider: Optional[str] = None) -> Tuple[str, List[CanonicalBillingRecord]]:
    """Validates and parses billing content into CanonicalBillingRecord entries."""
    is_valid, validation_msg = validate_billing_content(content, cloud_provider)
    if not is_valid:
        raise ValueError(validation_msg)

    provider_key = (cloud_provider or "").lower().strip()
    if not provider_key:
        provider_key = detect_cloud_provider(content)

    adapter = get_adapter(provider_key)
    records = adapter.parse(content)
    if not records:
        raise ValueError(f"No valid billing line items could be extracted for provider '{provider_key}'.")

    return provider_key, records
