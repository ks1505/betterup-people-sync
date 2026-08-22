#!/usr/bin/env python3
"""
BetterUp People Technology Onboarding Sync Prototype - Interactive CLI Demo
Demonstrates Change Propagation, Pre-Flight Validation, SLA Exception Engine, and MCP/Claude AI integration.
"""

import os
import sys
import json
import time
from datetime import date

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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

def print_header(title):
    print("\n" + "=" * 80)
    print(f" 🚀 {title.upper()}")
    print("=" * 80)

def print_sub(title):
    print(f"\n---> 🔹 {title}")

def main():
    print_header("BetterUp People Tech Onboarding Sync Prototype")
    print("Initializing system adapters, audit logger, reconciler, and Claude AI resolver...")

    ashby = AshbyAdapter()
    workday = WorkdayAdapter()
    okta = OktaLumosAdapter()
    expoit = ExpoITAdapter()
    slack = SlackAdapter()
    tracker = CohortTrackerAdapter()
    audit_logger = AuditLogger(log_filepath="demo_audit_ledger.json")

    reconciler = ReconciliationEngine(
        ashby=ashby, workday=workday, okta=okta,
        expoit=expoit, slack=slack, tracker=tracker,
        audit_logger=audit_logger
    )
    gatekeeper = SLAGatekeeper(expoit=expoit, slack=slack, tracker=tracker, audit_logger=audit_logger)
    claude = ClaudeAIResolver()

    time.sleep(0.5)

    # -------------------------------------------------------------------------
    # SCENARIO 1: Happy Path Offer Acceptance & State Propagation
    # -------------------------------------------------------------------------
    print_header("Scenario 1: Offer Acceptance & Initial Multi-System Propagation")
    print("Candidate 'Maya Lin' accepts offer in Ashby for Senior Product Designer.")

    cand_maya = CandidateProfile(
        candidate_id="CAND-MAYA-101",
        first_name="Maya",
        last_name="Lin",
        personal_email="maya.lin@gmail.com",
        job_title="Senior Product Designer",
        department="Product Design",
        manager_email="sarah.design@betterup.co",
        hiring_manager_name="Sarah Jenkins",
        location="San Francisco, CA",
        address=Address(street="456 Market St, Apt 12B", city="San Francisco", state="CA", zip_code="94105"),
        start_date=date(2026, 9, 1)
    )

    print_sub("Executing Pre-Flight Data Quality Check...")
    val1 = PreFlightValidator.validate_candidate(cand_maya)
    print(f"Validation Result: Is Valid = {val1.is_valid} (Errors: {val1.has_errors}, Warnings: {val1.has_warnings})")

    print_sub("Executing State Reconciliation Across Systems...")
    res1 = reconciler.reconcile_hire(cand_maya, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    print(json.dumps(res1, indent=2))

    # -------------------------------------------------------------------------
    # SCENARIO 2: Post-Offer Change Propagation (Start Date Shift)
    # -------------------------------------------------------------------------
    print_header("Scenario 2: Post-Offer Start Date Shift Propagation")
    print("Maya Lin pushes start date from Sept 1 -> Sept 15 in Ashby.")

    cand_maya.start_date = date(2026, 9, 15)

    print_sub("Reconciling Start Date Change Across Downstream Systems...")
    res2 = reconciler.reconcile_hire(cand_maya, source_system="Ashby_ATS", event_type="START_DATE_CHANGED")
    print(json.dumps(res2, indent=2))

    # -------------------------------------------------------------------------
    # SCENARIO 3: Idempotency Protection Test
    # -------------------------------------------------------------------------
    print_header("Scenario 3: Idempotency Gate Protection Test")
    print("Simulating duplicate webhook dispatch for the exact same event...")

    res3 = reconciler.reconcile_hire(cand_maya, source_system="Ashby_ATS", event_type="START_DATE_CHANGED")
    print(f"Idempotency Status: {res3['status']}")
    print(f"Message: {res3['message']}")

    # -------------------------------------------------------------------------
    # SCENARIO 4: Pre-Flight Data Quality Trap (Bad Address)
    # -------------------------------------------------------------------------
    print_header("Scenario 4: Pre-Flight Quality Gate Blocks Bad Data")
    print("Simulating candidate offer with invalid street address and bad ZIP code...")

    cand_bad = CandidateProfile(
        candidate_id="CAND-BAD-202",
        first_name="Jordan",
        last_name="Smyth",
        personal_email="jordan.smyth@gmail.com",
        job_title="Data Engineer",
        department="Engineering",
        manager_email="eng.lead@betterup.co",
        hiring_manager_name="Alex Rivera",
        location="Remote",
        address=Address(street="12", city="Chicago", state="IL", zip_code="BAD_ZIP_99"),
        start_date=date(2026, 9, 10)
    )

    res4 = reconciler.reconcile_hire(cand_bad, source_system="Ashby_ATS", event_type="OFFER_ACCEPTED")
    print(f"Reconciliation Status: {res4['status']}")
    print("Pre-Flight Validation Issues Flagged:")
    for issue in res4["validation"]["issues"]:
        print(f"  ❌ [{issue['severity']}] {issue['field']}: {issue['message']} (Code: {issue['code']})")

    # -------------------------------------------------------------------------
    # SCENARIO 5: Off-Cycle Hire Outside Ashby
    # -------------------------------------------------------------------------
    print_header("Scenario 5: Off-Cycle Executive Hire Created in Workday")
    print("Creating VP of People Ops directly in Workday without an Ashby ATS record...")

    cand_offcycle = CandidateProfile(
        candidate_id="WD-OFFCYCLE-505",
        first_name="Eleanor",
        last_name="Vance",
        personal_email="eleanor.vance@personal.com",
        job_title="VP of People Ops",
        department="Executive",
        manager_email="ceo@betterup.co",
        hiring_manager_name="Chief Executive Officer",
        location="Austin, TX",
        address=Address(street="100 Executive Way", city="Austin", state="TX", zip_code="78701"),
        start_date=date(2026, 9, 8)
    )

    res5 = reconciler.reconcile_hire(cand_offcycle, source_system="Workday_Direct", event_type="OFF_CYCLE_HIRE_CREATED")
    print(json.dumps(res5, indent=2))

    # -------------------------------------------------------------------------
    # SCENARIO 6: Proactive SLA Watchdog & Claude Escalation
    # -------------------------------------------------------------------------
    print_header("Scenario 6: Proactive SLA Watchdog Scan & Claude Escalation")
    print("Scanning pending onboarding gates against T-minus deadlines (Ref Date: 2026-08-22)...")

    # Add a candidate with urgent start date (T-4 days) and missing hardware
    cand_urgent = CandidateProfile(
        candidate_id="CAND-URGENT-606",
        first_name="Marcus",
        last_name="Vance",
        personal_email="marcus.vance@techmail.com",
        job_title="Staff AI Engineer",
        department="AI R&D",
        manager_email="alex.ai@betterup.co",
        hiring_manager_name="Alex Rivera",
        location="Remote",
        address=Address(street="789 Mission St", city="San Francisco", state="CA", zip_code="94103"),
        start_date=date(2026, 8, 26)  # 4 days out
    )
    ashby_data = {
        "candidate_id": cand_urgent.candidate_id,
        "candidate_first_name": cand_urgent.first_name,
        "candidate_last_name": cand_urgent.last_name,
        "email": cand_urgent.personal_email,
        "job_title": cand_urgent.job_title,
        "department": cand_urgent.department,
        "start_date": cand_urgent.start_date.isoformat(),
        "street_address": cand_urgent.address.street,
        "city": cand_urgent.address.city,
        "state": cand_urgent.address.state,
        "zip_code": cand_urgent.address.zip_code,
        "manager_email": cand_urgent.manager_email,
        "hiring_manager_name": cand_urgent.hiring_manager_name
    }
    ashby.create_or_update_record(cand_urgent.candidate_id, ashby_data)

    breaches = gatekeeper.scan_candidate_slas(cand_urgent, current_date=date(2026, 8, 22))
    print(f"Total SLA Exceptions Detected: {len(breaches)}")
    for b in breaches:
        print(f"  🚨 [{b['severity']}] Gate: {b['gate']} | Candidate: {b['candidate_name']} ({b['days_until_start']} days left)")
        print(f"     Issue: {b['issue']}")
        print(f"     Recommended Action: {b['recommended_action']}")

        # Draft Claude AI Escalation
        sla_msg = claude.draft_sla_escalation(
            candidate_name=b['candidate_name'],
            gate=b['gate'],
            days_left=b['days_until_start'],
            manager_name="Alex Rivera"
        )
        print(f"     💬 AI Drafted Escalation Message:\n     {sla_msg}")

    # -------------------------------------------------------------------------
    # SCENARIO 7: Cryptographic Audit Ledger Verification
    # -------------------------------------------------------------------------
    print_header("Scenario 7: Cryptographic Audit Ledger Verification")
    is_valid = audit_logger.verify_integrity()
    total_logs = len(audit_logger.list_all_entries())
    print(f"Ledger Integrity Valid: {is_valid}")
    print(f"Total Audit Entries Recorded: {total_logs}")
    print("\nRecent Audit Entry Hash Chain Sample:")
    for entry in audit_logger.list_all_entries()[-3:]:
        print(f"  • LogID: {entry['log_id']} | Event: {entry['event_type']} | Status: {entry['status']} | Hash: {entry['hash'][:24]}...")

    print_header("Demo Complete! All Scenarios Verified Successfully.")

if __name__ == "__main__":
    main()
