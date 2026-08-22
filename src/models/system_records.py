from datetime import date, datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class AshbyOfferRecord(BaseModel):
    offer_id: str
    candidate_id: str
    candidate_first_name: str
    candidate_last_name: str
    email: str
    job_title: str
    department: str
    start_date: str  # YYYY-MM-DD
    street_address: str
    city: str
    state: str
    zip_code: str
    manager_email: str
    hiring_manager_name: str
    offer_status: str = "Signed"
    last_modified: datetime = Field(default_factory=datetime.utcnow)

class WorkdayWorkerRecord(BaseModel):
    employee_id: str
    candidate_id: str
    legal_first_name: str
    legal_last_name: str
    preferred_first_name: Optional[str] = None
    personal_email: str
    work_email: Optional[str] = None
    hire_date: str  # YYYY-MM-DD
    job_profile: str
    cost_center: str
    work_location: str
    status: str = "Pre-Hire"  # Pre-Hire, Active, Terminated
    last_synced: datetime = Field(default_factory=datetime.utcnow)

class OktaUserRecord(BaseModel):
    okta_id: str
    upn_email: str  # e.g. jsmith@betterup.co
    employee_id: str
    candidate_id: Optional[str] = None
    first_name: str
    last_name: str
    status: str = "STAGED"  # STAGED, ACTIVE, DEPROVISIONED
    assigned_apps: List[str] = []
    activation_date: str  # YYYY-MM-DD

class ExpoITHardwareOrder(BaseModel):
    order_id: str
    candidate_id: str
    recipient_name: str
    laptop_model: str
    shipping_street: str
    shipping_city: str
    shipping_state: str
    shipping_zip: str
    shipping_status: str = "Pending"  # Pending, Processing, Shipped, Delivered
    estimated_delivery: Optional[str] = None
    target_start_date: str

class SlackNotificationRecord(BaseModel):
    notification_id: str
    channel: str
    recipient_email: str
    message: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)

class CohortTrackerEntry(BaseModel):
    cohort_id: str
    candidate_id: str
    full_name: str
    department: str
    start_date: str
    workday_status: str
    okta_status: str
    hardware_status: str
    overall_onboarding_status: str  # On Track, At Risk, Blocked, Complete
    last_reconciled: datetime = Field(default_factory=datetime.utcnow)
