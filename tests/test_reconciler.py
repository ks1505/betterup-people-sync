import pytest
from datetime import date
from src.models.candidate import CandidateProfile, Address
from src.mock_adapters import (
    AshbyAdapter, WorkdayAdapter, OktaLumosAdapter,
    ExpoITAdapter, SlackAdapter, CohortTrackerAdapter
)
from src.core.audit_logger import AuditLogger
from src.core.reconciler import ReconciliationEngine

@pytest.fixture
def test_setup(tmp_path):
    ashby = AshbyAdapter()
    workday = WorkdayAdapter()
    okta = OktaLumosAdapter()
    expoit = ExpoITAdapter()
    slack = SlackAdapter()
    tracker = CohortTrackerAdapter()
    audit_log_path = str(tmp_path / "test_audit.json")
    audit = AuditLogger(log_filepath=audit_log_path)

    reconciler = ReconciliationEngine(
        ashby=ashby, workday=workday, okta=okta,
        expoit=expoit, slack=slack, tracker=tracker,
        audit_logger=audit
    )
    return {
        "ashby": ashby, "workday": workday, "okta": okta,
        "expoit": expoit, "slack": slack, "tracker": tracker,
        "audit": audit, "reconciler": reconciler
    }

def test_reconcile_new_hire(test_setup):
    reconciler = test_setup["reconciler"]
    cand = CandidateProfile(
        candidate_id="CAND-TEST-1",
        first_name="Jane",
        last_name="Doe",
        personal_email="jane.doe@gmail.com",
        job_title="Engineering Manager",
        department="Engineering",
        manager_email="cto@betterup.co",
        hiring_manager_name="Alex CTO",
        location="San Francisco, CA",
        address=Address(street="100 Market St", city="San Francisco", state="CA", zip_code="94105"),
        start_date=date(2026, 9, 15)
    )

    res = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    assert res["status"] == "RECONCILED"
    assert "Workday_HRIS" in res["affected_systems"]
    assert "Okta_Lumos" in res["affected_systems"]
    assert "ExpoIT_Hardware" in res["affected_systems"]
    assert "Cohort_Tracker" in res["affected_systems"]

    # Verify Workday record was created with Employee ID
    wd_rec = test_setup["workday"].get_record("CAND-TEST-1")
    assert wd_rec is not None
    assert wd_rec["legal_first_name"] == "Jane"

def test_idempotency_duplicate_event_blocked(test_setup):
    reconciler = test_setup["reconciler"]
    cand = CandidateProfile(
        candidate_id="CAND-TEST-2",
        first_name="Bob",
        last_name="Smith",
        personal_email="bob.smith@gmail.com",
        job_title="Account Executive",
        department="Sales",
        manager_email="vp.sales@betterup.co",
        hiring_manager_name="Sales VP",
        location="New York, NY",
        address=Address(street="500 5th Ave", city="New York", state="NY", zip_code="10036"),
        start_date=date(2026, 9, 20)
    )

    # First Run
    res1 = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    assert res1["status"] == "RECONCILED"

    # Second Run with identical payload
    res2 = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    assert res2["status"] == "SKIPPED_DUPLICATE"
    assert "Idempotency gate blocked re-execution" in res2["message"]

def test_post_offer_start_date_shift_propagation(test_setup):
    reconciler = test_setup["reconciler"]
    cand = CandidateProfile(
        candidate_id="CAND-TEST-3",
        first_name="Alice",
        last_name="Wong",
        personal_email="alice.wong@gmail.com",
        job_title="Staff Designer",
        department="Design",
        manager_email="design.dir@betterup.co",
        hiring_manager_name="Design Lead",
        location="Remote",
        address=Address(street="123 Pine St", city="Seattle", state="WA", zip_code="98101"),
        start_date=date(2026, 9, 1)
    )

    # Initial Sync
    reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")

    # Start date shifts to 2026-09-15
    cand.start_date = date(2026, 9, 15)
    res = reconciler.reconcile_hire(cand, source_system="Ashby_ATS", event_type="START_DATE_CHANGED")

    assert res["status"] == "RECONCILED"
    
    # Check Workday updated hire date
    wd_rec = test_setup["workday"].get_record("CAND-TEST-3")
    assert wd_rec["hire_date"] == "2026-09-15"

    # Check ExpoIT target start date updated
    exp_rec = test_setup["expoit"].get_record("CAND-TEST-3")
    assert exp_rec["target_start_date"] == "2026-09-15"
