import io
import json
import csv
from typing import List, Dict, Any, Union
from backend.app.schemas.canonical import CanonicalBillingRecord

class GCPBillingAdapter:
    """Parses GCP billing CSV/JSON exports into CanonicalBillingRecord entries."""

    @property
    def provider(self) -> str:
        return "gcp"

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
            service = (
                self._get_nested(row, ["service", "description"]) or
                row.get("service_description") or
                row.get("Service description") or
                row.get("service") or ""
            )
            sku = (
                self._get_nested(row, ["sku", "description"]) or
                row.get("sku_description") or
                row.get("SKU description") or
                row.get("sku") or ""
            )
            project_id = (
                self._get_nested(row, ["project", "id"]) or
                row.get("project_id") or
                row.get("Project ID") or
                row.get("project") or "gcp-project-default"
            )
            zone = (
                self._get_nested(row, ["location", "zone"]) or
                self._get_nested(row, ["location", "region"]) or
                row.get("location") or
                row.get("zone") or
                row.get("region") or "us-central1-a"
            )
            cost = self._parse_float(
                self._get_nested(row, ["cost"]) or
                row.get("cost") or
                row.get("Cost") or 0.0
            )
            currency = (
                self._get_nested(row, ["currency"]) or
                row.get("currency") or "USD"
            )
            usage = self._parse_float(
                self._get_nested(row, ["usage", "amount"]) or
                row.get("usage.amount") or
                row.get("usage_amount") or 0.0
            )
            usage_unit = (
                self._get_nested(row, ["usage", "unit"]) or
                row.get("usage.unit") or
                row.get("usage_unit") or "hours"
            )

            res_id = (
                self._get_nested(row, ["resource", "name"]) or
                self._get_nested(row, ["resource", "global_name"]) or
                row.get("resource.name") or
                row.get("resource_id") or
                row.get("resource_name") or ""
            )
            res_name = (
                row.get("resource_name") or
                row.get("resource.name") or
                (res_id.split("/")[-1] if "/" in res_id else res_id) or
                f"gcp-res-{len(records)+1}"
            )

            explicit_status = (row.get("status_hint") or row.get("status") or "").lower()
            res_type, status_hint = self._infer_type_and_status(service, sku, explicit_status, row, usage)

            if not res_id:
                res_id = f"projects/{project_id}/zones/{zone}/{res_type}s/{res_name}"

            labels = self._extract_labels(row)
            metadata = {
                "sku_description": sku,
                "service_description": service,
                "attached_vm": row.get("attached_vm"),
                "idle_days": self._parse_int(row.get("idle_days") or 0),
                "snapshot_age_days": self._parse_int(row.get("snapshot_age_days") or 0),
                "vm_state": row.get("vm_state") or row.get("instance_state")
            }

            records.append(CanonicalBillingRecord(
                resource_id=res_id,
                resource_name=res_name,
                cloud_provider="gcp",
                resource_type=res_type,
                region_or_zone=zone,
                project_id=project_id,
                cost_amount=cost,
                currency=currency,
                usage_amount=usage,
                usage_unit=usage_unit,
                status_hint=status_hint,
                tags=labels,
                metadata=metadata
            ))

        return records

    def _infer_type_and_status(self, service: str, sku: str, explicit_status: str, row: Dict[str, Any], usage: float):
        combined = f"{service} {sku} {row.get('resource_type', '')}".lower()

        # Unattached Disk check
        if any(k in combined for k in ["persistent disk", "pd-standard", "pd-ssd", "pd-balanced", "storage pd capacity", "disk"]):
            res_type = "disk"
            if explicit_status in ["unattached", "orphan", "detached", "idle"]:
                status = "unattached"
            elif row.get("attached_vm") in [None, "", "null", "none"] and (usage == 0 or explicit_status != "active"):
                status = "unattached"
            else:
                status = explicit_status or "active"
            return res_type, status

        # Idle External IP check
        if any(k in combined for k in ["external ip", "static ip", "ip charge", "ip reservation"]):
            res_type = "ip"
            if explicit_status in ["unattached", "unassigned", "idle"]:
                status = "unattached"
            elif "unassigned" in combined or "idle" in combined:
                status = "unattached"
            else:
                status = explicit_status or "active"
            return res_type, status

        # Stopped Instance
        if any(k in combined for k in ["instance core", "instance ram", "compute engine instance", "vm"]):
            res_type = "instance"
            if explicit_status in ["stopped", "terminated", "idle"] or row.get("vm_state") in ["STOPPED", "TERMINATED"]:
                status = "stopped"
            else:
                status = explicit_status or "active"
            return res_type, status

        # Snapshot
        if "snapshot" in combined:
            res_type = "snapshot"
            age = self._parse_int(row.get("snapshot_age_days") or 0)
            status = "stale" if (age >= 30 or explicit_status in ["stale", "aged"]) else (explicit_status or "active")
            return res_type, status

        return row.get("resource_type") or "other", explicit_status or "active"

    def _extract_labels(self, row: Dict[str, Any]) -> Dict[str, Any]:
        labels_raw = row.get("labels") or row.get("tags") or {}
        if isinstance(labels_raw, dict):
            return labels_raw
        if isinstance(labels_raw, str):
            try:
                return json.loads(labels_raw)
            except Exception:
                pass
        return {}

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
