import io
import json
import csv
from typing import List, Dict, Any, Union
from app.ingestion.base import IngestionAdapter

class GCPIngestionAdapter(IngestionAdapter):
    """Adapter for Google Cloud Platform Detailed Billing Exports (CSV & JSON)."""

    @property
    def provider(self) -> str:
        return "gcp"

    def parse_records(self, raw_data: Union[str, bytes, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        if isinstance(raw_data, bytes):
            raw_text = raw_data.decode("utf-8", errors="replace")
        elif isinstance(raw_data, str):
            raw_text = raw_data
        else:
            # Already a list of dicts
            return self._normalize_records(raw_data)

        # Detect JSON vs CSV
        trimmed = raw_text.strip()
        if trimmed.startswith("[") or trimmed.startswith("{"):
            parsed_json = json.loads(trimmed)
            if isinstance(parsed_json, dict):
                # could be wrapped in a key like "records" or "rows"
                for key in ["records", "rows", "items", "data"]:
                    if key in parsed_json and isinstance(parsed_json[key], list):
                        return self._normalize_records(parsed_json[key])
                return self._normalize_records([parsed_json])
            elif isinstance(parsed_json, list):
                return self._normalize_records(parsed_json)

        # Parse CSV
        reader = csv.DictReader(io.StringIO(raw_text))
        rows = [row for row in reader]
        return self._normalize_records(rows)

    def _normalize_records(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        canonical_records = []

        for row in rows:
            # GCP field resolution
            service_desc = (
                self._get_nested(row, ["service", "description"]) or
                row.get("service_description") or
                row.get("Service description") or
                row.get("service") or
                ""
            )
            sku_desc = (
                self._get_nested(row, ["sku", "description"]) or
                row.get("sku_description") or
                row.get("SKU description") or
                row.get("sku") or
                ""
            )
            project_id = (
                self._get_nested(row, ["project", "id"]) or
                row.get("project_id") or
                row.get("Project ID") or
                row.get("project") or
                "unknown-gcp-project"
            )
            zone_or_region = (
                self._get_nested(row, ["location", "zone"]) or
                self._get_nested(row, ["location", "region"]) or
                row.get("location") or
                row.get("zone") or
                row.get("region") or
                "us-central1-a"
            )

            # Cost and Currency
            cost = self._parse_float(
                self._get_nested(row, ["cost"]) or
                row.get("cost") or
                row.get("Cost") or
                row.get("cost_amount") or
                0.0
            )
            currency = (
                self._get_nested(row, ["currency"]) or
                row.get("currency") or
                row.get("Currency") or
                "USD"
            )

            # Usage
            usage_amount = self._parse_float(
                self._get_nested(row, ["usage", "amount"]) or
                row.get("usage_amount") or
                row.get("Usage amount") or
                0.0
            )
            usage_unit = (
                self._get_nested(row, ["usage", "unit"]) or
                row.get("usage_unit") or
                row.get("Usage unit") or
                "hours"
            )

            # Resource name and ID
            res_id = (
                self._get_nested(row, ["resource", "name"]) or
                self._get_nested(row, ["resource", "global_name"]) or
                row.get("resource_id") or
                row.get("Resource ID") or
                row.get("resource_name") or
                row.get("Resource name") or
                ""
            )
            res_name = (
                row.get("resource_name") or
                row.get("Resource name") or
                (res_id.split("/")[-1] if "/" in res_id else res_id) or
                f"gcp-resource-{len(canonical_records)+1}"
            )

            # Labels / Tags
            labels = self._extract_labels(row)

            # Status and Resource Type derivation
            explicit_status = (
                row.get("status_hint") or
                row.get("status") or
                row.get("Status") or
                ""
            ).lower()

            resource_type, status_hint = self._infer_gcp_type_and_status(
                service_desc, sku_desc, explicit_status, row, usage_amount
            )

            # If resource_id was empty, synthesize from type and name
            if not res_id:
                res_id = f"projects/{project_id}/zones/{zone_or_region}/{resource_type}s/{res_name}"

            # Extra metadata
            metadata = {
                "service_description": service_desc,
                "sku_description": sku_desc,
                "disk_size_gb": row.get("disk_size_gb") or row.get("size_gb"),
                "idle_days": self._parse_int(row.get("idle_days") or row.get("days_idle") or 0),
                "attached_vm": row.get("attached_vm") or row.get("attachment") or None,
                "ip_address": row.get("ip_address") or row.get("address") or None,
                "snapshot_age_days": self._parse_int(row.get("snapshot_age_days") or row.get("age_days") or 0),
                "vm_state": row.get("vm_state") or row.get("instance_state") or None
            }

            canonical_records.append({
                "resource_id": res_id,
                "resource_name": res_name,
                "provider": "gcp",
                "resource_type": resource_type,
                "region_or_zone": zone_or_region,
                "project_or_account_id": project_id,
                "cost_amount": cost,
                "currency": currency,
                "usage_amount": usage_amount,
                "usage_unit": usage_unit,
                "status_hint": status_hint,
                "tags": labels,
                "metadata": metadata
            })

        return canonical_records

    def _infer_gcp_type_and_status(
        self, service: str, sku: str, explicit_status: str, row: Dict[str, Any], usage_amount: float
    ) -> (str, str):
        combined = f"{service} {sku} {row.get('resource_type', '')}".lower()
        
        # 1. Persistent Disks
        if any(k in combined for k in ["persistent disk", "pd-standard", "pd-ssd", "pd-balanced", "storage pd capacity", "disk"]):
            resource_type = "disk"
            if explicit_status in ["unattached", "orphan", "detached", "idle"]:
                status = "unattached"
            elif row.get("attached_vm") in [None, "", "none", "null"] and (usage_amount == 0 or explicit_status != "active"):
                status = "unattached"
            elif explicit_status:
                status = explicit_status
            else:
                status = "active"
            return resource_type, status

        # 2. Static / External IPs
        if any(k in combined for k in ["external ip", "static ip", "ip charge", "ip reservation", "public ip"]):
            resource_type = "ip"
            if explicit_status in ["unattached", "unassigned", "idle"]:
                status = "unattached"
            elif "unassigned" in combined or "idle" in combined or "unused" in combined:
                status = "unattached"
            elif explicit_status:
                status = explicit_status
            else:
                status = "active"
            return resource_type, status

        # 3. Compute Instances / VMs
        if any(k in combined for k in ["instance core", "instance ram", "compute engine instance", "predefined instance", "custom instance", "vm"]):
            resource_type = "instance"
            if explicit_status in ["stopped", "terminated", "idle"]:
                status = "stopped"
            elif row.get("vm_state") in ["TERMINATED", "STOPPED"] or usage_amount == 0:
                status = "stopped"
            elif explicit_status:
                status = explicit_status
            else:
                status = "active"
            return resource_type, status

        # 4. Snapshots
        if any(k in combined for k in ["snapshot", "storage image"]):
            resource_type = "snapshot"
            age = self._parse_int(row.get("snapshot_age_days") or row.get("age_days") or 0)
            if age > 30 or explicit_status in ["stale", "aged"]:
                status = "stale"
            elif explicit_status:
                status = explicit_status
            else:
                status = "active"
            return resource_type, status

        # 5. Cloud SQL
        if "cloud sql" in combined or "sql" in combined:
            return "sql", explicit_status or "active"

        # 6. Cloud Storage
        if "cloud storage" in combined or "storage" in combined:
            return "storage", explicit_status or "active"

        return "other", explicit_status or "active"

    def _extract_labels(self, row: Dict[str, Any]) -> Dict[str, str]:
        labels = {}
        raw_labels = row.get("labels") or row.get("tags") or {}
        if isinstance(raw_labels, dict):
            return {str(k): str(v) for k, v in raw_labels.items()}
        if isinstance(raw_labels, list):
            for item in raw_labels:
                if isinstance(item, dict) and "key" in item and "value" in item:
                    labels[str(item["key"])] = str(item["value"])
            return labels
        if isinstance(raw_labels, str):
            try:
                parsed = json.loads(raw_labels)
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
            except Exception:
                pass
        return labels

    def _get_nested(self, d: Dict[str, Any], keys: List[str]) -> Any:
        curr = d
        for k in keys:
            if not isinstance(curr, dict) or k not in curr:
                return None
            curr = curr[k]
        return curr

    def _parse_float(self, val: Any) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def _parse_int(self, val: Any) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0
