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

# Get only the Gigs INSERT statement
gig_start = sql_script.find("INSERT INTO Gigs")

if gig_start == -1:
    raise Exception("Gigs INSERT statement not found.")

gig_sql = sql_script[gig_start:].strip()

cursor.execute(gig_sql)
connection.commit()

cursor.close()
connection.close()

print("✅ 30 gigs inserted successfully!")