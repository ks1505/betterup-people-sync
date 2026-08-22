from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from src.models.candidate import CandidateProfile
from src.models.events import EventType
from src.core.audit_logger import AuditLogger
from src.mock_adapters import SlackAdapter, CohortTrackerAdapter, ExpoITAdapter

class SLAGatekeeper:
    """
    Proactive SLA Watchdog & Exception Monitor.
    Watches onboarding milestones (Hardware order, Background check, Okta staging) against deadlines.
    Triggers automated AI-driven escalations before deadlines are missed.
    """
    def __init__(
        self,
        expoit: ExpoITAdapter,
        slack: SlackAdapter,
        tracker: CohortTrackerAdapter,
        audit_logger: AuditLogger,
        hardware_sla_days: int = 7,
        bg_check_sla_days: int = 5,
        okta_sla_days: int = 3
    ):
        self.expoit = expoit
        self.slack = slack
        self.tracker = tracker
        self.audit_logger = audit_logger
        self.hardware_sla_days = hardware_sla_days
        self.bg_check_sla_days = bg_check_sla_days
        self.okta_sla_days = okta_sla_days

    def scan_candidate_slas(self, candidate: CandidateProfile, current_date: Optional[date] = None) -> List[Dict[str, Any]]:
        if current_date is None:
            current_date = date.today()

        days_until_start = (candidate.start_date - current_date).days
        breaches = []

        # 1. Hardware Order SLA (7 Days)
        hardware_record = self.expoit.get_record(candidate.candidate_id)
        is_hardware_ordered = hardware_record and hardware_record.get("shipping_status") in ("Ordered", "Processing", "Shipped", "Delivered")
        
        if days_until_start <= self.hardware_sla_days and not is_hardware_ordered:
            severity = "CRITICAL" if days_until_start <= 3 else "HIGH"
            breach = {
                "candidate_id": candidate.candidate_id,
                "candidate_name": candidate.full_name(),
                "gate": "IT_HARDWARE_ORDER",
                "days_until_start": days_until_start,
                "sla_threshold_days": self.hardware_sla_days,
                "severity": severity,
                "issue": f"Hardware order not placed with ExpoIT. Only {days_until_start} days left until start date {candidate.start_date}.",
                "recommended_action": "Trigger urgent IT equipment expedite order via ExpoIT portal."
            }
            breaches.append(breach)

        # 2. Background Check SLA (5 Days)
        if days_until_start <= self.bg_check_sla_days and candidate.background_check_status != "Passed":
            severity = "CRITICAL" if days_until_start <= 2 else "HIGH"
            breach = {
                "candidate_id": candidate.candidate_id,
                "candidate_name": candidate.full_name(),
                "gate": "BACKGROUND_CHECK",
                "days_until_start": days_until_start,
                "sla_threshold_days": self.bg_check_sla_days,
                "severity": severity,
                "issue": f"Background check status is '{candidate.background_check_status}'. Only {days_until_start} days remaining.",
                "recommended_action": "Contact candidate / vendor to complete missing authorization form."
            }
            breaches.append(breach)

        # 3. Okta Provisioning SLA (3 Days)
        if days_until_start <= self.okta_sla_days and not candidate.okta_provisioned:
            breach = {
                "candidate_id": candidate.candidate_id,
                "candidate_name": candidate.full_name(),
                "gate": "OKTA_PROVISIONING",
                "days_until_start": days_until_start,
                "sla_threshold_days": self.okta_sla_days,
                "severity": "CRITICAL",
                "issue": f"Okta account not staged for corporate access. Only {days_until_start} days remaining.",
                "recommended_action": "Invoke Okta auto-staging trigger immediately."
            }
            breaches.append(breach)

        # Handle Breaches
        if breaches:
            for b in breaches:
                # Update Tracker Status to At Risk or Blocked
                self.tracker.create_or_update_record(
                    candidate.candidate_id,
                    {"overall_onboarding_status": "Blocked" if b["severity"] == "CRITICAL" else "At Risk"}
                )

                # Send Slack Escalation
                msg = (
                    f"🚨 *SLA GATEWAY ALERT [{b['severity']}]*\n"
                    f"• *Candidate*: {candidate.full_name()} ({candidate.department})\n"
                    f"• *Start Date*: {candidate.start_date} ({b['days_until_start']} days away)\n"
                    f"• *Gate*: {b['gate']}\n"
                    f"• *Issue*: {b['issue']}\n"
                    f"• *Action*: {b['recommended_action']}"
                )
                self.slack.send_notification(
                    channel="#onboarding-escalations",
                    recipient_email=candidate.manager_email,
                    message=msg
                )

                # Log Audit
                self.audit_logger.log_event(
                    event_type=EventType.SLA_BREACH_WARNING,
                    candidate_id=candidate.candidate_id,
                    idempotency_key=f"SLA-{candidate.candidate_id}-{b['gate']}-{current_date}",
                    source_system="SLAGatekeeper",
                    affected_systems=["Cohort_Tracker", "Slack_Comms"],
                    changes=[b],
                    status="SLA_ALERT",
                    details=f"SLA breach detected for gate {b['gate']} ({b['severity']}). Escalation dispatched."
                )

        return breaches
