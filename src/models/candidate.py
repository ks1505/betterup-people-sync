from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class Address(BaseModel):
    street: str
    unit: Optional[str] = None
    city: str
    state: str
    zip_code: str
    country: str = "USA"

    def full_address(self) -> str:
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{self.street}{unit_str}, {self.city}, {self.state} {self.zip_code}, {self.country}"

class CandidateProfile(BaseModel):
    """
    Canonical Unified Data Model for a Hire across Ashby, Workday, Okta, ExpoIT, etc.
    """
    candidate_id: str = Field(description="Ashby Candidate ID or System ID")
    workday_employee_id: Optional[str] = Field(default=None, description="Workday Employee ID")
    okta_id: Optional[str] = Field(default=None, description="Okta User ID / UPN")
    
    first_name: str
    last_name: str
    preferred_name: Optional[str] = None
    personal_email: str
    work_email: Optional[str] = None
    
    job_title: str
    department: str
    manager_email: str
    hiring_manager_name: str
    location: str
    address: Address
    
    start_date: date
    hardware_tier: str = Field(default="MacBook Pro 16", description="Assigned laptop model")
    
    # Milestone Statuses
    offer_status: str = "Accepted"
    background_check_status: str = "Passed"  # Pending, Passed, Failed
    hardware_order_status: str = "Not Ordered"  # Not Ordered, Ordered, Shipped, Delivered
    okta_provisioned: bool = False
    slack_invited: bool = False
    cohort_tracker_synced: bool = False
    
    version: int = 1
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def preferred_or_legal_name(self) -> str:
        if self.preferred_name:
            return f"{self.preferred_name} {self.last_name}"
        return self.full_name()
