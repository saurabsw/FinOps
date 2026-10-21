import io
import json
import csv
from typing import List, Dict, Any, Union
from app.ingestion.base import IngestionAdapter

class AzureIngestionAdapter(IngestionAdapter):
    """Adapter for Azure Cost Export (CSV & JSON)."""

    @property
    def provider(self) -> str:
        return "azure"

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
            consumed_service = row.get("ConsumedService") or row.get("consumed_service") or row.get("service") or ""
            meter_category = row.get("MeterCategory") or row.get("meter_category") or ""
            subscription_id = row.get("SubscriptionId") or row.get("subscription_id") or "sub-00000000"
            resource_location = row.get("ResourceLocation") or row.get("resource_location") or "eastus"
            cost = self._parse_float(row.get("CostInBillingCurrency") or row.get("cost") or row.get("PreTaxCost") or 0.0)
            currency = row.get("BillingCurrency") or row.get("currency") or "USD"
            usage = self._parse_float(row.get("UsageQuantity") or row.get("usage_amount") or 0.0)
            usage_unit = row.get("UnitOfMeasure") or row.get("usage_unit") or "Hours"

            res_id = row.get("ResourceId") or row.get("resource_id") or ""
            res_name = row.get("ResourceName") or row.get("resource_name") or (res_id.split("/")[-1] if "/" in res_id else res_id) or f"azure-res-{len(canonical_records)+1}"

            combined = f"{consumed_service} {meter_category} {row.get('resource_type', '')}".lower()
            status_hint = (row.get("status_hint") or row.get("status") or "").lower()
            resource_type = "other"

            if "snapshot" in combined:
                resource_type = "snapshot"
                if not status_hint:
                    status_hint = "stale" if int(row.get("snapshot_age_days") or 0) > 30 else "active"
            elif "public ip" in combined or "publicip" in combined or "pip" in combined:
                resource_type = "ip"
                if not status_hint:
                    status_hint = "unattached" if "unassociated" in combined or "idle" in combined else "active"
            elif any(k in combined for k in ["virtual machines", "virtualmachine", "vm"]) and "disk" not in combined:
                resource_type = "instance"
                if not status_hint:
                    status_hint = "stopped" if row.get("vm_state") == "Deallocated" or usage == 0 else "active"
            elif "disk" in combined or "storage" in combined:
                resource_type = "disk"
                if not status_hint:
                    status_hint = "unattached" if row.get("attached_vm") in [None, "", "null"] and usage == 0 else "active"

            if not res_id:
                res_id = f"/subscriptions/{subscription_id}/resourceGroups/default/providers/Microsoft.Compute/{resource_type}s/{res_name}"

            canonical_records.append({
                "resource_id": res_id,
                "resource_name": res_name,
                "provider": "azure",
                "resource_type": resource_type,
                "region_or_zone": resource_location,
                "project_or_account_id": subscription_id,
                "cost_amount": cost,
                "currency": currency,
                "usage_amount": usage,
                "usage_unit": usage_unit,
                "status_hint": status_hint or "active",
                "tags": self._extract_tags(row),
                "metadata": {
                    "consumed_service": consumed_service,
                    "meter_category": meter_category,
                    "attached_vm": row.get("attached_vm"),
                    "idle_days": int(row.get("idle_days") or 0)
                }
            })
        return canonical_records

    def _extract_tags(self, row: Dict[str, Any]) -> Dict[str, str]:
        tags_raw = row.get("Tags") or row.get("tags")
        if isinstance(tags_raw, dict):
            return {str(k): str(v) for k, v in tags_raw.items()}
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
