import re
from datetime import date, datetime
from typing import Dict, Any, Optional
from src.models.candidate import CandidateProfile
from src.models.validation import PreFlightValidationResult

class PreFlightValidator:
    """
    Pre-Flight Cross-System Data Quality Validator.
    Prevents bad data in Ashby or HRIS from cascading downstream into Workday, Okta, or ExpoIT shipping.
    """

    @staticmethod
    def validate_candidate(candidate: CandidateProfile) -> PreFlightValidationResult:
        result = PreFlightValidationResult(is_valid=True, candidate_id=candidate.candidate_id)

        # 1. Validate First & Last Name
        if not candidate.first_name or len(candidate.first_name.strip()) < 1:
            result.add_issue("first_name", "ERROR", "NAME_EMPTY", "First name cannot be empty.")
        if not candidate.last_name or len(candidate.last_name.strip()) < 1:
            result.add_issue("last_name", "ERROR", "NAME_EMPTY", "Last name cannot be empty.")

        if re.search(r"[0-9!@#$%^&*()_+={}\[\]:;\"'<>,/?]", candidate.first_name + candidate.last_name):
            result.add_issue("name", "WARNING", "NAME_SYMBOLS", "Name contains special characters or numbers.", "Verify legal spelling with HR.")

        # 2. Validate Personal Email
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_regex, candidate.personal_email):
            result.add_issue("personal_email", "ERROR", "EMAIL_INVALID", f"Invalid email format: {candidate.personal_email}")

        # 3. Validate Shipping Address (Critical for ExpoIT hardware delivery)
        addr = candidate.address
        if not addr.street or len(addr.street.strip()) < 3:
            result.add_issue("address.street", "ERROR", "ADDRESS_STREET_MISSING", "Street address is missing or too short for shipping.")
        
        # Check ZIP code format (5 digits or 5-4)
        zip_clean = addr.zip_code.strip()
        if not re.match(r"^\d{5}(-\d{4})?$", zip_clean):
            result.add_issue(
                "address.zip_code",
                "ERROR",
                "INVALID_ZIP_CODE",
                f"ZIP code '{addr.zip_code}' is invalid for US shipping. Must be 5 digits (e.g. 94105).",
                "Correct ZIP code in Ashby before creating shipping label."
            )

        if not addr.city or len(addr.city.strip()) < 2:
            result.add_issue("address.city", "ERROR", "CITY_MISSING", "City name is missing.")

        # 4. Validate Start Date
        today = date.today()
        if candidate.start_date < today:
            result.add_issue(
                "start_date",
                "ERROR",
                "START_DATE_IN_PAST",
                f"Start date {candidate.start_date} is in the past.",
                "Update start date to a future business day."
            )

        # Check if start date falls on Saturday (5) or Sunday (6)
        if candidate.start_date.weekday() in (5, 6):
            result.add_issue(
                "start_date",
                "WARNING",
                "START_DATE_WEEKEND",
                f"Start date {candidate.start_date} falls on a weekend ({candidate.start_date.strftime('%A')}).",
                "Verify if orientation on weekend is intentional or shift to Monday."
            )

        # 5. Department & Manager Check
        if not candidate.department:
            result.add_issue("department", "ERROR", "DEPT_MISSING", "Department is required for role-based access assignment.")
        if not candidate.manager_email or not re.match(email_regex, candidate.manager_email):
            result.add_issue("manager_email", "ERROR", "MANAGER_EMAIL_INVALID", "Valid manager email required for notifications.")

        return result
