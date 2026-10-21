import io
import json
import csv
from typing import List, Dict, Any, Union
from backend.app.schemas.canonical import CanonicalBillingRecord

class AWSBillingAdapter:
    """Parses AWS Cost and Usage Report (CUR) CSV/JSON into CanonicalBillingRecord entries."""

    @property
    def provider(self) -> str:
        return "aws"

    def parse(self, content: Union[str, bytes]) -> List[CanonicalBillingRecord]:
        raw_text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        trimmed = raw_text.strip()

        if trimmed.startswith("[") or trimmed.startswith("{"):
            parsed_json = json.loads(trimmed)
            if isinstance(parsed_json, dict):
                for k in ["records", "rows", "items", "data"]:
                    if k in parsed_json and isinstance(parsed_json[k], list):
                        return self._normalize_rows(parsed_json[k])
                return self._normalize_rows([parsed_json])
            elif isinstance(parsed_json, list):
                return self._normalize_rows(parsed_json)

        reader = csv.DictReader(io.StringIO(raw_text))
        rows = [r for r in reader]
        return self._normalize_rows(rows)

    def _normalize_rows(self, rows: List[Dict[str, Any]]) -> List[CanonicalBillingRecord]:
        records: List[CanonicalBillingRecord] = []

        for row in rows:
            prod_name = (
                row.get("product/ProductName") or
                row.get("product_name") or
                row.get("service") or ""
            )
            item_desc = (
                row.get("lineItem/LineItemDescription") or
                row.get("item_description") or
                row.get("description") or ""
            )
            account_id = (
                row.get("lineItem/UsageAccountId") or
                row.get("account_id") or
                row.get("LinkedAccountId") or "123456789012"
            )
            region = (
                row.get("product/region") or
                row.get("region") or
                row.get("AvailabilityZone") or "us-east-1"
            )
            cost = self._parse_float(
                row.get("lineItem/UnblendedCost") or
                row.get("cost") or 0.0
            )
            currency = row.get("lineItem/CurrencyCode") or row.get("currency") or "USD"
            usage = self._parse_float(
                row.get("lineItem/UsageAmount") or
                row.get("usage_amount") or 0.0
            )
            usage_unit = row.get("pricing/unit") or row.get("usage_unit") or "Hrs"

            res_id = (
                row.get("lineItem/ResourceId") or
                row.get("resource_id") or ""
            )
            res_name = (
                row.get("resource_name") or
                (res_id.split("/")[-1] if "/" in res_id else res_id) or
                f"aws-res-{len(records)+1}"
            )

            status_hint = (row.get("status_hint") or row.get("status") or "").lower()
            combined = f"{prod_name} {item_desc}".lower()

            if "snapshot" in combined:
                res_type = "snapshot"
                if not status_hint:
                    age = int(row.get("snapshot_age_days") or 0)
                    status_hint = "stale" if age > 30 else "active"
            elif any(k in combined for k in ["elastic ip", "elasticip", "eip", "public ip"]):
                res_type = "ip"
                if not status_hint:
                    status_hint = "unattached" if "unassociated" in combined or "idle" in combined else "active"
            elif "ebs" in combined or "volume" in combined or "disk" in combined:
                res_type = "disk"
                if not status_hint:
                    status_hint = "unattached" if row.get("attached_vm") in [None, "", "null"] and usage == 0 else "active"
            elif any(k in combined for k in ["instance", "compute"]) or ("ec2" in combined and "ebs" not in combined):
                res_type = "instance"
                if not status_hint:
                    status_hint = "stopped" if row.get("instance_state") == "stopped" or usage == 0 else "active"
            else:
                res_type = row.get("resource_type") or "other"
                if not status_hint:
                    status_hint = "active"

            if not res_id:
                res_id = f"arn:aws:{res_type}:{region}:{account_id}:{res_name}"

            tags = self._extract_tags(row)
            metadata = {
                "product_name": prod_name,
                "item_description": item_desc,
                "attached_vm": row.get("attached_vm"),
                "idle_days": int(row.get("idle_days") or 0),
                "snapshot_age_days": int(row.get("snapshot_age_days") or 0)
            }

            records.append(CanonicalBillingRecord(
                resource_id=res_id,
                resource_name=res_name,
                cloud_provider="aws",
                resource_type=res_type,
                region_or_zone=region,
                project_id=account_id,
                cost_amount=cost,
                currency=currency,
                usage_amount=usage,
                usage_unit=usage_unit,
                status_hint=status_hint,
                tags=tags,
                metadata=metadata
            ))

        return records

    def _extract_tags(self, row: Dict[str, Any]) -> Dict[str, Any]:
        tags = {}
        for k, v in row.items():
            if k.startswith("resourceTags/user:"):
                tags[k.replace("resourceTags/user:", "")] = v
            elif k.startswith("tag:"):
                tags[k.replace("tag:", "")] = v
        raw = row.get("tags")
        if isinstance(raw, dict):
            tags.update(raw)
        return tags

    def _parse_float(self, val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
