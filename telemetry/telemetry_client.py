import os
import ssl
from datetime import datetime, timezone

from dotenv import load_dotenv
try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
    # Python 3.12+ removed the `asyncore` module that cassandra-driver uses
    # by default for its event loop, and the libev C-extension fallback
    # isn't reliably prebuilt for brand-new Python versions (e.g. 3.14) yet.
    # AsyncioConnection is a pure-Python alternative that avoids both.
    from cassandra.io.asyncioreactor import AsyncioConnection
    CASSANDRA_AVAILABLE = True
except Exception:
    CASSANDRA_AVAILABLE = False

load_dotenv()

CASSANDRA_HOST = os.getenv("CASSANDRA_HOST")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "10350"))
CASSANDRA_USERNAME = os.getenv("CASSANDRA_USERNAME")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD")
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "gigtrust")

# Tracks whether we've already ensured the keyspace/table exist in this process,
# so we don't re-run CREATE IF NOT EXISTS on every single call.
_schema_ready = False


def get_cassandra_session():
    if not CASSANDRA_AVAILABLE:
        raise RuntimeError("Cassandra driver not available in this environment.")

    auth_provider = PlainTextAuthProvider(
        username=CASSANDRA_USERNAME,
        password=CASSANDRA_PASSWORD
    )

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False

    cluster = Cluster(
        [CASSANDRA_HOST],
        port=CASSANDRA_PORT,
        auth_provider=auth_provider,
        ssl_context=ssl_context,
        connection_class=AsyncioConnection
    )

    session = cluster.connect()

    _ensure_schema(session)
    session.set_keyspace(CASSANDRA_KEYSPACE)

    return cluster, session


def _ensure_schema(session):
    """Create the keyspace and table if they don't exist yet.
    Cosmos DB's Cassandra API requires these to exist before use --
    unlike self-hosted Cassandra, nothing is created automatically."""
    global _schema_ready
    if _schema_ready:
        return

    session.execute(
        f"""
        CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
        WITH REPLICATION = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}
        """
    )

    session.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {CASSANDRA_KEYSPACE}.telemetry_readings (
            region text,
            metric_type text,
            ts timestamp,
            node_id text,
            value double,
            PRIMARY KEY ((region, metric_type), ts)
        ) WITH CLUSTERING ORDER BY (ts DESC)
        """
    )

    _schema_ready = True


def test_cassandra_connection():
    cluster, session = get_cassandra_session()

    try:
        rows = session.execute(
            "SELECT release_version FROM system.local"
        )

        version = rows.one().release_version

        return {
            "database": "Cosmos DB Cassandra",
            "status": "connected",
            "release_version": version
        }

    finally:
        session.shutdown()
        cluster.shutdown()


def insert_telemetry(
    region: str,
    metric_type: str,
    node_id: str,
    value: float
):
    cluster, session = get_cassandra_session()

    try:
        query = """
        INSERT INTO telemetry_readings (
            region,
            metric_type,
            ts,
            node_id,
            value
        )
        VALUES (%s, %s, %s, %s, %s)
        """

        timestamp = datetime.now(timezone.utc)

        session.execute(
            query,
            (
                region,
                metric_type,
                timestamp,
                node_id,
                value
            )
        )

        return {
            "status": "inserted",
            "region": region,
            "metric_type": metric_type,
            "node_id": node_id,
            "value": value,
            "timestamp": timestamp.isoformat()
        }

    finally:
        session.shutdown()
        cluster.shutdown()


def get_recent_telemetry(
    region: str,
    metric_type: str,
    limit: int = 10
):
    cluster, session = get_cassandra_session()

    try:
        query = """
        SELECT
            region,
            metric_type,
            ts,
            node_id,
            value
        FROM telemetry_readings
        WHERE region = %s
          AND metric_type = %s
        LIMIT %s
        """

        rows = session.execute(
            query,
            (
                region,
                metric_type,
                limit
            )
        )

        return [
            {
                "region": row.region,
                "metric_type": row.metric_type,
                "timestamp": row.ts.isoformat(),
                "node_id": row.node_id,
                "value": row.value
            }
            for row in rows
        ]

    finally:
        session.shutdown()
        cluster.shutdown()