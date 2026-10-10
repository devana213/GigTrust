function getUserId() {
  return localStorage.getItem("gigtrust_user_id");
}

function getRole() {
  return localStorage.getItem("gigtrust_role");
}

async function fetchGigs() {
  const res = await fetch(`${API}/gigs`);
  return res.json();
}

async function postGig(title, description, budget) {
  const res = await fetch(`${API}/gigs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: parseInt(getUserId()),
      title,
      description,
      budget: parseFloat(budget),
    }),
  });
  return res.json();
}

async function fetchBids(gigId) {
  const res = await fetch(`${API}/gigs/${gigId}/bids`);
  return res.json();
}

async function placeBid(gigId, amount, proposal) {
  const res = await fetch(`${API}/bids`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      gig_id: gigId,
      freelancer_id: parseInt(getUserId()),
      bid_amount: parseFloat(amount),
      proposal,
    }),
  });
  return res.json();
}

async function acceptBid(bidId) {
  const res = await fetch(`${API}/bids/${bidId}/accept?user_id=${getUserId()}`, { method: "POST" });
  return res.json();
}

async function fundEscrow(escrowId) {
  const res = await fetch(`${API}/escrows/${escrowId}/fund?user_id=${getUserId()}`, { method: "POST" });
  return res.json();
}

function formatMoney(n) {
  return "Rs " + Number(n).toLocaleString("en-IN");
}

function timeAgo(dateStr) {
  const diff = Math.floor((Date.now() - new Date(dateStr + "Z")) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}
