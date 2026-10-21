import pytest
from app.ingestion.gcp_adapter import GCPIngestionAdapter
from app.ingestion.aws_adapter import AWSIngestionAdapter
from app.ingestion.azure_adapter import AzureIngestionAdapter
from app.ingestion.detector import detect_provider, parse_billing_content
from app.core.config import settings

def test_detect_provider():
    gcp_csv_header = "billing_account_id,service.description,sku.description,project.id"
    aws_csv_header = "lineItem/ResourceId,product/ProductName,lineItem/UnblendedCost"
    azure_csv_header = "ResourceId,ConsumedService,CostInBillingCurrency"

    assert detect_provider(gcp_csv_header) == "gcp"
    assert detect_provider(aws_csv_header) == "aws"
    assert detect_provider(azure_csv_header) == "azure"

def test_gcp_csv_ingestion():
    sample_file = settings.SAMPLES_DIR / "gcp_detailed_billing_sample.csv"
    assert sample_file.exists()
    content = sample_file.read_text(encoding="utf-8")

    adapter = GCPIngestionAdapter()
    records = adapter.parse_records(content)

    assert len(records) > 0
    # Check canonical mapping
    first = records[0]
    assert first["provider"] == "gcp"
    assert "resource_id" in first
    assert "resource_name" in first
    assert "cost_amount" in first
    assert first["cost_amount"] > 0
    assert "status_hint" in first
    assert "metadata" in first

def test_gcp_json_ingestion():
    sample_file = settings.SAMPLES_DIR / "gcp_billing_sample.json"
    assert sample_file.exists()
    content = sample_file.read_text(encoding="utf-8")

    provider, records = parse_billing_content(content)
    assert provider == "gcp"
    assert len(records) == 3
    disk_rec = next(r for r in records if r["resource_name"] == "disk-datalake-etl-orphaned")
    assert disk_rec["resource_type"] == "disk"
    assert disk_rec["status_hint"] == "unattached"
    assert disk_rec["cost_amount"] == 125.0

def test_aws_cur_ingestion():
    sample_file = settings.SAMPLES_DIR / "aws_cur_sample.csv"
    assert sample_file.exists()
    content = sample_file.read_text(encoding="utf-8")

    adapter = AWSIngestionAdapter()
    records = adapter.parse_records(content)

    assert len(records) == 4
    assert any(r["resource_type"] == "disk" and r["status_hint"] == "unattached" for r in records)
    assert any(r["resource_type"] == "ip" and r["status_hint"] == "unattached" for r in records)
    assert any(r["resource_type"] == "instance" and r["status_hint"] == "stopped" for r in records)
    assert any(r["resource_type"] == "snapshot" and r["status_hint"] == "stale" for r in records)

def test_azure_cost_export_ingestion():
    sample_file = settings.SAMPLES_DIR / "azure_cost_export_sample.csv"
    assert sample_file.exists()
    content = sample_file.read_text(encoding="utf-8")

    adapter = AzureIngestionAdapter()
    records = adapter.parse_records(content)

    assert len(records) == 3
    assert any(r["resource_type"] == "disk" and r["status_hint"] == "unattached" for r in records)
    assert any(r["resource_type"] == "ip" and r["status_hint"] == "unattached" for r in records)
    assert any(r["resource_type"] == "instance" and r["status_hint"] == "stopped" for r in records)
