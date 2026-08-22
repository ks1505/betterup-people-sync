from typing import Dict, Any, Optional, List
from datetime import datetime
from src.mock_adapters.base import BaseAdapter
from src.models.system_records import SlackNotificationRecord

class SlackAdapter(BaseAdapter):
    """
    Mock Connector for Slack Messaging & Escalation Alerts
    """
    def __init__(self):
        self._sent_messages: List[SlackNotificationRecord] = []

    @property
    def system_name(self) -> str:
        return "Slack_Comms"

    def get_record(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        for msg in reversed(self._sent_messages):
            if candidate_id in msg.message:
                return msg.dict()
        return None

    def send_notification(self, channel: str, recipient_email: str, message: str) -> Dict[str, Any]:
        rec = SlackNotificationRecord(
            notification_id=f"SLACK-MSG-{len(self._sent_messages) + 1}",
            channel=channel,
            recipient_email=recipient_email,
            message=message,
            sent_at=datetime.utcnow()
        )
        self._sent_messages.append(rec)
        return rec.dict()

    def create_or_update_record(self, candidate_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.send_notification(
            channel=data.get("channel", "#people-ops-alerts"),
            recipient_email=data.get("recipient_email", "manager@betterup.co"),
            message=data.get("message", f"Onboarding update for Candidate {candidate_id}")
        )

    def delete_record(self, candidate_id: str) -> bool:
        return True

    def list_all_notifications(self) -> List[Dict[str, Any]]:
        return [m.dict() for m in self._sent_messages]
