import os
import hashlib
import pyodbc
from dotenv import load_dotenv

load_dotenv()

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.getenv('DB_SERVER')},1433;"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

connection = pyodbc.connect(connection_string)
cursor = connection.cursor()

cursor.execute("""
    SELECT transaction_id, escrow_id, type, amount, transaction_date
    FROM Transactions
    ORDER BY transaction_id
""")

transactions = cursor.fetchall()

previous_hash = None

for transaction in transactions:
    transaction_id = transaction[0]
    escrow_id = transaction[1]
    transaction_type = transaction[2]
    amount = transaction[3]
    transaction_date = transaction[4]

    data = (
        f"{transaction_id}|"
        f"{escrow_id}|"
        f"{transaction_type}|"
        f"{amount}|"
        f"{transaction_date}|"
        f"{previous_hash}"
    )

    current_hash = hashlib.sha256(data.encode()).hexdigest()

    cursor.execute("""
        INSERT INTO LedgerBlocks
            (transaction_id, prev_hash, current_hash)
        VALUES (?, ?, ?)
    """, transaction_id, previous_hash, current_hash)

    previous_hash = current_hash

connection.commit()

cursor.close()
connection.close()

print(f"✅ {len(transactions)} ledger blocks created successfully!")