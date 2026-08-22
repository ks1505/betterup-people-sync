import pytest
from datetime import date
from src.models.candidate import CandidateProfile, Address
from src.core.validator import PreFlightValidator

def test_valid_candidate_passes():
    cand = CandidateProfile(
        candidate_id="CAND-VALID",
        first_name="Carlos",
        last_name="Mendez",
        personal_email="carlos.mendez@example.com",
        job_title="Data Scientist",
        department="Data",
        manager_email="data.head@betterup.co",
        hiring_manager_name="Elena VP",
        location="Austin, TX",
        address=Address(street="700 Congress Ave", city="Austin", state="TX", zip_code="78701"),
        start_date=date(2026, 9, 15)
    )
    res = PreFlightValidator.validate_candidate(cand)
    assert res.is_valid is True
    assert res.has_errors is False

def test_invalid_zip_code_fails():
    cand = CandidateProfile(
        candidate_id="CAND-BAD-ZIP",
        first_name="Carlos",
        last_name="Mendez",
        personal_email="carlos.mendez@example.com",
        job_title="Data Scientist",
        department="Data",
        manager_email="data.head@betterup.co",
        hiring_manager_name="Elena VP",
        location="Austin, TX",
        address=Address(street="700 Congress Ave", city="Austin", state="TX", zip_code="BAD_ZIP"),
        start_date=date(2026, 9, 15)
    )
    res = PreFlightValidator.validate_candidate(cand)
    assert res.is_valid is False
    assert res.has_errors is True
    assert any(i.code == "INVALID_ZIP_CODE" for i in res.issues)

def test_past_start_date_fails():
    cand = CandidateProfile(
        candidate_id="CAND-PAST-DATE",
        first_name="Carlos",
        last_name="Mendez",
        personal_email="carlos.mendez@example.com",
        job_title="Data Scientist",
        department="Data",
        manager_email="data.head@betterup.co",
        hiring_manager_name="Elena VP",
        location="Austin, TX",
        address=Address(street="700 Congress Ave", city="Austin", state="TX", zip_code="78701"),
        start_date=date(2020, 1, 1)  # Past date
    )
    res = PreFlightValidator.validate_candidate(cand)
    assert res.is_valid is False
    assert any(i.code == "START_DATE_IN_PAST" for i in res.issues)
