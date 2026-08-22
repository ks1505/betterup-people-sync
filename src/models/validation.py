from typing import List, Optional
from pydantic import BaseModel, Field

class ValidationIssue(BaseModel):
    field: str
    severity: str  # ERROR, WARNING, INFO
    code: str
    message: str
    suggested_fix: Optional[str] = None

class PreFlightValidationResult(BaseModel):
    is_valid: bool
    candidate_id: str
    issues: List[ValidationIssue] = []
    has_errors: bool = False
    has_warnings: bool = False

    def add_issue(self, field: str, severity: str, code: str, message: str, suggested_fix: Optional[str] = None):
        issue = ValidationIssue(
            field=field,
            severity=severity,
            code=code,
            message=message,
            suggested_fix=suggested_fix
        )
        self.issues.append(issue)
        if severity == "ERROR":
            self.has_errors = True
            self.is_valid = False
        elif severity == "WARNING":
            self.has_warnings = True
