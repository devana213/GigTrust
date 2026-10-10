# GigTrust authorization check: every call below MUST be refused.
# Run:  powershell -ExecutionPolicy Bypass -File .\auth_check.ps1

$base = "http://127.0.0.1:8000"

function Try-Call($label, $method, $path, $body) {
    Write-Host "`n$label"
    if ($body) {
        $r = Invoke-RestMethod -Method $method -Uri "$base$path" -ContentType "application/json" -Body ($body | ConvertTo-Json)
    } else {
        $r = Invoke-RestMethod -Method $method -Uri "$base$path"
    }
    Write-Host ($r | ConvertTo-Json -Compress)
    if ($r.status -eq "failed") { Write-Host "REFUSED (good)" -ForegroundColor Green }
    else { Write-Host "ALLOWED (bad!)" -ForegroundColor Red }
}

Try-Call "1. Freelancer (user 2) tries to post a gig" "POST" "/gigs" @{ client_id = 2; title = "x"; description = "x"; budget = 100 }
Try-Call "2. Client (user 1) tries to place a bid" "POST" "/bids" @{ gig_id = 10; freelancer_id = 1; bid_amount = 100; proposal = "x" }
Try-Call "3. Freelancer (user 2) tries to fund escrow 8" "POST" "/escrows/8/fund?user_id=2" $null
$g = Invoke-RestMethod -Method Post -Uri "$base/gigs" -ContentType "application/json" -Body (@{ client_id = 1; title = "auth check gig"; description = "x"; budget = 100 } | ConvertTo-Json)
$bd = Invoke-RestMethod -Method Post -Uri "$base/bids" -ContentType "application/json" -Body (@{ gig_id = $g.gig_id; freelancer_id = 2; bid_amount = 90; proposal = "x" } | ConvertTo-Json)
Try-Call "4. Freelancer (user 2) tries to accept their OWN pending bid $($bd.bid_id)" "POST" "/bids/$($bd.bid_id)/accept?user_id=2" $null
Try-Call "5. No user_id at all on release" "POST" "/escrows/8/release" $null
