from fastapi import FastAPI
from backend.database import get_db_connection
from agent.resource_manager import make_resource_decision
from telemetry.telemetry_client import (
    test_cassandra_connection,
    insert_telemetry,
    get_recent_telemetry
)
from mongo.activity_logs import (
    log_activity,
    test_mongo_connection
)
from backend.services.blockchain import (
    add_transaction_to_ledger,
    verify_ledger
)

app = FastAPI(
    title="GigTrust API",
    description="Cloud-based freelance marketplace with secure escrow transactions",
    version="1.0"
)


@app.get("/")
def home():
    return {
        "project": "GigTrust",
        "message": "Backend running successfully"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return {
            "database": "Azure SQL",
            "status": "connected",
            "test": result[0]
        }

    except Exception as e:
        return {
            "database": "Azure SQL",
            "status": "failed",
            "error": str(e)
        }


@app.post("/ledger/add/{transaction_id}")
def add_ledger_block(transaction_id: int):
    try:
        return add_transaction_to_ledger(transaction_id)

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.get("/ledger/verify")
def verify_blockchain_ledger():
    try:
        return verify_ledger()

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.post("/activity/test")
def test_activity_log():
    try:
        return log_activity(
            event_type="TEST_EVENT",
            user_id=1,
            details={
                "message": "GigTrust MongoDB logging test"
            }
        )

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.get("/health/mongodb")
def mongodb_health():
    try:
        return test_mongo_connection()

    except Exception as e:
        return {
            "database": "Cosmos DB MongoDB",
            "status": "failed",
            "error": str(e)
        }


@app.post("/activity/test")
def test_activity_log():
    try:
        return log_activity(
            event_type="TEST_EVENT",
            user_id=1,
            details={
                "message": "GigTrust MongoDB activity logging test"
            }
        )

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.post("/activity/escrow-funded")
def log_escrow_funded():
    try:
        return log_activity(
            event_type="ESCROW_FUNDED",
            user_id=1,
            transaction_id=1,
            amount=9500.00,
            details={
                "escrow_id": 1,
                "contract_id": 1,
                "source": "Azure SQL"
            }
        )

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.get("/health/cassandra")
def cassandra_health():
    try:
        return test_cassandra_connection()

    except Exception as e:
        return {
            "database": "Cosmos DB Cassandra",
            "status": "failed",
            "error": str(e)
        }

@app.post("/telemetry/test")
def create_test_telemetry():
    try:
        results = []

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="CPU_UTIL",
                node_id="gigtrust-api-01",
                value=72.4
            )
        )

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="LATENCY_MS",
                node_id="gigtrust-api-01",
                value=118.0
            )
        )

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="THROUGHPUT_RPS",
                node_id="gigtrust-api-01",
                value=430.0
            )
        )

        return {
            "status": "success",
            "telemetry": results
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


@app.get("/telemetry/{region}/{metric_type}")
def read_telemetry(
    region: str,
    metric_type: str
):
    try:
        return get_recent_telemetry(
            region=region,
            metric_type=metric_type
        )

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.get("/agent/decision/{region}")
def resource_agent_decision(region: str):
    try:
        return make_resource_decision(region)

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.post("/telemetry/high-load")
def create_high_load_telemetry():
    try:
        results = []

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="CPU_UTIL",
                node_id="gigtrust-api-01",
                value=88.5
            )
        )

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="LATENCY_MS",
                node_id="gigtrust-api-01",
                value=220.0
            )
        )

        results.append(
            insert_telemetry(
                region="Central India",
                metric_type="THROUGHPUT_RPS",
                node_id="gigtrust-api-01",
                value=910.0
            )
        )

        return {
            "status": "success",
            "scenario": "high_load",
            "telemetry": results
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.post("/telemetry/second-region")
def create_second_region_telemetry():
    try:
        results = []

        results.append(
            insert_telemetry(
                region="UAE North",
                metric_type="CPU_UTIL",
                node_id="gigtrust-api-02",
                value=42.0
            )
        )

        results.append(
            insert_telemetry(
                region="UAE North",
                metric_type="LATENCY_MS",
                node_id="gigtrust-api-02",
                value=85.0
            )
        )

        results.append(
            insert_telemetry(
                region="UAE North",
                metric_type="THROUGHPUT_RPS",
                node_id="gigtrust-api-02",
                value=310.0
            )
        )

        return {
            "status": "success",
            "region": "UAE North",
            "telemetry": results
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }