"""Replace the non-hashed seed passwords (users 1, 2, 3) with proper PBKDF2 hashes.

Run from C:\\Dev\\GigTrust:
    .venv312\\Scripts\\python.exe fix_seed_hashes.py
You type new passwords for users 1 and 2 (hidden). Nothing is printed or stored in plain text.
"""
import getpass
import secrets

from backend.database import get_db_connection
from mongo.auth_users import _hash_password


def ask(label):
    while True:
        p1 = getpass.getpass(f"New password for {label} (min 6 chars): ")
        if len(p1) < 6:
            print("Too short, try again.")
            continue
        if getpass.getpass("Type it again to confirm: ") != p1:
            print("Did not match, try again.")
            continue
        return p1


conn = get_db_connection()
cur = conn.cursor()
try:
    cur.execute("SELECT user_id, role, email FROM Users WHERE user_id IN (1, 2, 3) ORDER BY user_id")
    rows = cur.fetchall()
    for user_id, role, email in rows:
        if role.upper() == "ADMIN":
            new_hash = _hash_password(secrets.token_urlsafe(32))
            print(f"User {user_id} (ADMIN): set to an unusable random hash (admin login uses .env).")
        else:
            print(f"\nUser {user_id} ({role}, {email})")
            new_hash = _hash_password(ask(f"user {user_id}"))
        cur.execute("UPDATE Users SET password_hash = ? WHERE user_id = ?", new_hash, user_id)
    conn.commit()

    cur.execute(
        "SELECT user_id, role, CASE WHEN password_hash LIKE 'pbkdf2_sha256$%' THEN 'hashed' ELSE 'NOT HASHED' END "
        "FROM Users WHERE user_id IN (1, 2, 3) ORDER BY user_id"
    )
    print("\nResult:")
    for r in cur.fetchall():
        print(tuple(r))
finally:
    conn.close()
