import pytest
from backend.app.adapters.gcp_adapter import GCPBillingAdapter
from backend.app.adapters.aws_adapter import AWSBillingAdapter
from backend.app.adapters.azure_adapter import AzureBillingAdapter
from backend.app.adapters.base_adapter import get_adapter, detect_cloud_provider, parse_billing_file
from backend.app.schemas.canonical import CanonicalBillingRecord
from backend.app.core.config import settings

def test_base_adapter_factory():
    assert isinstance(get_adapter("gcp"), GCPBillingAdapter)
    assert isinstance(get_adapter("aws"), AWSBillingAdapter)
    assert isinstance(get_adapter("azure"), AzureBillingAdapter)

def test_detect_cloud_provider():
    assert detect_cloud_provider("billing_account_id,service.description,sku.description") == "gcp"
    assert detect_cloud_provider("lineItem/UnblendedCost,lineItem/ResourceId") == "aws"
    assert detect_cloud_provider("CostInBillingCurrency,ConsumedService") == "azure"

def test_gcp_adapter_transformation():
    sample_path = settings.SAMPLES_DIR / "gcp_detailed_billing_sample.csv"
    assert sample_path.exists()
    content = sample_path.read_text(encoding="utf-8")

    adapter = GCPBillingAdapter()
    records = adapter.parse(content)

    assert len(records) > 0
    for r in records:
        assert isinstance(r, CanonicalBillingRecord)
        assert r.cloud_provider == "gcp"
        assert r.resource_id != ""
        assert r.resource_name != ""
        assert r.cost_amount >= 0.0
        assert r.region_or_zone != ""
        assert r.project_id != ""

    # Verify unattached disk detection
    disk = next(r for r in records if r.resource_name == "disk-prod-db-replica-detached")
    assert disk.resource_type == "disk"
    assert disk.status_hint == "unattached"
    assert disk.cost_amount == 85.50

    # Verify idle IP detection
    ip = next(r for r in records if r.resource_name == "ip-static-nat-unassigned-1")
    assert ip.resource_type == "ip"
    assert ip.status_hint == "unattached"
    assert ip.cost_amount == 14.40

def test_aws_adapter_transformation():
    sample_path = settings.SAMPLES_DIR / "aws_cur_sample.csv"
    assert sample_path.exists()
    content = sample_path.read_text(encoding="utf-8")

    adapter = AWSBillingAdapter()
    records = adapter.parse(content)

    assert len(records) == 4
    for r in records:
        assert isinstance(r, CanonicalBillingRecord)
        assert r.cloud_provider == "aws"
        assert r.cost_amount > 0

    ebs = next(r for r in records if r.resource_id == "vol-0123456789abcdef0")
    assert ebs.resource_type == "disk"
    assert ebs.status_hint == "unattached"

    eip = next(r for r in records if r.resource_id == "eipalloc-0a1b2c3d4e5f6g7h8")
    assert eip.resource_type == "ip"
    assert eip.status_hint == "unattached"

def test_azure_adapter_transformation():
    sample_path = settings.SAMPLES_DIR / "azure_cost_export_sample.csv"
    assert sample_path.exists()
    content = sample_path.read_text(encoding="utf-8")

    adapter = AzureBillingAdapter()
    records = adapter.parse(content)

    assert len(records) == 3
    for r in records:
        assert isinstance(r, CanonicalBillingRecord)
        assert r.cloud_provider == "azure"

    disk = next(r for r in records if "disk-unattached-analytics" in r.resource_id)
    assert disk.resource_type == "disk"
    assert disk.status_hint == "unattached"

def test_parse_billing_file_auto_detection():
    sample_path = settings.SAMPLES_DIR / "gcp_billing_sample.json"
    content = sample_path.read_text(encoding="utf-8")

    prov, records = parse_billing_file(content)
    assert prov == "gcp"
    assert len(records) == 3
    assert all(isinstance(r, CanonicalBillingRecord) for r in records)

def test_validation_rejects_empty_and_corrupt_files():
    # Empty file
    with pytest.raises(ValueError, match="empty"):
        parse_billing_file("")

    # Malformed JSON
    with pytest.raises(ValueError, match="Malformed JSON"):
        parse_billing_file("{\"records\": [corrupted json")

    # Non-billing arbitrary CSV
    with pytest.raises(ValueError, match="Unrecognized CSV schema"):
        parse_billing_file("first_name,last_name,age\nAlice,Smith,30\nBob,Jones,25")
