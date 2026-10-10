"""Lists every CHECK constraint in the GigTrust Azure SQL database.

Run from the repository root (the folder that contains backend/ and .env):
    python check_constraints.py
"""
from backend.database import get_db_connection

conn = get_db_connection()
try:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT OBJECT_NAME(parent_object_id) AS table_name, name, definition "
        "FROM sys.check_constraints ORDER BY table_name, name"
    )
    rows = cursor.fetchall()
    if not rows:
        print("No CHECK constraints found.")
    for table_name, name, definition in rows:
        print(f"{table_name}  |  {name}")
        print(f"    {definition}")
finally:
    conn.close()
