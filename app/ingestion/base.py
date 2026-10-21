from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union

class IngestionAdapter(ABC):
    """Abstract base class for cloud billing data ingestion."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Returns the provider name: 'gcp', 'aws', or 'azure'."""
        pass

    @abstractmethod
    def parse_records(self, raw_data: Union[str, bytes, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Parses raw billing records into canonical resource dictionaries conforming to:
        {
            "resource_id": str,
            "resource_name": str,
            "provider": str,
            "resource_type": str, # disk | instance | ip | snapshot | sql | storage
            "region_or_zone": str,
            "project_or_account_id": str,
            "cost_amount": float,
            "currency": str,
            "usage_amount": float,
            "usage_unit": str,
            "status_hint": str, # unattached | idle | stale | active | stopped
            "tags": dict,
            "metadata": dict
        }
        """
        pass
