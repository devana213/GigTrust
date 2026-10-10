"""Ledger tamper demo: tamper -> /ledger/verify must FAIL -> restore -> /ledger/verify must PASS.

Run from C:\\Dev\\GigTrust (the backend server must be running):
    .venv312\\Scripts\\python.exe tamper_demo.py
"""
import json
import urllib.request

from backend.database import get_db_connection

BASE = "http://127.0.0.1:8000"
BLOCK_ID = 3  # an early test block; tampering it must break the chain


def verify():
    with urllib.request.urlopen(f"{BASE}/ledger/verify", timeout=60) as r:
        return json.loads(r.read().decode())


conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT amount FROM LedgerBlocks WHERE block_id = ?", BLOCK_ID)
row = cur.fetchone()
if not row:
    raise SystemExit(f"Block {BLOCK_ID} not found.")
original = row[0]
print(f"Block {BLOCK_ID} original amount: {original}")

print("\n[1] Ledger BEFORE tampering:")
print(json.dumps(verify(), indent=2))

try:
    cur.execute("UPDATE LedgerBlocks SET amount = amount + 1 WHERE block_id = ?", BLOCK_ID)
    conn.commit()
    cur.execute("SELECT amount FROM LedgerBlocks WHERE block_id = ?", BLOCK_ID)
    print(f"\n[2] TAMPERED block {BLOCK_ID} amount to: {cur.fetchone()[0]}")
    print("    Ledger AFTER tampering (must report a break):")
    print(json.dumps(verify(), indent=2))
finally:
    cur.execute("UPDATE LedgerBlocks SET amount = ? WHERE block_id = ?", original, BLOCK_ID)
    conn.commit()
    cur.execute("SELECT amount FROM LedgerBlocks WHERE block_id = ?", BLOCK_ID)
    print(f"\n[3] RESTORED block {BLOCK_ID} amount to: {cur.fetchone()[0]}")
    conn.close()

print("    Ledger AFTER restoring (must be valid again):")
print(json.dumps(verify(), indent=2))
