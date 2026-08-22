import hashlib
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from src.models.candidate import CandidateProfile, Address
from src.models.events import EventType, ChangeDelta, OnboardingEvent
from src.models.validation import PreFlightValidationResult
from src.core.validator import PreFlightValidator
from src.core.audit_logger import AuditLogger
from src.mock_adapters import (
    AshbyAdapter,
    WorkdayAdapter,
    OktaLumosAdapter,
    ExpoITAdapter,
    SlackAdapter,
    CohortTrackerAdapter,
)

class ReconciliationEngine:
    """
    Idempotent State Reconciliation Engine.
    Ensures changes in start date, name, address, or off-cycle hires ripple deterministically
    across Workday, Okta, ExpoIT, Slack, and Cohort Tracker without duplicate side-effects.
    """
    def __init__(
        self,
        ashby: AshbyAdapter,
        workday: WorkdayAdapter,
        okta: OktaLumosAdapter,
        expoit: ExpoITAdapter,
        slack: SlackAdapter,
        tracker: CohortTrackerAdapter,
        audit_logger: AuditLogger
    ):
        self.ashby = ashby
        self.workday = workday
        self.okta = okta
        self.expoit = expoit
        self.slack = slack
        self.tracker = tracker
        self.audit_logger = audit_logger
        self._processed_keys: set = set()

    def generate_idempotency_key(self, candidate_id: str, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Generates a deterministic key based on candidate ID, event type, and payload hash.
        """
        payload_str = str(sorted(payload.items()))
        raw = f"{candidate_id}:{event_type}:{payload_str}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def reconcile_hire(self, candidate: CandidateProfile, source_system: str, event_type: str) -> Dict[str, Any]:
        """
        Main reconciliation execution method.
        """
        # 1. Idempotency Check
        payload = candidate.dict(include={
            "candidate_id", "first_name", "last_name", "personal_email",
            "job_title", "department", "start_date", "address"
        })
        idempotency_key = self.generate_idempotency_key(candidate.candidate_id, event_type, payload)

        if idempotency_key in self._processed_keys:
            return {
                "status": "SKIPPED_DUPLICATE",
                "idempotency_key": idempotency_key,
                "message": "Event already processed. Idempotency gate blocked re-execution.",
                "affected_systems": []
            }

        # 2. Pre-Flight Data Quality Validation
        validation_result: PreFlightValidationResult = PreFlightValidator.validate_candidate(candidate)

        if not validation_result.is_valid:
            # Block propagation due to bad data
            issues_summary = [f"{i.field}: {i.message}" for i in validation_result.issues]
            self.audit_logger.log_event(
                event_type=EventType.VALIDATION_FAILED,
                candidate_id=candidate.candidate_id,
                idempotency_key=idempotency_key,
                source_system=source_system,
                affected_systems=[],
                changes=[{"error": msg} for msg in issues_summary],
                status="BLOCKED",
                details="Pre-flight validation failed. Propagation halted to prevent data contamination."
            )

            # Alert Slack
            self.slack.send_notification(
                channel="#people-ops-alerts",
                recipient_email="people-ops@betterup.co",
                message=f"⚠️ [DATA VALIDATION BLOCKED] Onboarding for {candidate.full_name()} ({candidate.candidate_id}) blocked due to data errors: {', '.join(issues_summary)}"
            )

            return {
                "status": "BLOCKED_VALIDATION_FAILED",
                "idempotency_key": idempotency_key,
                "validation": validation_result.dict(),
                "affected_systems": []
            }

        # 3. Compute Diffs & Update Workday (HRIS System of Record)
        affected_systems = []
        changes = []

        wd_record = self.workday.get_record(candidate.candidate_id)
        wd_payload = {
            "legal_first_name": candidate.first_name,
            "legal_last_name": candidate.last_name,
            "preferred_first_name": candidate.preferred_name,
            "personal_email": candidate.personal_email,
            "work_email": candidate.work_email or f"{candidate.first_name[0].lower()}{candidate.last_name.lower()}@betterup.co",
            "hire_date": candidate.start_date.isoformat(),
            "job_profile": candidate.job_title,
            "cost_center": candidate.department,
            "work_location": candidate.location,
            "status": "Pre-Hire"
        }

        if wd_record:
            if wd_record.get("hire_date") != candidate.start_date.isoformat():
                changes.append({
                    "target_system": "Workday_HRIS",
                    "field": "hire_date",
                    "old_value": wd_record.get("hire_date"),
                    "new_value": candidate.start_date.isoformat()
                })
        else:
            changes.append({
                "target_system": "Workday_HRIS",
                "field": "record",
                "old_value": None,
                "new_value": "CREATED"
            })

        updated_wd = self.workday.create_or_update_record(candidate.candidate_id, wd_payload)
        candidate.workday_employee_id = updated_wd["employee_id"]
        candidate.work_email = updated_wd["work_email"]
        affected_systems.append("Workday_HRIS")

        # 4. Sync Okta & Lumos Identity
        okta_record = self.okta.get_record(candidate.candidate_id)
        okta_payload = {
            "employee_id": candidate.workday_employee_id,
            "first_name": candidate.preferred_name or candidate.first_name,
            "last_name": candidate.last_name,
            "upn_email": candidate.work_email,
            "activation_date": candidate.start_date.isoformat(),
            "status": "STAGED"
        }

        if okta_record and okta_record.get("activation_date") != candidate.start_date.isoformat():
            changes.append({
                "target_system": "Okta_Lumos",
                "field": "activation_date",
                "old_value": okta_record.get("activation_date"),
                "new_value": candidate.start_date.isoformat()
            })

        updated_okta = self.okta.create_or_update_record(candidate.candidate_id, okta_payload)
        candidate.okta_id = updated_okta["okta_id"]
        candidate.okta_provisioned = True
        affected_systems.append("Okta_Lumos")

        # 5. Sync ExpoIT Hardware Shipping Order
        expo_record = self.expoit.get_record(candidate.candidate_id)
        expo_payload = {
            "recipient_name": candidate.preferred_or_legal_name(),
            "laptop_model": candidate.hardware_tier,
            "shipping_street": candidate.address.street,
            "shipping_city": candidate.address.city,
            "shipping_state": candidate.address.state,
            "shipping_zip": candidate.address.zip_code,
            "target_start_date": candidate.start_date.isoformat(),
            "shipping_status": "Ordered"
        }

        if expo_record:
            if expo_record.get("target_start_date") != candidate.start_date.isoformat():
                changes.append({
                    "target_system": "ExpoIT_Hardware",
                    "field": "target_start_date",
                    "old_value": expo_record.get("target_start_date"),
                    "new_value": candidate.start_date.isoformat()
                })
            if expo_record.get("shipping_street") != candidate.address.street:
                changes.append({
                    "target_system": "ExpoIT_Hardware",
                    "field": "shipping_street",
                    "old_value": expo_record.get("shipping_street"),
                    "new_value": candidate.address.street
                })
        else:
            changes.append({
                "target_system": "ExpoIT_Hardware",
                "field": "hardware_order",
                "old_value": None,
                "new_value": "ORDERED"
            })

        self.expoit.create_or_update_record(candidate.candidate_id, expo_payload)
        candidate.hardware_order_status = "Ordered"
        affected_systems.append("ExpoIT_Hardware")

        # 6. Update Cohort Tracker Sheet/DB
        tracker_payload = {
            "full_name": candidate.full_name(),
            "department": candidate.department,
            "start_date": candidate.start_date.isoformat(),
            "workday_status": "Synced",
            "okta_status": "Staged",
            "hardware_status": "Ordered",
            "overall_onboarding_status": "On Track"
        }
        self.tracker.create_or_update_record(candidate.candidate_id, tracker_payload)
        candidate.cohort_tracker_synced = True
        affected_systems.append("Cohort_Tracker")

        # 7. Notify Manager via Slack
        slack_msg = f"🎉 *Onboarding Update for {candidate.full_name()}*\n• *Role*: {candidate.job_title} ({candidate.department})\n• *Start Date*: {candidate.start_date.strftime('%B %d, %Y')}\n• *Work Email*: {candidate.work_email}\n• *Hardware Order*: {candidate.hardware_tier} ordered via ExpoIT."
        self.slack.send_notification(
            channel=f"#{candidate.department.lower()}-onboarding",
            recipient_email=candidate.manager_email,
            message=slack_msg
        )
        candidate.slack_invited = True
        affected_systems.append("Slack_Comms")

        # 8. Record in Cryptographic Audit Logger & Mark Key Processed
        self._processed_keys.add(idempotency_key)

        self.audit_logger.log_event(
            event_type=event_type,
            candidate_id=candidate.candidate_id,
            idempotency_key=idempotency_key,
            source_system=source_system,
            affected_systems=affected_systems,
            changes=changes,
            status="SUCCESS",
            details=f"Successfully reconciled state across {len(affected_systems)} systems."
        )

        return {
            "status": "RECONCILED",
            "idempotency_key": idempotency_key,
            "candidate_id": candidate.candidate_id,
            "workday_employee_id": candidate.workday_employee_id,
            "work_email": candidate.work_email,
            "affected_systems": affected_systems,
            "changes_applied": changes
        }
