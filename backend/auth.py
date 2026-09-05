"""Password hashing and signed bearer tokens (stdlib only)."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import db

TOKEN_TTL = 60 * 60 * 24 * 14  # two weeks
_ITERATIONS = 240_000


def _secret() -> bytes:
    env = os.environ.get("QRIP_SECRET")
    if env:
        return env.encode()
    path = os.path.join(db.DATA_DIR, "secret.key")
    if not os.path.exists(path):
        os.makedirs(db.DATA_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip().encode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return "pbkdf2$" + str(_ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user_id: str) -> str:
    payload = json.dumps({"sub": user_id, "exp": int(time.time()) + TOKEN_TTL},
                         separators=(",", ":")).encode()
    body = _b64(payload)
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return body + "." + _b64(signature)


def read_token(token: str):
    try:
        body, signature = token.split(".")
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")
    except Exception:
        return None


def user_from_header(header: str):
    if not header or not header.lower().startswith("bearer "):
        return None
    user_id = read_token(header.split(" ", 1)[1].strip())
    if not user_id:
        return None
    return db.q1("SELECT * FROM users WHERE id=?", (user_id,))


def register(email: str, password: str, name: str):
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email is required.")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters.")
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise ValueError("That email is already registered.")
    # the first account to be created owns the workspace
    first = db.q1("SELECT COUNT(*) AS n FROM users")["n"] == 0
    user = {
        "id": db.new_id(),
        "email": email,
        "name": (name or email.split("@")[0]).strip(),
        "password_hash": hash_password(password),
        "role": "owner" if first else "researcher",
        "created_at": db.now(),
        "last_login_at": db.now(),
    }
    db.insert("users", user)
    db.audit(None, user["id"], "auth.register", "user", user["id"], {"email": email})
    return db.q1("SELECT * FROM users WHERE id=?", (user["id"],))


def login(email: str, password: str):
    user = db.q1("SELECT * FROM users WHERE email=?", ((email or "").strip().lower(),))
    if not user or not verify_password(password or "", user["password_hash"]):
        raise ValueError("Incorrect email or password.")
    db.ex("UPDATE users SET last_login_at=? WHERE id=?", (db.now(), user["id"]))
    db.audit(None, user["id"], "auth.login", "user", user["id"], {})
    return user
