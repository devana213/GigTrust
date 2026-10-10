// contracts.js - contract, escrow and transaction panels for both dashboards.
// Needs config.js, dashboard-common.js and marketplace.js loaded before it.
// Panels: <div id="contracts-panel" data-role="client|freelancer"></div>
//         <div id="transactions-panel"></div>

function gtEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function gtPost(path) {
  // user_id is sent so the backend can check who is acting (Task 5).
  const sep = path.includes("?") ? "&" : "?";
  const res = await fetch(`${API}${path}${sep}user_id=${encodeURIComponent(getUserId())}`, { method: "POST" });
  return res.json();
}

async function gtFund(escrowId) {
  if (!confirm(`Fund escrow #${escrowId}?`)) return;
  const r = await gtPost(`/escrows/${escrowId}/fund`);
  if (r.status !== "success") alert(r.message || r.error || "Funding failed.");
  gtRefreshAll();
}

async function gtRelease(escrowId) {
  if (!confirm(`Approve the work and release payment from escrow #${escrowId}?`)) return;
  const r = await gtPost(`/escrows/${escrowId}/release`);
  if (r.status !== "success") alert(r.message || r.error || "Release failed.");
  gtRefreshAll();
}

async function gtVerifyLedger() {
  const out = document.getElementById("gt-verify-result");
  if (out) out.textContent = "Verifying...";
  try {
    const res = await fetch(`${API}/ledger/verify`);
    const d = await res.json();
    if (out) {
      out.textContent = d.status === "valid"
        ? `Ledger valid (${d.blocks_verified} blocks verified)`
        : `LEDGER BROKEN: ${d.message || d.error || JSON.stringify(d)}`;
      out.style.color = d.status === "valid" ? "#15803d" : "#b91c1c";
    }
  } catch (e) {
    if (out) { out.textContent = "Could not reach backend."; out.style.color = "#b91c1c"; }
  }
}

async function gtLoadContracts() {
  const panel = document.getElementById("contracts-panel");
  if (!panel) return;
  const role = panel.dataset.role === "freelancer" ? "freelancer" : "client";
  panel.innerHTML = '<p class="muted">Loading...</p>';
  try {
    const res = await fetch(`${API}/users/${getUserId()}/contracts?role=${role}`);
    const d = await res.json();
    if (d.status !== "success") { panel.innerHTML = '<p class="muted">Could not load contracts.</p>'; return; }
    if (d.contracts.length === 0) { panel.innerHTML = '<p class="muted">No contracts yet.</p>'; return; }

    panel.innerHTML = d.contracts.map(c => {
      const es = c.escrow_status || "NONE";
      let action = "";
      if (role === "client" && es === "UNFUNDED") {
        action = `<button class="primary-btn small-btn" onclick="gtFund(${c.escrow_id})">Fund Escrow</button>`;
      } else if (role === "client" && es === "HELD") {
        action = `<button class="primary-btn small-btn" onclick="gtRelease(${c.escrow_id})">Approve &amp; Release</button>`;
      } else if (role === "freelancer" && es === "UNFUNDED") {
        action = '<span class="muted">Waiting for client to fund</span>';
      } else if (role === "freelancer" && es === "HELD") {
        action = '<span class="muted">Funds secured in escrow</span>';
      } else if (es === "RELEASED") {
        action = '<span class="muted">Paid</span>';
      }
      const other = role === "client" ? `Freelancer: ${gtEsc(c.freelancer_name)}` : `Client: ${gtEsc(c.client_name)}`;
      return `
        <div class="gig-card">
          <div class="gig-card-header">
            <strong>${gtEsc(c.gig_title)}</strong>
            <span class="badge badge-${gtEsc(es.toLowerCase())}">Escrow ${gtEsc(es)}</span>
          </div>
          <p class="muted">Contract #${c.contract_id} (${gtEsc(c.contract_status)}) | ${other}</p>
          <div class="gig-card-footer">
            <span>${formatMoney(c.agreed_amount)}</span>
            ${action}
          </div>
        </div>`;
    }).join("");
  } catch (e) {
    panel.innerHTML = '<p class="muted">Could not reach backend.</p>';
  }
}

async function gtLoadTransactions() {
  const panel = document.getElementById("transactions-panel");
  if (!panel) return;
  panel.innerHTML = '<p class="muted">Loading...</p>';
  try {
    const res = await fetch(`${API}/users/${getUserId()}/transactions`);
    const d = await res.json();
    if (d.status !== "success") { panel.innerHTML = '<p class="muted">Could not load transactions.</p>'; return; }

    const verifyBar = `
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
        <button class="primary-btn small-btn" onclick="gtVerifyLedger()">Verify ledger</button>
        <span id="gt-verify-result" class="muted"></span>
      </div>`;

    if (d.transactions.length === 0) {
      panel.innerHTML = verifyBar + '<p class="muted">No transactions yet.</p>';
      return;
    }
    const myId = parseInt(getUserId());
    panel.innerHTML = verifyBar + d.transactions.map(t => {
      const dir = t.sender_id === myId ? "Sent" : "Received";
      const hash = t.block_hash
        ? `Block #${t.block_id} | hash ${gtEsc(t.block_hash.slice(0, 16))}...`
        : "No ledger block";
      return `
        <div class="gig-card">
          <div class="gig-card-header">
            <strong>${gtEsc(t.transaction_type)}</strong>
            <span class="badge badge-${gtEsc(t.status.toLowerCase())}">${gtEsc(t.status)}</span>
          </div>
          <p class="muted">Txn #${t.transaction_id} | Escrow #${t.escrow_id} | ${dir}</p>
          <div class="gig-card-footer">
            <span>${formatMoney(t.amount)}</span>
            <span class="muted" style="font-family:monospace; font-size:12px;">${hash}</span>
          </div>
        </div>`;
    }).join("");
  } catch (e) {
    panel.innerHTML = '<p class="muted">Could not reach backend.</p>';
  }
}

function gtRefreshAll() {
  gtLoadContracts();
  gtLoadTransactions();
}

gtRefreshAll();
