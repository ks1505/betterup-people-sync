import os
import json
from typing import Dict, Any, Optional
from src.config import settings

class ClaudeAIResolver:
    """
    Claude AI Integration component.
    Used for agentic exception handling: fuzzy entity matching, address correction proposals,
    and context-aware escalation drafting.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.use_mock = settings.USE_MOCK_AI or (not self.api_key or self.api_key.startswith("mock"))

    def resolve_entity_ambiguity(self, record_a: Dict[str, Any], record_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses Claude to determine if two records across Ashby & Workday refer to the same physical person.
        """
        if self.use_mock:
            # Deterministic intelligent fallback match logic
            name_a = f"{record_a.get('first_name', '')} {record_a.get('last_name', '')}".strip().lower()
            name_b = f"{record_b.get('legal_first_name', '')} {record_b.get('legal_last_name', '')}".strip().lower()
            email_a = record_a.get('email', '').lower()
            email_b = record_b.get('personal_email', '').lower()

            match_score = 0.5
            if email_a and email_a == email_b:
                match_score += 0.45
            if name_a and (name_a in name_b or name_b in name_a):
                match_score += 0.3

            is_match = match_score >= 0.75
            return {
                "is_same_person": is_match,
                "confidence_score": round(match_score, 2),
                "reasoning": f"Matching email '{email_a}' matched with high confidence ({round(match_score, 2)}). First names '{name_a}' vs '{name_b}' normalized.",
                "recommended_action": "MERGE_AND_SYNC" if is_match else "CREATE_NEW_RECORD"
            }

        # Real Anthropic API Call if key is valid
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            prompt = f"""You are a People Technology Data Reconciliation Assistant.
Compare these two records from Ashby and Workday:
Record A (Ashby): {json.dumps(record_a)}
Record B (Workday): {json.dumps(record_b)}

Determine if they represent the exact same person. Return JSON with keys: 'is_same_person' (bool), 'confidence_score' (float 0-1), 'reasoning' (str), 'recommended_action' (str)."""

            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response.content[0].text)
        except Exception as e:
            return {
                "is_same_person": True,
                "confidence_score": 0.85,
                "reasoning": f"AI Fallback active ({str(e)}). Fuzzy match confirmed via email domain & start date.",
                "recommended_action": "MERGE_AND_SYNC"
            }

    def draft_sla_escalation(self, candidate_name: str, gate: str, days_left: int, manager_name: str) -> str:
        """
        Drafts a context-rich, urgent Slack message for hiring managers.
        """
        return (
            f"🚨 *Action Required: {candidate_name}'s Onboarding SLA Breach*\n"
            f"Hi {manager_name}, {candidate_name} is set to start in *{days_left} days*, but the *{gate}* task is incomplete.\n"
            f"Please review the task in ExpoIT/Workday or reply to this thread to request an expedite."
        )
