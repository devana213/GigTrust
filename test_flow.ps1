# GigTrust full-flow test: gig -> bid -> accept -> fund -> release -> verify ledger
# Uses user 1 (client) and user 2 (freelancer). Every ID is captured automatically.
# Run in PowerShell:  powershell -ExecutionPolicy Bypass -File .\test_flow.ps1

$base = "http://127.0.0.1:8000"
$clientId = 1
$freelancerId = 2

function Call($method, $path, $body) {
    $uri = "$base$path"
    if ($body) {
        return Invoke-RestMethod -Method $method -Uri $uri -ContentType "application/json" -Body ($body | ConvertTo-Json)
    }
    return Invoke-RestMethod -Method $method -Uri $uri
}

function Require-Success($label, $resp) {
    if ($resp.status -ne "success") {
        Write-Host "FAILED at: $label" -ForegroundColor Red
        $resp | ConvertTo-Json -Depth 6
        exit 1
    }
    Write-Host "OK: $label" -ForegroundColor Green
}

Write-Host "`n== 1. Post gig (client $clientId) =="
$gig = Call "POST" "/gigs" @{ client_id = $clientId; title = "Flow test gig"; description = "Created by test_flow.ps1"; budget = 1000 }
Require-Success "post gig" $gig
$gigId = $gig.gig_id
Write-Host "gig_id = $gigId"

Write-Host "`n== 2. Place bid (freelancer $freelancerId) =="
$bid = Call "POST" "/bids" @{ gig_id = $gigId; freelancer_id = $freelancerId; bid_amount = 900; proposal = "Test proposal from test_flow.ps1" }
Require-Success "place bid" $bid
$bidId = $bid.bid_id
Write-Host "bid_id = $bidId"

Write-Host "`n== 3. Accept bid =="
$acc = Call "POST" "/bids/$bidId/accept?user_id=$clientId" $null
Require-Success "accept bid" $acc
$contractId = $acc.contract_id
$escrowId = $acc.escrow_id
Write-Host "contract_id = $contractId, escrow_id = $escrowId"

Write-Host "`n== 4. Fund escrow =="
$fund = Call "POST" "/escrows/$escrowId/fund?user_id=$clientId" $null
Require-Success "fund escrow" $fund
Write-Host "fund transaction_id = $($fund.transaction_id)"
Write-Host "ledger: $($fund.ledger | ConvertTo-Json -Compress -Depth 4)"

Write-Host "`n== 5. Release escrow =="
$rel = Call "POST" "/escrows/$escrowId/release?user_id=$clientId" $null

Write-Host "`n== 5b. Wrong-user check: freelancer tries to release again (must be refused) =="
$bad = Call "POST" "/escrows/$escrowId/release?user_id=$freelancerId" $null
Write-Host ($bad | ConvertTo-Json -Compress)
Require-Success "release escrow" $rel
Write-Host "release transaction_id = $($rel.transaction_id)"
Write-Host "ledger: $($rel.ledger | ConvertTo-Json -Compress -Depth 4)"

Write-Host "`n== 6. Transactions for escrow $escrowId =="
$tx = Call "GET" "/users/$clientId/transactions" $null
Require-Success "list transactions" $tx
$tx.transactions | Where-Object { $_.escrow_id -eq $escrowId } |
    Select-Object transaction_id, transaction_type, status, amount, block_id |
    Format-Table -AutoSize

Write-Host "== 7. Ledger blocks for escrow $escrowId =="
$blocks = Call "GET" "/ledger/blocks" $null
Require-Success "list ledger blocks" $blocks
$blocks.blocks | Where-Object { $_.escrow_id -eq $escrowId } |
    Select-Object block_id, transaction_id, transaction_type, amount, previous_hash, current_hash |
    Format-List

Write-Host "== 8. Verify whole ledger =="
$ver = Call "GET" "/ledger/verify" $null
$ver | ConvertTo-Json -Depth 6

Write-Host "`nDone. Paste everything above into the chat."
