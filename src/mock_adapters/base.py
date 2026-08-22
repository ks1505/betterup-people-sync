from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAdapter(ABC):
    """
    Abstract Base Class for System Connectors (Ashby, Workday, Okta, ExpoIT, Slack, Tracker)
    """
    @property
    @abstractmethod
    def system_name(self) -> str:
        pass

    @abstractmethod
    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def delete_record(self, candidate_id: str) -> bool:
        pass
