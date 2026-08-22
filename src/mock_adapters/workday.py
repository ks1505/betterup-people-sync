from typing import Dict, Any, Optional
from datetime import datetime
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import WorkdayWorkerRecord

class WorkdayAdapter(BaseAdapter):
    """
    Mock Connector for Workday HRIS (System of Record)
    """
    def __init__(self):
        self._workers: Dict[str, WorkdayWorkerRecord] = {}

    @property
    def system_name(self) -> str:
        return "Workday_HRIS"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        # Lookup by candidate_id
        for emp in self._workers.values():
            if emp.candidate_id == candidate_id:
                return emp.dict()
        return None

    def get_by_employee_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        emp = self._workers.get(employee_id)
        return emp.dict() if emp else None

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing_emp_id = None
        for emp_id, emp in self._workers.items():
            if emp.candidate_id == candidate_id:
                existing_emp_id = emp_id
                break

        if existing_emp_id:
            updated_data = self._workers[existing_emp_id].dict()
            updated_data.update(data)
            updated_data["last_synced"] = datetime.utcnow()
            record = WorkdayWorkerRecord(**updated_data)
            self._workers[existing_emp_id] = record
        else:
            emp_id = data.get("employee_id") or f"WD-{10000 + len(self._workers) + 1}"
            data["employee_id"] = emp_id
            data["candidate_id"] = candidate_id
            data["last_synced"] = datetime.utcnow()
            record = WorkdayWorkerRecord(**data)
            self._workers[emp_id] = record

        return record.dict()

    def delete_record(self, candidate_id: str) -> bool:
        to_delete = [emp_id for emp_id, emp in self._workers.items() if emp.candidate_id == candidate_id]
        for emp_id in to_delete:
            del self._workers[emp_id]
        return len(to_delete) > 0

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return {emp_id: rec.dict() for emp_id, rec in self._workers.items()}
