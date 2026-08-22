from typing import Dict, Any, Optional
from datetime import datetime
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import CohortTrackerEntry

class CohortTrackerAdapter(BaseAdapter):
    """
    Mock Connector for Cohort Tracker (Operations Central Sheet / DB)
    """
    def __init__(self):
        self._tracker_entries: Dict[str, CohortTrackerEntry] = {}

    @property
    def system_name(self) -> str:
        return "Cohort_Tracker"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        entry = self._tracker_entries.get(candidate_id)
        return entry.dict() if entry else None

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._tracker_entries.get(candidate_id)
        start_date = data.get("start_date", "2026-09-01")
        cohort_id = f"COHORT-{start_date[:7]}"  # YYYY-MM
        
        if existing:
            updated = existing.dict()
            updated.update(data)
            updated["last_reconciled"] = datetime.utcnow()
            record = CohortTrackerEntry(**updated)
        else:
            payload = {
                "cohort_id": data.get("cohort_id", cohort_id),
                "candidate_id": candidate_id,
                "full_name": data.get("full_name", data.get("candidate_name", "Hire Name")),
                "department": data.get("department", "Engineering"),
                "start_date": start_date,
                "workday_status": data.get("workday_status", "Synced"),
                "okta_status": data.get("okta_status", "Pending"),
                "hardware_status": data.get("hardware_status", "Ordered"),
                "overall_onboarding_status": data.get("overall_onboarding_status", "On Track"),
                "last_reconciled": datetime.utcnow()
            }
            record = CohortTrackerEntry(**payload)

        self._tracker_entries[candidate_id] = record
        return record.dict()

    def delete_record(self, candidate_id: str) -> bool:
        if candidate_id in self._tracker_entries:
            del self._tracker_entries[candidate_id]
            return True
        return False

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return {cid: rec.dict() for cid, rec in self._tracker_entries.items()}
