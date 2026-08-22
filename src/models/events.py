from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class EventType:
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    START_DATE_CHANGED = "START_DATE_CHANGED"
    NAME_CHANGED = "NAME_CHANGED"
    ADDRESS_CHANGED = "ADDRESS_CHANGED"
    OFF_CYCLE_HIRE_CREATED = "OFF_CYCLE_HIRE_CREATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SLA_BREACH_WARNING = "SLA_BREACH_WARNING"
    RECONCILIATION_COMPLETED = "RECONCILIATION_COMPLETED"

class ChangeDelta(BaseModel):
    field_name: str
    old_value: Any
    new_value: Any
    target_system: str

class OnboardingEvent(BaseModel):
    event_id: str
    event_type: str
    candidate_id: str
    source_system: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: Dict[str, Any]
    idempotency_key: str

class AuditLogEntry(BaseModel):
    log_id: str
    timestamp: str
    event_type: str
    candidate_id: str
    idempotency_key: str
    source_system: str
    affected_systems: List[str]
    changes: List[Dict[str, Any]]
    status: str  # SUCCESS, PARTIAL_FAILURE, BLOCKED, SLA_ALERT
    hash: str  # Cryptographic hash chaining for audit integrity
    details: Optional[str] = None
