import os
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

with open("database/sample_data.sql", "r") as file:
    sql_script = file.read()

transaction_start = sql_script.find("INSERT INTO Transactions")

if transaction_start == -1:
    raise Exception("Transactions INSERT statement not found.")

transaction_sql = sql_script[transaction_start:].strip()

cursor.execute(transaction_sql)
connection.commit()

cursor.close()
connection.close()

print("✅ Transactions inserted successfully!")