from typing import Dict, Any, Optional
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import ExpoITHardwareOrder

class ExpoITAdapter(BaseAdapter):
    """
    Mock Connector for ExpoIT / Hardware Fulfillment & Shipping System
    """
    def __init__(self):
        self._orders: Dict[str, ExpoITHardwareOrder] = {}  # key: candidate_id or order_id

    @property
    def system_name(self) -> str:
        return "ExpoIT_Hardware"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        record = self._orders.get(candidate_id)
        return record.dict() if record else None

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._orders.get(candidate_id)
        if existing:
            updated = existing.dict()
            updated.update(data)
            record = ExpoITHardwareOrder(**updated)
        else:
            order_id = data.get("order_id") or f"EXPO-{5000 + len(self._orders) + 1}"
            payload = {
                "order_id": order_id,
                "candidate_id": candidate_id,
                "recipient_name": data.get("recipient_name", data.get("full_name", "Hire Name")),
                "laptop_model": data.get("laptop_model", data.get("hardware_tier", "MacBook Pro 16")),
                "shipping_street": data.get("shipping_street", data.get("street", "123 Main St")),
                "shipping_city": data.get("shipping_city", data.get("city", "San Francisco")),
                "shipping_state": data.get("shipping_state", data.get("state", "CA")),
                "shipping_zip": data.get("shipping_zip", data.get("zip_code", "94105")),
                "shipping_status": data.get("shipping_status", "Ordered"),
                "estimated_delivery": data.get("estimated_delivery"),
                "target_start_date": data.get("target_start_date", data.get("start_date", "2026-09-01"))
            }
            record = ExpoITHardwareOrder(**payload)

        self._orders[candidate_id] = record
        return record.dict()

    def delete_record(self, candidate_id: str) -> bool:
        if candidate_id in self._orders:
            del self._orders[candidate_id]
            return True
        return False

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return {cid: order.dict() for cid, order in self._orders.items()}
