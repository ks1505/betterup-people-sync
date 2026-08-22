import json
from typing import Dict, Any, List
from mcp.server import Server
from src.models.candidate import CandidateProfile, Address
from src.core.validator import PreFlightValidator
from src.core.audit_logger import AuditLogger
from src.mock_adapters import (
    AshbyAdapter, WorkdayAdapter, OktaLumosAdapter,
    ExpoITAdapter, SlackAdapter, CohortTrackerAdapter
)
from src.core.reconciler import ReconciliationEngine
from src.core.gatekeeper import SLAGatekeeper
from src.ai.claude_client import ClaudeAIResolver

# Initialize MCP Server instance
mcp_server = Server("BetterUp-People-Sync-MCP")

# Global Shared Adapter Instances
ashby_adapter = AshbyAdapter()
workday_adapter = WorkdayAdapter()
okta_adapter = OktaLumosAdapter()
expoit_adapter = ExpoITAdapter()
slack_adapter = SlackAdapter()
tracker_adapter = CohortTrackerAdapter()
audit_logger = AuditLogger()

reconciler = ReconciliationEngine(
    ashby=ashby_adapter,
    workday=workday_adapter,
    okta=okta_adapter,
    expoit=expoit_adapter,
    slack=slack_adapter,
    tracker=tracker_adapter,
    audit_logger=audit_logger
)

gatekeeper = SLAGatekeeper(
    expoit=expoit_adapter,
    slack=slack_adapter,
    tracker=tracker_adapter,
    audit_logger=audit_logger
)

claude_resolver = ClaudeAIResolver()

# MCP Tool Implementations
def validate_onboarding_data(candidate_json: str) -> str:
    """
    MCP Tool: Performs pre-flight data validation on candidate onboarding details.
    """
    try:
        data = json.loads(candidate_json)
        candidate = CandidateProfile(**data)
        res = PreFlightValidator.validate_candidate(candidate)
        return json.dumps(res.dict(), indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "is_valid": False})

def reconcile_candidate_change(candidate_json: str, source_system: str = "Ashby_ATS", event_type: str = "START_DATE_CHANGED") -> str:
    """
    MCP Tool: Idempotently reconciles a candidate profile across all 6 downstream systems.
    """
    try:
        data = json.loads(candidate_json)
        candidate = CandidateProfile(**data)
        res = reconciler.reconcile_hire(candidate, source_system, event_type)
        return json.dumps(res, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "status": "ERROR"})

def get_sla_exceptions() -> str:
    """
    MCP Tool: Scans all candidate records for pending onboarding SLA deadline breaches.
    """
    try:
        all_candidates = ashby_adapter.list_all()
        all_breaches = []
        for cid, record in all_candidates.items():
            addr_data = {
                "street": record.get("street_address", "123 Main St"),
                "city": record.get("city", "SF"),
                "state": record.get("state", "CA"),
                "zip_code": record.get("zip_code", "94105")
            }
            cand = CandidateProfile(
                candidate_id=cid,
                first_name=record.get("candidate_first_name", "First"),
                last_name=record.get("candidate_last_name", "Last"),
                personal_email=record.get("email", "hire@email.com"),
                job_title=record.get("job_title", "Engineer"),
                department=record.get("department", "Engineering"),
                manager_email=record.get("manager_email", "manager@betterup.co"),
                hiring_manager_name=record.get("hiring_manager_name", "Hiring Mgr"),
                location="Remote",
                address=Address(**addr_data),
                start_date=record.get("start_date", "2026-09-01")
            )
            breaches = gatekeeper.scan_candidate_slas(cand)
            all_breaches.extend(breaches)
        return json.dumps({"total_exceptions": len(all_breaches), "exceptions": all_breaches}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def ai_resolve_record_discrepancy(ashby_record_json: str, workday_record_json: str) -> str:
    """
    MCP Tool: Leverages Claude AI to compare conflicting Ashby & Workday records.
    """
    try:
        rec_a = json.loads(ashby_record_json)
        rec_b = json.loads(workday_record_json)
        result = claude_resolver.resolve_entity_ambiguity(rec_a, rec_b)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_audit_trail_integrity() -> str:
    """
    MCP Tool: Checks cryptographic SHA-256 hash chain integrity of the audit ledger.
    """
    is_valid = audit_logger.verify_integrity()
    entries = audit_logger.list_all_entries()
    return json.dumps({
        "ledger_integrity_valid": is_valid,
        "total_audit_records": len(entries),
        "recent_entries": entries[-5:]
    }, indent=2)

MCP_TOOLS = {
    "validate_onboarding_data": validate_onboarding_data,
    "reconcile_candidate_change": reconcile_candidate_change,
    "get_sla_exceptions": get_sla_exceptions,
    "ai_resolve_record_discrepancy": ai_resolve_record_discrepancy,
    "get_audit_trail_integrity": get_audit_trail_integrity
}
