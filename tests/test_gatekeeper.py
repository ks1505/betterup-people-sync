import pytest
from datetime import date
from src.models.candidate import CandidateProfile, Address
from src.mock_adapters import ExpoITAdapter, SlackAdapter, CohortTrackerAdapter
from src.core.audit_logger import AuditLogger
from src.core.gatekeeper import SLAGatekeeper

def test_sla_hardware_breach_detected(tmp_path):
    expoit = ExpoITAdapter()
    slack = SlackAdapter()
    tracker = CohortTrackerAdapter()
    audit = AuditLogger(log_filepath=str(tmp_path / "audit.json"))

    gatekeeper = SLAGatekeeper(expoit=expoit, slack=slack, tracker=tracker, audit_logger=audit)

    # Hire starting in 4 days (2026-08-26 relative to ref date 2026-08-22), but hardware NOT ordered
    cand = CandidateProfile(
        candidate_id="CAND-SLA-1",
        first_name="David",
        last_name="Kim",
        personal_email="david.kim@gmail.com",
        job_title="Security Architect",
        department="Security",
        manager_email="ciso@betterup.co",
        hiring_manager_name="CISO",
        location="Remote",
        address=Address(street="100 Main St", city="San Jose", state="CA", zip_code="95113"),
        start_date=date(2026, 8, 26)
    )

    ref_date = date(2026, 8, 22)  # T-4 days
    breaches = gatekeeper.scan_candidate_slas(cand, current_date=ref_date)

    assert len(breaches) > 0
    hw_breach = next(b for b in breaches if b["gate"] == "IT_HARDWARE_ORDER")
    assert hw_breach["severity"] == "HIGH"
    assert hw_breach["days_until_start"] == 4

    # Verify Slack notification sent
    sent_msgs = slack.list_all_notifications()
    assert len(sent_msgs) > 0
    assert "SLA GATEWAY ALERT" in sent_msgs[0]["message"]
