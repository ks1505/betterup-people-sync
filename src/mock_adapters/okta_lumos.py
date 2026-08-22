from typing import Dict, Any, Optional, List
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import OktaUserRecord

class OktaLumosAdapter(BaseAdapter):
    """
    Mock Connector for Okta Identity & Lumos App Provisioning Governance
    """
    def __init__(self):
        self._users: Dict[str, OktaUserRecord] = {}

    @property
    def system_name(self) -> str:
        return "Okta_Lumos"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        for user in self._users.values():
            if user.candidate_id == candidate_id or user.employee_id == candidate_id:
                return user.dict()
        return None

    def get_by_upn(self, upn_email: str) -> Optional[Dict[str, Any]]:
        for user in self._users.values():
            if user.upn_email.lower() == upn_email.lower():
                return user.dict()
        return None

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing_key = None
        for key, user in self._users.items():
            if user.candidate_id == candidate_id or user.employee_id == data.get("employee_id"):
                existing_key = key
                break

        if existing_key:
            updated = self._users[existing_key].dict()
            updated.update(data)
            updated["candidate_id"] = candidate_id
            record = OktaUserRecord(**updated)
            self._users[existing_key] = record
        else:
            okta_id = data.get("okta_id") or f"OKTA-{1000 + len(self._users) + 1}"
            first_initial = data.get("first_name", "user")[0].lower()
            last_name_clean = data.get("last_name", "hire").lower().replace(" ", "")
            upn = data.get("upn_email") or f"{first_initial}{last_name_clean}@betterup.co"
            
            payload = {
                "okta_id": okta_id,
                "upn_email": upn,
                "employee_id": data.get("employee_id", f"WD-{candidate_id}"),
                "candidate_id": candidate_id,
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "status": data.get("status", "STAGED"),
                "assigned_apps": data.get("assigned_apps", ["Google Workspace", "Slack", "GSuite"]),
                "activation_date": data.get("activation_date", data.get("start_date", "2026-09-01"))
            }
            record = OktaUserRecord(**payload)
            self._users[okta_id] = record

        return record.dict()

    def delete_record(self, candidate_id: str) -> bool:
        to_del = [k for k, u in self._users.items() if u.candidate_id == candidate_id]
        for k in to_del:
            del self._users[k]
        return len(to_del) > 0

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return {k: u.dict() for k, u in self._users.items()}
