import json
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.models.events import AuditLogEntry

class AuditLogger:
    """
    Append-only Cryptographic Audit Ledger for cross-system sync tracking.
    Uses SHA-256 hash chaining (blockchain-style ledger) for tamper-evident history.
    """
    def __init__(self, log_filepath: str = "audit_ledger.json"):
        self.log_filepath = log_filepath
        self._entries: List[AuditLogEntry] = []
        self._last_hash = "GENESIS_HASH_00000000000000000000000000000000000000000000000000000000"
        self._load_existing_ledger()

    def _load_existing_ledger(self):
        if os.path.exists(self.log_filepath):
            try:
                with open(self.log_filepath, "r") as f:
                    data = json.load(f)
                    for item in data:
                        entry = AuditLogEntry(**item)
                        self._entries.append(entry)
                        self._last_hash = entry.hash
            except Exception:
                self._entries = []

    def _calculate_hash(self, prev_hash: str, timestamp: str, event_type: str, candidate_id: str, changes: str) -> str:
        raw_str = f"{prev_hash}|{timestamp}|{event_type}|{candidate_id}|{changes}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def log_event(
        self,
        event_type: str,
        candidate_id: str,
        idempotency_key: str,
        source_system: str,
        affected_systems: List[str],
        changes: List[Dict[str, Any]],
        status: str = "SUCCESS",
        details: Optional[str] = None
    ) -> AuditLogEntry:
        timestamp_str = datetime.utcnow().isoformat()
        changes_json = json.dumps(changes, sort_keys=True)
        new_hash = self._calculate_hash(self._last_hash, timestamp_str, event_type, candidate_id, changes_json)

        entry = AuditLogEntry(
            log_id=f"AUDIT-{len(self._entries) + 1:06d}",
            timestamp=timestamp_str,
            event_type=event_type,
            candidate_id=candidate_id,
            idempotency_key=idempotency_key,
            source_system=source_system,
            affected_systems=affected_systems,
            changes=changes,
            status=status,
            hash=new_hash,
            details=details
        )

        self._entries.append(entry)
        self._last_hash = new_hash
        self._save_ledger()
        return entry

    def _save_ledger(self):
        with open(self.log_filepath, "w") as f:
            json.dump([e.dict() for e in self._entries], f, indent=2)

    def get_history_for_candidate(self, candidate_id: str) -> List[Dict[str, Any]]:
        return [e.dict() for e in self._entries if e.candidate_id == candidate_id]

    def list_all_logs(self) -> List[Dict[str, Any]]:
        return [e.dict() for e in self._entries]

    def list_all_entries(self) -> List[Dict[str, Any]]:
        return [e.dict() for e in self._entries]

    def verify_integrity(self) -> bool:
        """
        Verifies cryptographic hash chain integrity of the ledger.
        """
        prev = "GENESIS_HASH_00000000000000000000000000000000000000000000000000000000"
        for entry in self._entries:
            changes_json = json.dumps(entry.changes, sort_keys=True)
            expected_hash = self._calculate_hash(prev, entry.timestamp, entry.event_type, entry.candidate_id, changes_json)
            if entry.hash != expected_hash:
                return False
            prev = entry.hash
        return True
