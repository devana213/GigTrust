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

with open("database/schema.sql", "r") as file:
    sql_script = file.read()

statements = sql_script.split(";")

for statement in statements:
    statement = statement.strip()

    if statement:
        cursor.execute(statement)
        print("✅ Executed SQL statement")

connection.commit()

cursor.close()
connection.close()

print("🎉 Database schema updated successfully!")