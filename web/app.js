const API_BASE = '/api/v1';

async function fetchAPI(endpoint, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, options);
        return await res.json();
    } catch (err) {
        console.error('API Error:', err);
        return { error: err.message };
    }
}

async function runSimulation(scenario) {
    const logBox = document.getElementById('sim-log');
    const timeBox = document.getElementById('last-exec-time');
    
    logBox.textContent = `⚡ Dispatching scenario request [${scenario}]...`;
    timeBox.textContent = new Date().toLocaleTimeString();

    let body = { scenario };
    if (scenario === 'CHANGE_START_DATE') {
        body.candidate_id = 'CAND-1001';
        body.new_start_date = '2026-09-15';
    } else if (scenario === 'INJECT_BAD_ADDRESS') {
        body.bad_zip = 'BAD99';
    }

    const data = await fetchAPI('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    logBox.textContent = JSON.stringify(data, null, 2);
    
    // Refresh Matrix and Audit Ledger
    refreshSystemState();
    loadAuditLedger();
}

async function scanSLAExceptions() {
    const logBox = document.getElementById('sim-log');
    const timeBox = document.getElementById('last-exec-time');

    logBox.textContent = `⏰ Running Proactive SLA Watchdog Deadline Scan...`;
    timeBox.textContent = new Date().toLocaleTimeString();

    const data = await fetchAPI('/slas/exceptions');
    logBox.textContent = JSON.stringify(data, null, 2);

    refreshSystemState();
    loadAuditLedger();
}

async function refreshSystemState() {
    const grid = document.getElementById('matrix-grid');
    const data = await fetchAPI('/systems/state');

    if (!data || data.error) {
        grid.innerHTML = `<div class="error">Failed to load system matrix</div>`;
        return;
    }

    const ashby = data.ashby || {};
    const workday = data.workday || {};
    const okta = data.okta || {};
    const expoit = data.expoit || {};
    const tracker = data.cohort_tracker || {};

    let html = '';
    const candidateIds = Object.keys(ashby);

    if (candidateIds.length === 0) {
        grid.innerHTML = `<div class="text-muted">No candidate records found.</div>`;
        return;
    }

    for (const cid of candidateIds) {
        const aRec = ashby[cid] || {};
        const wdRec = Object.values(workday).find(w => w.candidate_id === cid) || {};
        const oktaRec = Object.values(okta).find(o => o.candidate_id === cid || o.employee_id === wdRec.employee_id) || {};
        const expRec = expoit[cid] || {};
        const trkRec = tracker[cid] || {};

        html += `
            <div class="candidate-card">
                <div class="card-header">
                    <div>
                        <div class="candidate-name">${aRec.candidate_first_name || 'Hire'} ${aRec.candidate_last_name || ''}</div>
                        <div class="candidate-meta">${aRec.job_title || ''} • ${aRec.department || ''} • Start: <strong>${aRec.start_date || 'N/A'}</strong></div>
                    </div>
                    <span class="badge">${trkRec.overall_onboarding_status || 'Syncing'}</span>
                </div>
                <div class="systems-status-row">
                    <div class="sys-badge">
                        <span class="sys-name">Workday</span>
                        <span class="sys-val ${wdRec.employee_id ? 'ok' : 'pending'}">${wdRec.employee_id || 'Pending'}</span>
                    </div>
                    <div class="sys-badge">
                        <span class="sys-name">Okta</span>
                        <span class="sys-val ${oktaRec.status === 'STAGED' ? 'ok' : 'pending'}">${oktaRec.status || 'Pending'}</span>
                    </div>
                    <div class="sys-badge">
                        <span class="sys-name">ExpoIT</span>
                        <span class="sys-val ${expRec.shipping_status === 'Ordered' ? 'ok' : 'pending'}">${expRec.shipping_status || 'Unordered'}</span>
                    </div>
                    <div class="sys-badge">
                        <span class="sys-name">Tracker</span>
                        <span class="sys-val ${trkRec.workday_status === 'Synced' ? 'ok' : 'pending'}">${trkRec.overall_onboarding_status || 'Pending'}</span>
                    </div>
                    <div class="sys-badge">
                        <span class="sys-name">Slack</span>
                        <span class="sys-val ok">Notified</span>
                    </div>
                </div>
            </div>
        `;
    }

    grid.innerHTML = html;
}

async function loadAuditLedger() {
    const tbody = document.getElementById('ledger-tbody');
    const topHashLabel = document.getElementById('ledger-top-hash');
    const data = await fetchAPI('/audit/ledger');

    if (!data || !data.entries) return;

    if (data.entries.length > 0) {
        const top = data.entries[data.entries.length - 1];
        topHashLabel.textContent = `Top Hash: ${top.hash.substring(0, 16)}...`;
    }

    let rows = '';
    for (const entry of data.entries.slice().reverse()) {
        const statusClass = entry.status === 'SUCCESS' ? 'ok' : (entry.status === 'BLOCKED' ? 'blocked' : 'pending');
        rows += `
            <tr>
                <td><strong>${entry.log_id}</strong></td>
                <td>${new Date(entry.timestamp).toLocaleTimeString()}</td>
                <td>${entry.event_type}</td>
                <td>${entry.candidate_id}</td>
                <td><small>${entry.idempotency_key.substring(0, 8)}...</small></td>
                <td>${entry.source_system}</td>
                <td>${(entry.affected_systems || []).join(', ')}</td>
                <td><span class="sys-val ${statusClass}">${entry.status}</span></td>
                <td class="hash-cell">${entry.hash.substring(0, 16)}...</td>
            </tr>
        `;
    }

    tbody.innerHTML = rows;
}

async function verifyLedgerIntegrity() {
    const data = await fetchAPI('/health');
    alert(`Audit Ledger Cryptographic Verification: ${data.audit_integrity ? 'VALID (Hash chain intact)' : 'TAMPERED / INVALID'}`);
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    refreshSystemState();
    loadAuditLedger();
});
