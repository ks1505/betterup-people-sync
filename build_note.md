# BetterUp People Tech Prototype: Technical Build Note

> **Role**: AI Automation Engineer Take-Home Exercise  
> **Author**: Engineering Candidate  
> **Date**: August 2026  
> **Deliverable**: Architectural Rationale, Design Decisions, Failure Handling & AI Tool Analysis  

---

## 1. Slice Selection Rationale

We selected the **Unified Change Propagation Engine with Integrated Pre-Flight Validation and SLA Gatekeeping**.

### Why This Slice Offers Maximum Leverage
When onboarding hires at speed, point-to-point scripts (e.g. Zapier syncing Ashby to Slack) create **data drift**. If a candidate's start date moves by two weeks post-offer, or an address has a missing unit number, isolated scripts fail silently or push bad data downstream. 

By engineering a single **Idempotent State Reconciler**, we solve root-cause synchronization across **Ashby, Workday, Okta/Lumos, ExpoIT, Slack, and Cohort Tracker**. Embedding **Pre-Flight Validation** and an **SLA Watchdog** into this engine ensures that:
1. **Bad data is trapped pre-flight** before it pollutes HRIS or triggers FedEx shipping labels.
2. **Changes propagate deterministically** across all 6 systems.
3. **Approaching SLA deadlines** (e.g. 7-day hardware lead times) trigger proactive Claude AI escalation to hiring managers.

---

## 2. Key Technical Design Decisions

```
+-----------------------------------------------------------------------------------+
|                                 CANONICAL DATA MODEL                              |
|                              (src/models/candidate.py)                            |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           PRE-FLIGHT QUALITY VALIDATOR                            |
|                              (src/core/validator.py)                              |
+-----------------------------------------------------------------------------------+
                    | Passed                                | Blocked (Bad ZIP/Address)
                    v                                       v
+---------------------------------------+   +---------------------------------------+
|    IDEMPOTENT STATE RECONCILER        |   |      AUDIT LOG & SLACK ALERT          |
|      (src/core/reconciler.py)         |   |    "Validation Gate Blocked Sync"     |
+---------------------------------------+   +---------------------------------------+
                    | Diffs & Atomic Updates
                    v
+-----------------------------------------------------------------------------------+
|            WORKDAY -> OKTA/LUMOS -> EXPOIT -> COHORT TRACKER -> SLACK            |
+-----------------------------------------------------------------------------------+
                    |
                    v
+-----------------------------------------------------------------------------------+
|                        CRYPTOGRAPHIC SHA-256 AUDIT LEDGER                         |
|                            (src/core/audit_logger.py)                             |
+-----------------------------------------------------------------------------------+
```

### A. Unified Data Model (`CandidateProfile`)
Rather than mapping per-system JSON payloads directly to each other, we established a **Canonical Domain Model** (`CandidateProfile`). This model normalizes identity across:
- Ashby Candidate ID (`CAND-XXXX`)
- Workday Employee ID (`WD-XXXXX`)
- Okta UPN (`first_initial.lastname@betterup.co`)
- ExpoIT Hardware Order ID (`EXPO-XXXX`)

### B. Idempotency & Re-execution Protection
Network retries and duplicate webhooks are guaranteed to occur in production. The `ReconciliationEngine` constructs a deterministic key:
$$\text{IdempotencyKey} = \text{MD5}(\text{candidate\_id} \mathbin{\Vert} \text{event\_type} \mathbin{\Vert} \text{sorted\_payload})$$
If the key has been processed, the reconciler returns a `SKIPPED_DUPLICATE` response immediately without emitting duplicate API mutations or sending repeat Slack alerts.

### C. Cryptographic Append-Only Audit Trail
To ensure auditability across HR compliance and security operations, every reconciliation step generates a tamper-evident entry chained via SHA-256 hashes:
$$\text{Hash}_n = \text{SHA256}(\text{Hash}_{n-1} \mathbin{\Vert} \text{Timestamp} \mathbin{\Vert} \text{EventType} \mathbin{\Vert} \text{CandidateID} \mathbin{\Vert} \text{Changes})$$
The `/api/v1/audit/ledger` endpoint provides real-time verification of ledger integrity.

### D. Failure Handling & Circuit Breaking
- **Pre-Flight Address Trap**: Validates street address length and US ZIP code patterns (e.g. 5 digits). If invalid, propagation is blocked before an ExpoIT hardware order is placed.
- **SLA Watchdog**: Scans candidates daily. If $T - \text{Start Date} \le 7\text{ days}$ and hardware is unordered, it raises a `CRITICAL` alert and dispatches a manager escalation via Slack.

---

## 3. What We Would Productionize

To move this working prototype to production at BetterUp scale:

1. **OAuth 2.0 / SSO & Webhook Signature Verification**:
   - Implement HMAC-SHA256 signature verification on incoming Ashby & Workday webhooks.
   - Use Okta OIDC Client Credentials flow with JWT bearer tokens for API connectors.
2. **Persistent Storage & Database Migrations**:
   - Replace in-memory mock adapters with PostgreSQL backed by SQLAlchemy / Alembic.
3. **Queueing & Rate Limiting**:
   - Wrap downstream adapter calls in Celery / Redis background workers with exponential backoff retries to respect Workday & Okta API rate limits.
4. **Model Context Protocol (MCP) Integration in Workflows**:
   - Deploy `src/ai/mcp_server.py` as an internal MCP micro-service accessible by internal Claude Code or Slack AI agents.

---

## 4. AI Tools Used & Case Study: "What the AI Got Wrong"

### AI Tools Utilized
- **Claude (Anthropic API & Claude Code)**: Used for agentic exception resolution, fuzzy entity matching between Ashby & Workday, and drafting Slack alerts.
- **Cursor / LLM Code Generation**: Used to accelerate boilerplate generation for Pydantic models and mock connectors.

### The AI Error Case Study 🔍
* **The Bug**: While generating the initial Okta user staging connector, the AI derived the candidate's Okta UPN email independently using `first_name.last_name@betterup.co`.
* **Why it Broke**: For a candidate with a legal name "Mayabelle Lin" in Workday but preferred name "Maya Lin" in Ashby, the AI generated `mayabelle.lin@betterup.co` in Workday and `maya.lin@betterup.co` in Okta. This created two distinct identities, breaking SSO login and Lumos entitlement mapping.
* **How We Caught & Fixed It**: During cross-system matrix testing, we inspected the generated UPNs in `src/mock_adapters/okta_lumos.py`. We caught the discrepancy between Workday legal email and Okta UPN. We fixed the architecture by establishing **Workday as the sole generator of the corporate work email**, which is then explicitly passed down to Okta, Lumos, ExpoIT, and Slack.
