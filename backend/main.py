from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import get_db_connection
from agent.resource_manager import make_resource_decision

from telemetry.telemetry_client import (
    test_cassandra_connection,
    insert_telemetry,
    get_recent_telemetry,
)

from mongo.activity_logs import (
    log_activity,
    test_mongo_connection,
)

from mongo.auth_users import (
    register_account,
    login_account,
)

from backend.services.blockchain import (
    add_transaction_to_ledger,
    verify_ledger,
)


app = FastAPI(
    title="GigTrust API",
    description="Cloud-based freelance marketplace with secure escrow transactions",
    version="1.2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(background: BackgroundTasks, event_type, user_id=None,
         transaction_id=None, amount=None, details=None):
    """Write an activity event to Cosmos DB (Mongo) AFTER the response is sent.
    Never raises: if Mongo is unreachable the main request is unaffected."""

    def _run():
        try:
            log_activity(
                event_type=event_type,
                user_id=user_id,
                transaction_id=transaction_id,
                amount=amount,
                details=details or {},
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[activity-log] skipped {event_type}: {exc}")

    background.add_task(_run)


def _extract_user_id(result):
    """auth_users.py's exact response shape isn't fixed, so look in the usual places."""
    if not isinstance(result, dict):
        return None
    for key in ("user_id", "id"):
        if result.get(key) is not None:
            return result[key]
    user = result.get("user")
    if isinstance(user, dict):
        return user.get("user_id") or user.get("id")
    return None


def _role_of(cursor, user_id):
    """Role of a user from the Users table (CLIENT / FREELANCER / ADMIN), or None."""
    if user_id is None:
        return None
    cursor.execute("SELECT role FROM Users WHERE user_id = ?", user_id)
    row = cursor.fetchone()
    return row[0].upper() if row and row[0] else None


def _denied(message):
    return {"status": "failed", "message": message}


def _post_commit_ledger(transaction_id):
    """Ledger write happens after the SQL commit. If it fails the money movement
    is still recorded; the block can be retried via POST /ledger/add/{id}."""
    try:
        return add_transaction_to_ledger(transaction_id)
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error": str(exc), "retry": f"POST /ledger/add/{transaction_id}"}


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str
    role: str


# ---------------------------------------------------------------------------
# Basics / health
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return {
        "project": "GigTrust",
        "message": "Backend running successfully",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/database")
def database_health():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        return {"database": "Azure SQL", "status": "connected", "test": result[0]}
    except Exception as e:
        return {"database": "Azure SQL", "status": "failed", "error": str(e)}


@app.get("/health/mongodb")
def mongodb_health():
    try:
        return test_mongo_connection()
    except Exception as e:
        return {"database": "Cosmos DB MongoDB", "status": "failed", "error": str(e)}


@app.get("/health/cassandra")
def cassandra_health():
    try:
        return test_cassandra_connection()
    except Exception as e:
        return {"database": "Cosmos DB Cassandra", "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/register")
def register(request: RegisterRequest, background: BackgroundTasks):
    try:
        result = register_account(
            name=request.name,
            email=request.email,
            password=request.password,
            role=request.role,
        )
        ok = isinstance(result, dict) and result.get("status") == "success"
        _log(
            background,
            "USER_REGISTERED" if ok else "USER_REGISTER_FAILED",
            user_id=_extract_user_id(result),
            details={"email": request.email, "role": request.role},
        )
        return result
    except Exception as e:
        return {"status": "failed", "message": "Account registration failed.", "error": str(e)}


@app.post("/auth/login")
def login(request: LoginRequest, background: BackgroundTasks):
    try:
        result = login_account(
            email=request.email,
            password=request.password,
            role=request.role,
        )
        ok = isinstance(result, dict) and result.get("status") == "success"
        _log(
            background,
            "USER_LOGIN" if ok else "USER_LOGIN_FAILED",
            user_id=_extract_user_id(result),
            details={"email": request.email, "role": request.role},
        )
        return result
    except Exception as e:
        return {"status": "failed", "message": "Login failed.", "error": str(e)}


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

@app.post("/ledger/add/{transaction_id}")
def add_ledger_block(transaction_id: int):
    try:
        return add_transaction_to_ledger(transaction_id)
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/ledger/verify")
def verify_blockchain_ledger():
    try:
        return verify_ledger()
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/ledger/blocks")
def list_ledger_blocks():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT block_id, transaction_id, escrow_id, sender_id, receiver_id, amount, "
            "transaction_type, previous_hash, current_hash, created_at "
            "FROM LedgerBlocks ORDER BY block_id"
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "blocks": [
                {
                    "block_id": r[0],
                    "transaction_id": r[1],
                    "escrow_id": r[2],
                    "sender_id": r[3],
                    "receiver_id": r[4],
                    "amount": float(r[5]),
                    "transaction_type": r[6],
                    "previous_hash": r[7],
                    "current_hash": r[8],
                    "created_at": str(r[9]),
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Activity log (Cosmos DB - Mongo API) and telemetry (Cosmos DB - Cassandra API)
# ---------------------------------------------------------------------------

@app.post("/activity/test")
def test_activity_log():
    try:
        return log_activity(
            event_type="TEST_EVENT",
            user_id=1,
            details={"message": "GigTrust MongoDB activity logging test"},
        )
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.post("/activity/escrow-funded")
def log_escrow_funded():
    try:
        return log_activity(
            event_type="ESCROW_FUNDED",
            user_id=1,
            transaction_id=1,
            amount=9500.00,
            details={"escrow_id": 1, "contract_id": 1, "source": "Azure SQL"},
        )
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.post("/telemetry/test")
def create_test_telemetry():
    try:
        results = []
        results.append(insert_telemetry(region="Central India", metric_type="CPU_UTIL", node_id="gigtrust-api-01", value=72.4))
        results.append(insert_telemetry(region="Central India", metric_type="LATENCY_MS", node_id="gigtrust-api-01", value=118.0))
        results.append(insert_telemetry(region="Central India", metric_type="THROUGHPUT_RPS", node_id="gigtrust-api-01", value=430.0))
        return {"status": "success", "scenario": "normal_load", "region": "Central India", "telemetry": results}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/telemetry/{region}/{metric_type}")
def read_telemetry(region: str, metric_type: str):
    try:
        return get_recent_telemetry(region=region, metric_type=metric_type)
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/agent/decision/{region}")
def resource_agent_decision(region: str):
    try:
        return make_resource_decision(region)
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.post("/telemetry/high-load")
def create_high_load_telemetry():
    try:
        results = []
        results.append(insert_telemetry(region="Central India", metric_type="CPU_UTIL", node_id="gigtrust-api-01", value=88.5))
        results.append(insert_telemetry(region="Central India", metric_type="LATENCY_MS", node_id="gigtrust-api-01", value=220.0))
        results.append(insert_telemetry(region="Central India", metric_type="THROUGHPUT_RPS", node_id="gigtrust-api-01", value=910.0))
        return {"status": "success", "scenario": "high_load", "region": "Central India", "telemetry": results}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.post("/telemetry/second-region")
def create_second_region_telemetry():
    try:
        results = []
        results.append(insert_telemetry(region="Korea Central", metric_type="CPU_UTIL", node_id="gigtrust-api-02", value=42.0))
        results.append(insert_telemetry(region="Korea Central", metric_type="LATENCY_MS", node_id="gigtrust-api-02", value=85.0))
        results.append(insert_telemetry(region="Korea Central", metric_type="THROUGHPUT_RPS", node_id="gigtrust-api-02", value=310.0))
        return {"status": "success", "region": "Korea Central", "telemetry": results}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Marketplace: gigs and bids
# ---------------------------------------------------------------------------

class GigCreateRequest(BaseModel):
    client_id: int
    title: str
    description: str
    budget: float


@app.post("/gigs")
def create_gig(request: GigCreateRequest, background: BackgroundTasks):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if _role_of(cursor, request.client_id) != "CLIENT":
            return _denied("Only a client account can post gigs.")
        cursor.execute(
            "INSERT INTO Gigs (client_id, title, description, budget, status, created_at) OUTPUT INSERTED.gig_id VALUES (?, ?, ?, ?, 'OPEN', SYSUTCDATETIME())",
            request.client_id, request.title, request.description, request.budget,
        )
        gig_id = cursor.fetchone()[0]
        conn.commit()
        _log(background, "GIG_POSTED", user_id=request.client_id, amount=request.budget,
             details={"gig_id": gig_id, "title": request.title})
        return {"status": "success", "gig_id": gig_id}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.get("/gigs")
def list_gigs():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT g.gig_id, g.title, g.description, g.budget, g.status, g.created_at, u.full_name FROM Gigs g JOIN Users u ON g.client_id = u.user_id ORDER BY g.created_at DESC"
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "gigs": [
                {"gig_id": r[0], "title": r[1], "description": r[2], "budget": float(r[3]), "status": r[4], "created_at": str(r[5]), "client_name": r[6]}
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


class BidCreateRequest(BaseModel):
    gig_id: int
    freelancer_id: int
    bid_amount: float
    proposal: str


@app.post("/bids")
def create_bid(request: BidCreateRequest, background: BackgroundTasks):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if _role_of(cursor, request.freelancer_id) != "FREELANCER":
            return _denied("Only a freelancer account can place bids.")
        cursor.execute(
            "INSERT INTO Bids (gig_id, freelancer_id, bid_amount, proposal, status, created_at) OUTPUT INSERTED.bid_id VALUES (?, ?, ?, ?, 'PENDING', SYSUTCDATETIME())",
            request.gig_id, request.freelancer_id, request.bid_amount, request.proposal,
        )
        bid_id = cursor.fetchone()[0]
        conn.commit()
        _log(background, "BID_PLACED", user_id=request.freelancer_id, amount=request.bid_amount,
             details={"bid_id": bid_id, "gig_id": request.gig_id})
        return {"status": "success", "bid_id": bid_id}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.get("/gigs/{gig_id}/bids")
def list_bids(gig_id: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT b.bid_id, b.freelancer_id, u.full_name, b.bid_amount, b.proposal, b.status, b.created_at FROM Bids b JOIN Users u ON b.freelancer_id = u.user_id WHERE b.gig_id = ? ORDER BY b.created_at DESC",
            gig_id,
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "bids": [
                {"bid_id": r[0], "freelancer_id": r[1], "freelancer_name": r[2], "bid_amount": float(r[3]), "proposal": r[4], "status": r[5], "created_at": str(r[6])}
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.post("/bids/{bid_id}/accept")
def accept_bid(bid_id: int, background: BackgroundTasks, user_id: int = None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT gig_id, freelancer_id, bid_amount, status FROM Bids WHERE bid_id = ?", bid_id)
        bid = cursor.fetchone()
        if not bid:
            return {"status": "failed", "message": "Bid not found."}
        gig_id, freelancer_id, bid_amount, bid_status = bid
        if bid_status != "PENDING":
            return {"status": "failed", "message": f"Bid is already {bid_status}."}

        cursor.execute("SELECT client_id, status FROM Gigs WHERE gig_id = ?", gig_id)
        gig = cursor.fetchone()
        if not gig:
            return {"status": "failed", "message": "Gig not found."}
        client_id, gig_status = gig
        if user_id is None or user_id != client_id:
            return _denied("Only the client who posted this gig can accept its bids.")
        if gig_status != "OPEN":
            return {"status": "failed", "message": f"Gig is {gig_status}; a bid was already accepted."}

        cursor.execute(
            "INSERT INTO Contracts (gig_id, client_id, freelancer_id, agreed_amount, status, created_at) OUTPUT INSERTED.contract_id VALUES (?, ?, ?, ?, 'ACTIVE', SYSUTCDATETIME())",
            gig_id, client_id, freelancer_id, bid_amount,
        )
        contract_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO Escrows (contract_id, amount, status) OUTPUT INSERTED.escrow_id VALUES (?, ?, 'UNFUNDED')",
            contract_id, bid_amount,
        )
        escrow_id = cursor.fetchone()[0]

        cursor.execute("UPDATE Bids SET status = 'ACCEPTED' WHERE bid_id = ?", bid_id)
        # Business rule: every other pending bid on this gig is rejected.
        cursor.execute(
            "UPDATE Bids SET status = 'REJECTED' WHERE gig_id = ? AND bid_id <> ? AND status = 'PENDING'",
            gig_id, bid_id,
        )
        cursor.execute("UPDATE Gigs SET status = 'IN_PROGRESS' WHERE gig_id = ?", gig_id)

        conn.commit()
        _log(background, "BID_ACCEPTED", user_id=client_id, amount=float(bid_amount),
             details={"bid_id": bid_id, "gig_id": gig_id, "contract_id": contract_id,
                      "escrow_id": escrow_id, "freelancer_id": freelancer_id})
        return {"status": "success", "contract_id": contract_id, "escrow_id": escrow_id}
    except Exception as e:
        if conn:
            conn.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Escrow lifecycle: UNFUNDED -> HELD (fund) -> RELEASED (release)
# Every money movement = Escrows update + Transactions row (one SQL transaction),
# then a hash-chained LedgerBlocks entry, then a Mongo activity event.
# ---------------------------------------------------------------------------

@app.post("/escrows/{escrow_id}/fund")
def fund_escrow(escrow_id: int, background: BackgroundTasks, user_id: int = None):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT c.client_id FROM Escrows e JOIN Contracts c ON e.contract_id = c.contract_id WHERE e.escrow_id = ?",
            escrow_id,
        )
        owner = cursor.fetchone()
        if not owner:
            return {"status": "failed", "message": "Escrow not found."}
        if user_id is None or user_id != owner[0]:
            return _denied("Only the client of this contract can fund its escrow.")

        cursor.execute(
            "UPDATE Escrows SET status = 'HELD', funded_at = SYSUTCDATETIME() WHERE escrow_id = ? AND status = 'UNFUNDED'",
            escrow_id,
        )
        if cursor.rowcount == 0:
            return {"status": "failed", "message": "Escrow not found or already funded."}

        cursor.execute(
            "SELECT e.amount, c.contract_id, c.client_id, c.freelancer_id FROM Escrows e "
            "JOIN Contracts c ON e.contract_id = c.contract_id WHERE e.escrow_id = ?",
            escrow_id,
        )
        amount, contract_id, client_id, freelancer_id = cursor.fetchone()

        cursor.execute(
            "INSERT INTO Transactions (escrow_id, sender_id, receiver_id, amount, transaction_type, status, created_at) "
            "OUTPUT INSERTED.transaction_id "
            "VALUES (?, ?, ?, ?, 'ESCROW_FUND', 'SUCCESS', SYSUTCDATETIME())",
            escrow_id, client_id, freelancer_id, amount,
        )
        transaction_id = cursor.fetchone()[0]

        conn.commit()

        ledger_result = _post_commit_ledger(transaction_id)
        _log(background, "ESCROW_FUNDED", user_id=client_id, transaction_id=transaction_id,
             amount=float(amount),
             details={"escrow_id": escrow_id, "contract_id": contract_id, "freelancer_id": freelancer_id})

        return {
            "status": "success",
            "message": "Escrow funded successfully.",
            "transaction_id": transaction_id,
            "ledger": ledger_result,
        }
    except Exception as e:
        if conn:
            conn.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.post("/escrows/{escrow_id}/release")
def release_escrow(escrow_id: int, background: BackgroundTasks, user_id: int = None):
    """Client approves the work: pays the held funds out to the freelancer."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT e.status, e.amount, c.contract_id, c.gig_id, c.client_id, c.freelancer_id "
            "FROM Escrows e JOIN Contracts c ON e.contract_id = c.contract_id "
            "WHERE e.escrow_id = ?",
            escrow_id,
        )
        row = cursor.fetchone()
        if not row:
            return {"status": "failed", "message": "Escrow not found."}
        escrow_status, amount, contract_id, gig_id, client_id, freelancer_id = row
        if user_id is None or user_id != client_id:
            return _denied("Only the client of this contract can release its payment.")
        if escrow_status != "HELD":
            return {"status": "failed", "message": f"Escrow is {escrow_status}; only HELD escrows can be released."}

        # The status guard in the WHERE clause makes a double release impossible.
        cursor.execute(
            "UPDATE Escrows SET status = 'RELEASED', released_at = SYSUTCDATETIME() WHERE escrow_id = ? AND status = 'HELD'",
            escrow_id,
        )
        if cursor.rowcount == 0:
            return {"status": "failed", "message": "Escrow was already released."}

        cursor.execute(
            "INSERT INTO Transactions (escrow_id, sender_id, receiver_id, amount, transaction_type, status, created_at) "
            "OUTPUT INSERTED.transaction_id "
            "VALUES (?, ?, ?, ?, 'ESCROW_RELEASE', 'SUCCESS', SYSUTCDATETIME())",
            escrow_id, client_id, freelancer_id, amount,
        )
        transaction_id = cursor.fetchone()[0]

        cursor.execute("UPDATE Contracts SET status = 'COMPLETED' WHERE contract_id = ?", contract_id)
        cursor.execute("UPDATE Gigs SET status = 'COMPLETED' WHERE gig_id = ?", gig_id)

        conn.commit()

        ledger_result = _post_commit_ledger(transaction_id)
        _log(background, "ESCROW_RELEASED", user_id=client_id, transaction_id=transaction_id,
             amount=float(amount),
             details={"escrow_id": escrow_id, "contract_id": contract_id, "freelancer_id": freelancer_id})

        return {
            "status": "success",
            "message": "Payment released to freelancer.",
            "transaction_id": transaction_id,
            "ledger": ledger_result,
        }
    except Exception as e:
        if conn:
            conn.rollback()
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Read endpoints for the dashboards
# ---------------------------------------------------------------------------

@app.get("/users/{user_id}/gigs")
def user_gigs(user_id: int):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gig_id, title, description, budget, status, created_at FROM Gigs WHERE client_id = ? ORDER BY created_at DESC",
            user_id,
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "gigs": [
                {"gig_id": r[0], "title": r[1], "description": r[2], "budget": float(r[3]), "status": r[4], "created_at": str(r[5])}
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.get("/users/{user_id}/contracts")
def user_contracts(user_id: int, role: str = "client"):
    """Contracts (with their escrow state) where the user is the client or the freelancer."""
    column = "c.client_id" if role == "client" else "c.freelancer_id"
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.contract_id, g.title, c.agreed_amount, c.status, c.created_at, "
            "e.escrow_id, e.status, e.funded_at, e.released_at, cu.full_name, fu.full_name "
            "FROM Contracts c "
            "JOIN Gigs g ON c.gig_id = g.gig_id "
            "JOIN Users cu ON c.client_id = cu.user_id "
            "JOIN Users fu ON c.freelancer_id = fu.user_id "
            "LEFT JOIN Escrows e ON e.contract_id = c.contract_id "
            f"WHERE {column} = ? ORDER BY c.created_at DESC",
            user_id,
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "contracts": [
                {
                    "contract_id": r[0],
                    "gig_title": r[1],
                    "agreed_amount": float(r[2]),
                    "contract_status": r[3],
                    "created_at": str(r[4]),
                    "escrow_id": r[5],
                    "escrow_status": r[6],
                    "funded_at": str(r[7]) if r[7] else None,
                    "released_at": str(r[8]) if r[8] else None,
                    "client_name": r[9],
                    "freelancer_name": r[10],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()


@app.get("/users/{user_id}/transactions")
def user_transactions(user_id: int):
    """Every transaction the user sent or received, with its ledger block (if any)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT t.transaction_id, t.escrow_id, t.sender_id, t.receiver_id, t.amount, "
            "t.transaction_type, t.status, t.created_at, l.block_id, l.current_hash "
            "FROM Transactions t "
            "LEFT JOIN LedgerBlocks l ON l.transaction_id = t.transaction_id "
            "WHERE t.sender_id = ? OR t.receiver_id = ? "
            "ORDER BY t.created_at DESC",
            user_id, user_id,
        )
        rows = cursor.fetchall()
        return {
            "status": "success",
            "transactions": [
                {
                    "transaction_id": r[0],
                    "escrow_id": r[1],
                    "sender_id": r[2],
                    "receiver_id": r[3],
                    "amount": float(r[4]),
                    "transaction_type": r[5],
                    "status": r[6],
                    "created_at": str(r[7]),
                    "block_id": r[8],
                    "block_hash": r[9],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if conn:
            conn.close()
