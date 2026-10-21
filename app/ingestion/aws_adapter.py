import io
import json
import csv
from typing import List, Dict, Any, Union
from app.ingestion.base import IngestionAdapter

class AWSIngestionAdapter(IngestionAdapter):
    """Adapter for AWS Cost and Usage Report (CUR) (CSV & JSON)."""

    @property
    def provider(self) -> str:
        return "aws"

    def parse_records(self, raw_data: Union[str, bytes, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if isinstance(raw_data, bytes):
            raw_text = raw_data.decode("utf-8", errors="replace")
        elif isinstance(raw_data, str):
            raw_text = raw_data
        else:
            return self._normalize_records(raw_data)

        trimmed = raw_text.strip()
        if trimmed.startswith("[") or trimmed.startswith("{"):
            parsed_json = json.loads(trimmed)
            if isinstance(parsed_json, dict):
                for key in ["records", "rows", "items", "data"]:
                    if key in parsed_json and isinstance(parsed_json[key], list):
                        return self._normalize_records(parsed_json[key])
                return self._normalize_records([parsed_json])
            elif isinstance(parsed_json, list):
                return self._normalize_records(parsed_json)

        reader = csv.DictReader(io.StringIO(raw_text))
        rows = [row for row in reader]
        return self._normalize_records(rows)

    def _normalize_records(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        canonical_records = []
        for row in rows:
            product_name = (
                row.get("product/ProductName") or
                row.get("product_name") or
                row.get("service") or
                row.get("Service") or
                ""
            )
            item_desc = (
                row.get("lineItem/LineItemDescription") or
                row.get("item_description") or
                row.get("description") or
                ""
            )
            account_id = (
                row.get("lineItem/UsageAccountId") or
                row.get("account_id") or
                row.get("LinkedAccountId") or
                "123456789012"
            )
            region = (
                row.get("product/region") or
                row.get("region") or
                row.get("AvailabilityZone") or
                "us-east-1"
            )
            cost = self._parse_float(
                row.get("lineItem/UnblendedCost") or
                row.get("cost") or
                row.get("Cost") or
                0.0
            )
            currency = row.get("lineItem/CurrencyCode") or row.get("currency") or "USD"
            usage = self._parse_float(
                row.get("lineItem/UsageAmount") or
                row.get("usage_amount") or
                0.0
            )
            usage_unit = row.get("pricing/unit") or row.get("usage_unit") or "Hrs"

            res_id = (
                row.get("lineItem/ResourceId") or
                row.get("resource_id") or
                row.get("ResourceId") or
                ""
            )
            res_name = (
                row.get("resource_name") or
                (res_id.split("/")[-1] if "/" in res_id else res_id) or
                f"aws-resource-{len(canonical_records)+1}"
            )

            status_hint = (row.get("status_hint") or row.get("status") or "").lower()
            resource_type = "other"

            combined = f"{product_name} {item_desc}".lower()
            if "snapshot" in combined:
                resource_type = "snapshot"
                if not status_hint:
                    status_hint = "stale" if int(row.get("snapshot_age_days") or 0) > 30 else "active"
            elif any(k in combined for k in ["elastic ip", "elasticip", "eip", "public ip"]):
                resource_type = "ip"
                if not status_hint:
                    status_hint = "unattached" if "unassociated" in combined or "idle" in combined else "active"
            elif "ebs" in combined or "volume" in combined or "disk" in combined:
                resource_type = "disk"
                if not status_hint:
                    status_hint = "unattached" if row.get("attached_vm") in [None, "", "null"] and usage == 0 else "active"
            elif any(k in combined for k in ["instance", "compute"]) or ("ec2" in combined and "ebs" not in combined):
                resource_type = "instance"
                if not status_hint:
                    status_hint = "stopped" if row.get("instance_state") == "stopped" or usage == 0 else "active"

            if not res_id:
                res_id = f"arn:aws:{resource_type}:{region}:{account_id}:{res_name}"

            canonical_records.append({
                "resource_id": res_id,
                "resource_name": res_name,
                "provider": "aws",
                "resource_type": resource_type,
                "region_or_zone": region,
                "project_or_account_id": account_id,
                "cost_amount": cost,
                "currency": currency,
                "usage_amount": usage,
                "usage_unit": usage_unit,
                "status_hint": status_hint or "active",
                "tags": self._extract_tags(row),
                "metadata": {
                    "product_name": product_name,
                    "item_description": item_desc,
                    "attached_vm": row.get("attached_vm"),
                    "idle_days": int(row.get("idle_days") or 0),
                    "snapshot_age_days": int(row.get("snapshot_age_days") or 0)
                }
            })
        return canonical_records

    def _extract_tags(self, row: Dict[str, Any]) -> Dict[str, str]:
        tags = {}
        for k, v in row.items():
            if k.startswith("resourceTags/user:"):
                tags[k.replace("resourceTags/user:", "")] = str(v)
            elif k.startswith("tag:"):
                tags[k.replace("tag:", "")] = str(v)
        raw_tags = row.get("tags")
        if isinstance(raw_tags, dict):
            tags.update({str(k): str(v) for k, v in raw_tags.items()})
        return tags

    def _parse_float(self, val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
