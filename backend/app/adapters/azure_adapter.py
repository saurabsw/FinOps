import io
import json
import csv
from typing import List, Dict, Any, Union
from backend.app.schemas.canonical import CanonicalBillingRecord

class AzureBillingAdapter:
    """Parses Azure Cost Export CSV/JSON into CanonicalBillingRecord entries."""

    @property
    def provider(self) -> str:
        return "azure"

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
            consumed = row.get("ConsumedService") or row.get("consumed_service") or row.get("service") or ""
            meter_cat = row.get("MeterCategory") or row.get("meter_category") or ""
            sub_id = row.get("SubscriptionId") or row.get("subscription_id") or "sub-00000000"
            location = row.get("ResourceLocation") or row.get("resource_location") or "eastus"
            cost = self._parse_float(row.get("CostInBillingCurrency") or row.get("cost") or row.get("PreTaxCost") or 0.0)
            currency = row.get("BillingCurrency") or row.get("currency") or "USD"
            usage = self._parse_float(row.get("UsageQuantity") or row.get("usage_amount") or 0.0)
            usage_unit = row.get("UnitOfMeasure") or row.get("usage_unit") or "Hours"

            res_id = row.get("ResourceId") or row.get("resource_id") or ""
            res_name = (
                row.get("ResourceName") or
                row.get("resource_name") or
                (res_id.split("/")[-1] if "/" in res_id else res_id) or
                f"azure-res-{len(records)+1}"
            )

            status_hint = (row.get("status_hint") or row.get("status") or "").lower()
            combined = f"{consumed} {meter_cat} {row.get('resource_type', '')}".lower()

            if "snapshot" in combined:
                res_type = "snapshot"
                if not status_hint:
                    age = int(row.get("snapshot_age_days") or 0)
                    status_hint = "stale" if age > 30 else "active"
            elif "public ip" in combined or "publicip" in combined or "pip" in combined:
                res_type = "ip"
                if not status_hint:
                    status_hint = "unattached" if "unassociated" in combined or "idle" in combined else "active"
            elif any(k in combined for k in ["virtual machines", "virtualmachine", "vm"]) and "disk" not in combined:
                res_type = "instance"
                if not status_hint:
                    status_hint = "stopped" if row.get("vm_state") == "Deallocated" or usage == 0 else "active"
            elif "disk" in combined or "storage" in combined:
                res_type = "disk"
                if not status_hint:
                    status_hint = "unattached" if row.get("attached_vm") in [None, "", "null"] and usage == 0 else "active"
            else:
                res_type = row.get("resource_type") or "other"
                if not status_hint:
                    status_hint = "active"

            if not res_id:
                res_id = f"/subscriptions/{sub_id}/resourceGroups/default/providers/Microsoft.Compute/{res_type}s/{res_name}"

            tags = self._extract_tags(row)
            metadata = {
                "consumed_service": consumed,
                "meter_category": meter_cat,
                "attached_vm": row.get("attached_vm"),
                "idle_days": int(row.get("idle_days") or 0)
            }

            records.append(CanonicalBillingRecord(
                resource_id=res_id,
                resource_name=res_name,
                cloud_provider="azure",
                resource_type=res_type,
                region_or_zone=location,
                project_id=sub_id,
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
        tags_raw = row.get("Tags") or row.get("tags")
        if isinstance(tags_raw, dict):
            return tags_raw
        if isinstance(tags_raw, str):
            try:
                return json.loads(tags_raw)
            except Exception:
                pass
        return {}

    def _parse_float(self, val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
