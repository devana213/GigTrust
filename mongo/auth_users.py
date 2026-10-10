import os
import base64
import hashlib
import hmac

from dotenv import load_dotenv
from backend.database import get_db_connection

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@gigtrust.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

def _to_db_role(role: str) -> str:
    mapping = {"user": "CLIENT", "freelancer": "FREELANCER", "admin": "ADMIN"}
    return mapping.get(role, role.upper())


def _from_db_role(role: str) -> str:
    mapping = {"CLIENT": "user", "FREELANCER": "freelancer", "ADMIN": "admin"}
    return mapping.get(role, role.lower())
def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 200_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(iterations),
            base64.b64encode(salt).decode("utf-8"),
            base64.b64encode(derived).decode("utf-8"),
        ]
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, hash_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def register_account(name: str, email: str, password: str, role: str):
    role = role.strip().lower()
    email = email.strip().lower()
    name = name.strip()

    if role not in {"user", "freelancer"}:
        return {
            "status": "failed",
            "message": "Only user and freelancer accounts can self-register.",
        }
    if not name:
        return {"status": "failed", "message": "Name is required."}
    if "@" not in email:
        return {"status": "failed", "message": "Enter a valid email address."}
    if len(password) < 6:
        return {
            "status": "failed",
            "message": "Password must contain at least 6 characters.",
        }

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM Users WHERE email = ?", email)
        if cursor.fetchone():
            return {
                "status": "failed",
                "message": "An account with this email already exists.",
            }

        password_hash = _hash_password(password)

        cursor.execute(
            """
            INSERT INTO Users (full_name, email, password_hash, role, balance, created_at)
            OUTPUT INSERTED.user_id
            VALUES (?, ?, ?, ?, 0, SYSUTCDATETIME())
            """,
            name, email, password_hash, _to_db_role(role),
)
        new_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "status": "success",
            "message": f"{role.capitalize()} account created.",
            "user": {
                "id": str(new_id),
                "name": name,
                "email": email,
                "role": role,
            },
        }
    except Exception as e:
        if conn:
            conn.rollback()
        return {"status": "failed", "message": "Registration failed.", "error": str(e)}
    finally:
        if conn:
            conn.close()


def login_account(email: str, password: str, role: str):
    role = role.strip().lower()
    email = email.strip().lower()

    if role == "admin":
        if email == ADMIN_EMAIL and hmac.compare_digest(password, ADMIN_PASSWORD):
            return {
                "status": "success",
                "message": "Admin login successful.",
                "user": {
                    "name": "Administrator",
                    "email": ADMIN_EMAIL,
                    "role": "admin",
                },
            }
        return {"status": "failed", "message": "Invalid admin credentials."}

    if role not in {"user", "freelancer"}:
        return {"status": "failed", "message": "Invalid role."}

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, full_name, email, password_hash, role FROM Users WHERE email = ? AND role = ?",
             email, _to_db_role(role),
)
        row = cursor.fetchone()

        if not row:
            return {
                "status": "failed",
                "message": f"No {role} account was found for this email.",
            }

        user_id, full_name, db_email, password_hash, db_role = row

        if not _verify_password(password, password_hash or ""):
            return {"status": "failed", "message": "Invalid email or password."}

        return {
            "status": "success",
            "message": "Login successful.",
            "user": {
                "id": str(user_id),
                "name": full_name,
                "email": db_email,
                "role": _from_db_role(db_role),
            },
        }
    except Exception as e:
        return {"status": "failed", "message": "Login failed.", "error": str(e)}
    finally:
        if conn:
            conn.close()