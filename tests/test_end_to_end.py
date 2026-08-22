import pytest
from datetime import date
from src.models.candidate import CandidateProfile, Address
from src.mock_adapters import (
    AshbyAdapter, WorkdayAdapter, OktaLumosAdapter,
    ExpoITAdapter, SlackAdapter, CohortTrackerAdapter
)
from src.core.audit_logger import AuditLogger
from src.core.reconciler import ReconciliationEngine
from src.core.gatekeeper import SLAGatekeeper
from src.ai.claude_client import ClaudeAIResolver

def test_full_onboarding_lifecycle(tmp_path):
    ashby = AshbyAdapter()
    workday = WorkdayAdapter()
    okta = OktaLumosAdapter()
    expoit = ExpoITAdapter()
    slack = SlackAdapter()
    tracker = CohortTrackerAdapter()
    audit = AuditLogger(log_filepath=str(tmp_path / "e2e_audit.json"))

    reconciler = ReconciliationEngine(
        ashby=ashby, workday=workday, okta=okta,
        expoit=expoit, slack=slack, tracker=tracker,
        audit_logger=audit
    )
    gatekeeper = SLAGatekeeper(expoit=expoit, slack=slack, tracker=tracker, audit_logger=audit)
    claude = ClaudeAIResolver()

    # Step 1: Ashby Offer Accepted Event
    cand = CandidateProfile(
        candidate_id="CAND-E2E-100",
        first_name="Maya",
        last_name="Lin",
        personal_email="maya.lin@gmail.com",
        job_title="Lead Product Designer",
        department="Product Design",
        manager_email="vp.design@betterup.co",
        hiring_manager_name="Sarah Jenkins",
        location="San Francisco, CA",
        address=Address(street="456 Market St", city="San Francisco", state="CA", zip_code="94105"),
        start_date=date(2026, 9, 1)
    )

    res1 = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    assert res1["status"] == "RECONCILED"
    wd_emp_id = res1["workday_employee_id"]

    # Step 2: Verify all downstream systems created records
    assert workday.get_record("CAND-E2E-100") is not None
    assert okta.get_record("CAND-E2E-100") is not None
    assert expoit.get_record("CAND-E2E-100") is not None
    assert tracker.get_record("CAND-E2E-100") is not None

    # Step 3: Post-offer Start Date Change (Delayed by 2 weeks)
    cand.start_date = date(2026, 9, 15)
    res2 = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="START_DATE_CHANGED")
    assert res2["status"] == "RECONCILED"

    # Verify start date updated in Workday & ExpoIT
    assert workday.get_record("CAND-E2E-100")["hire_date"] == "2026-09-15"
    assert expoit.get_record("CAND-E2E-100")["target_start_date"] == "2026-09-15"

    # Step 4: Verify Cryptographic Audit Log Integrity
    assert audit.verify_integrity() is True
    assert len(audit.list_all_entries()) >= 2
