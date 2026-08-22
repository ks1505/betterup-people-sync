import os
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.models.candidate import CandidateProfile, Address
from src.mock_adapters import (
    AshbyAdapter, WorkdayAdapter, OktaLumosAdapter,
    ExpoITAdapter, SlackAdapter, CohortTrackerAdapter
)
from src.core.audit_logger import AuditLogger
from src.core.validator import PreFlightValidator
from src.core.reconciler import ReconciliationEngine
from src.core.gatekeeper import SLAGatekeeper
from src.ai.claude_client import ClaudeAIResolver

app = FastAPI(
    title="BetterUp People Tech Onboarding Sync Engine",
    description="Idempotent Change Propagation, Pre-Flight Validation, and SLA Exception Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Core Shared System Services
ashby_adapter = AshbyAdapter()
workday_adapter = WorkdayAdapter()
okta_adapter = OktaLumosAdapter()
expoit_adapter = ExpoITAdapter()
slack_adapter = SlackAdapter()
tracker_adapter = CohortTrackerAdapter()
audit_logger = AuditLogger(log_filepath="audit_ledger.json")

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

# Populate Mock Initial Seed Data
def seed_mock_data():
    sample_hires = [
        {
            "candidate_id": "CAND-1001",
            "candidate_first_name": "Maya",
            "candidate_last_name": "Lin",
            "email": "maya.lin@gmail.com",
            "job_title": "Senior Product Designer",
            "department": "Design",
            "start_date": "2026-09-01",
            "street_address": "456 Market St, Apt 12B",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94105",
            "manager_email": "sarah.design@betterup.co",
            "hiring_manager_name": "Sarah Jenkins",
            "offer_status": "Signed"
        },
        {
            "candidate_id": "CAND-1002",
            "candidate_first_name": "Marcus",
            "candidate_last_name": "Vance",
            "email": "marcus.vance@techmail.com",
            "job_title": "Staff AI Engineer",
            "department": "Engineering",
            "start_date": "2026-08-28",  # T-6 days from today
            "street_address": "789 Mission St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94103",
            "manager_email": "alex.eng@betterup.co",
            "hiring_manager_name": "Alex Rivera",
            "offer_status": "Signed"
        }
    ]
    for h in sample_hires:
        ashby_adapter.create_or_update_record(h["candidate_id"], h)
        # Reconcile seed hire
        cand = CandidateProfile(
            candidate_id=h["candidate_id"],
            first_name=h["candidate_first_name"],
            last_name=h["candidate_last_name"],
            personal_email=h["email"],
            job_title=h["job_title"],
            department=h["department"],
            manager_email=h["manager_email"],
            hiring_manager_name=h["hiring_manager_name"],
            location="San Francisco, CA",
            address=Address(
                street=h["street_address"],
                city=h["city"],
                state=h["state"],
                zip_code=h["zip_code"]
            ),
            start_date=h["start_date"]
        )
        reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")

seed_mock_data()

# API Endpoints
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "system": "BetterUp People Tech Sync Engine",
        "audit_integrity": audit_logger.verify_integrity()
    }

@app.get("/api/v1/candidates")
def get_candidates():
    return {
        "ashby": ashby_adapter.list_all(),
        "workday": workday_adapter.list_all(),
        "cohort_tracker": tracker_adapter.list_all()
    }

@app.post("/api/v1/reconcile")
def reconcile_candidate(candidate: CandidateProfile, source_system: str = "Ashby_ATS", event_type: str = "MANUAL_TRIGGER"):
    res = reconciler.reconcile_hire(candidate, source_system=source_system, event_type=event_type)
    return res

@app.post("/api/v1/validate")
def validate_candidate(candidate: CandidateProfile):
    res = PreFlightValidator.validate_candidate(candidate)
    return res.dict()

@app.get("/api/v1/slas/exceptions")
def get_sla_exceptions(simulated_date: Optional[str] = None):
    ref_date = date.fromisoformat(simulated_date) if simulated_date else date.today()
    all_candidates = ashby_adapter.list_all()
    all_breaches = []
    
    for cid, record in all_candidates.items():
        cand = CandidateProfile(
            candidate_id=cid,
            first_name=record.get("candidate_first_name", "First"),
            last_name=record.get("candidate_last_name", "Last"),
            personal_email=record.get("email", "email@test.com"),
            job_title=record.get("job_title", "Role"),
            department=record.get("department", "Engineering"),
            manager_email=record.get("manager_email", "manager@betterup.co"),
            hiring_manager_name=record.get("hiring_manager_name", "Manager"),
            location="Remote",
            address=Address(
                street=record.get("street_address", "123 Main St"),
                city=record.get("city", "SF"),
                state=record.get("state", "CA"),
                zip_code=record.get("zip_code", "94105")
            ),
            start_date=record.get("start_date", "2026-09-01")
        )
        # Check background check state if set
        if record.get("background_check_status"):
            cand.background_check_status = record.get("background_check_status")

        breaches = gatekeeper.scan_candidate_slas(cand, current_date=ref_date)
        all_breaches.extend(breaches)

    return {
        "simulated_date": ref_date.isoformat(),
        "total_exceptions": len(all_breaches),
        "exceptions": all_breaches
    }

class SimulationRequest(BaseModel):
    scenario: str  # 'CHANGE_START_DATE', 'INJECT_BAD_ADDRESS', 'CREATE_OFF_CYCLE_HIRE', 'FAST_FORWARD_TIME'
    candidate_id: Optional[str] = "CAND-1001"
    new_start_date: Optional[str] = "2026-09-15"
    bad_zip: Optional[str] = "INVALID_ZIP_99"

@app.post("/api/v1/simulate")
def run_simulation(req: SimulationRequest):
    if req.scenario == "CHANGE_START_DATE":
        record = ashby_adapter.get_record(req.candidate_id)
        if not record:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        old_start = record.get("start_date")
        record["start_date"] = req.new_start_date
        ashby_adapter.create_or_update_record(req.candidate_id, record)
        
        # Trigger reconciliation
        cand = CandidateProfile(
            candidate_id=req.candidate_id,
            first_name=record.get("candidate_first_name"),
            last_name=record.get("candidate_last_name"),
            personal_email=record.get("email"),
            job_title=record.get("job_title"),
            department=record.get("department"),
            manager_email=record.get("manager_email"),
            hiring_manager_name=record.get("hiring_manager_name"),
            location="San Francisco, CA",
            address=Address(
                street=record.get("street_address"),
                city=record.get("city"),
                state=record.get("state"),
                zip_code=record.get("zip_code")
            ),
            start_date=req.new_start_date
        )
        res = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="START_DATE_CHANGED")
        return {
            "scenario": "CHANGE_START_DATE",
            "candidate_id": req.candidate_id,
            "old_start_date": old_start,
            "new_start_date": req.new_start_date,
            "reconciliation_result": res
        }

    elif req.scenario == "INJECT_BAD_ADDRESS":
        cid = "CAND-BAD-ADDR"
        bad_cand = CandidateProfile(
            candidate_id=cid,
            first_name="Jordan",
            last_name="Smyth",
            personal_email="jordan.smyth@test.com",
            job_title="Data Analyst",
            department="Analytics",
            manager_email="analytics.mgr@betterup.co",
            hiring_manager_name="Elena Rostova",
            location="Remote",
            address=Address(
                street="123",  # Street address too short
                city="Chicago",
                state="IL",
                zip_code=req.bad_zip  # Invalid ZIP pattern
            ),
            start_date="2026-09-10"
        )
        res = reconciler.reconcile_hire(bad_cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
        return {
            "scenario": "INJECT_BAD_ADDRESS",
            "candidate_id": cid,
            "reconciliation_result": res
        }

    elif req.scenario == "CREATE_OFF_CYCLE_HIRE":
        cid = f"WD-OFFCYCLE-{100 + len(workday_adapter.list_all())}"
        off_cycle = CandidateProfile(
            candidate_id=cid,
            first_name="Eleanor",
            last_name="Vance",
            personal_email="eleanor.exec@personal.com",
            job_title="VP of People Ops",
            department="Executive",
            manager_email="ceo@betterup.co",
            hiring_manager_name="Chief Executive",
            location="Austin, TX",
            address=Address(
                street="100 Executive Way",
                city="Austin",
                state="TX",
                zip_code="78701"
            ),
            start_date="2026-09-08"
        )
        res = reconciler.reconcile_hire(off_cycle, source_system="Workday_Direct", event_type="OFF_CYCLE_HIRE_CREATED")
        return {
            "scenario": "CREATE_OFF_CYCLE_HIRE",
            "candidate_id": cid,
            "reconciliation_result": res
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

@app.get("/api/v1/audit/ledger")
def get_audit_ledger():
    return {
        "integrity_valid": audit_logger.verify_integrity(),
        "total_logs": len(audit_logger.list_all_entries()),
        "entries": audit_logger.list_all_entries()
    }

@app.get("/api/v1/systems/state")
def get_all_systems_state():
    return {
        "ashby": ashby_adapter.list_all(),
        "workday": workday_adapter.list_all(),
        "okta": okta_adapter.list_all(),
        "expoit": expoit_adapter.list_all(),
        "slack": slack_adapter.list_all_notifications(),
        "cohort_tracker": tracker_adapter.list_all()
    }

# Mount static files UI if directory exists
web_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web")
if os.path.exists(web_dir):
    app.mount("/dashboard", StaticFiles(directory=web_dir, html=True), name="web")
