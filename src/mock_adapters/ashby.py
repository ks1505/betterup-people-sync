from typing import Dict, Any, Optional
from datetime import datetime
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import AshbyOfferRecord

class AshbyAdapter(BaseAdapter):
    """
    Mock Connector for Ashby ATS
    """
    def __init__(self):
        self._offers: Dict[str, AshbyOfferRecord] = {}

    @property
    def system_name(self) -> str:
        return "Ashby_ATS"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        record = self._offers.get(candidate_id)
        return record.dict() if record else None

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._offers.get(candidate_id)
        if existing:
            updated_data = existing.dict()
            updated_data.update(data)
            updated_data["last_modified"] = datetime.utcnow()
            record = AshbyOfferRecord(**updated_data)
        else:
            data["candidate_id"] = candidate_id
            if "offer_id" not in data:
                data["offer_id"] = f"ASH-OFFER-{candidate_id}"
            data["last_modified"] = datetime.utcnow()
            record = AshbyOfferRecord(**data)

        self._offers[candidate_id] = record
        return record.dict()

    def delete_record(self, candidate_id: str) -> bool:
        if candidate_id in self._offers:
            del self._offers[candidate_id]
            return True
        return False

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return {cid: rec.dict() for cid, rec in self._offers.items()}
