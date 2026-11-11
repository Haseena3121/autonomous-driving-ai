"""User Authentication & Registration REST Endpoints.

Provides:
- POST /api/auth/register (Create User ID)
- POST /api/auth/login (Sign In)
- GET  /api/auth/me (Current user session)
- GET  /api/auth/db-status (Database connection status)

Storage strategy (automatic, no config change needed):
  1. MongoDB  — used when ADAS_MONGO_URI points to a running server.
  2. SQLite   — automatic fallback when MongoDB is offline or not installed.
                Uses backend/users.db (zero-config, works on Render free tier).

Both backends store the same fields and return identical JSON responses.
Passwords are always salted SHA-256 hashed.
"""

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

import config

logger = logging.getLogger("adas.auth")
api = Blueprint("auth", __name__)

# ------------------------------------------------------------------ helpers --
_salt_lock = threading.Lock()


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# ================================================================ MongoDB ===
_mongo_client = None
_mongo_db = None


def get_mongo():
    """Returns connected MongoDB database, or None if unavailable."""
    global _mongo_client, _mongo_db
    if _mongo_db is not None:
        return _mongo_db
    try:
        import pymongo
        from pymongo.errors import PyMongoError

        _mongo_client = pymongo.MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=2500)
        _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[config.MONGO_DB_NAME]
        _mongo_db.users.create_index("user_id", unique=True)

        if _mongo_db.users.count_documents({}) == 0:
            salt = secrets.token_hex(16)
            _mongo_db.users.insert_one(
                {
                    "user_id": "demo",
                    "name": "Demo Driver",
                    "email": "demo@adas.ai",
                    "password_hash": hash_password("demo123", salt),
                    "salt": salt,
                    "created_at": time.time(),
                }
            )
            logger.info("Seeded default demo user in MongoDB")
        logger.info("Connected to MongoDB at %s (database: %s)", config.MONGO_URI, config.MONGO_DB_NAME)
        return _mongo_db
    except Exception as e:
        logger.info("MongoDB not available (%s) — will use SQLite fallback.", e)
        return None


# ================================================================= SQLite ===
_sqlite_conn = None
_sqlite_lock = threading.Lock()
_SQLITE_PATH = str(Path(config.BASE_DIR) / "users.db")


def get_sqlite():
    """Returns a SQLite connection, or None if SQLite fails."""
    global _sqlite_conn
    if _sqlite_conn is not None:
        return _sqlite_conn
    try:
        _sqlite_conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        c = _sqlite_conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at REAL
            )
            """
        )
        _sqlite_conn.commit()

        # Seed demo user if empty
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            salt = secrets.token_hex(16)
            c.execute(
                "INSERT INTO users (user_id, name, email, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("demo", "Demo Driver", "demo@adas.ai", hash_password("demo123", salt), salt, time.time()),
            )
            _sqlite_conn.commit()
            logger.info("Seeded default demo user in SQLite")
        logger.info("Using SQLite for auth (%s)", _SQLITE_PATH)
        return _sqlite_conn
    except Exception as e:
        logger.error("SQLite fallback failed: %s", e)
        return None


def _init_storage():
    """Pick MongoDB, or fall back to SQLite."""
    if get_mongo() is not None:
        return "MongoDB"
    if get_sqlite() is not None:
        return "SQLite"
    return None


_storage = _init_storage()


# ============================================================ db-status ======
@api.get("/auth/db-status")
def db_status():
    """Report database connection status."""
    if _storage == "MongoDB":
        try:
            count = get_mongo().users.count_documents({})
            return jsonify({
                "success": True,
                "data": {"connected": True, "database": "MongoDB", "db_name": config.MONGO_DB_NAME, "user_count": count},
            })
        except Exception as e:
            return jsonify({"success": False, "data": {"connected": False, "error": str(e)}})
    if _storage == "SQLite":
        try:
            conn = get_sqlite()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            count = c.fetchone()[0]
            return jsonify({
                "success": True,
                "data": {"connected": True, "database": "SQLite", "user_count": count},
            })
        except Exception as e:
            return jsonify({"success": False, "data": {"connected": False, "error": str(e)}})
    return jsonify({"success": False, "data": {"connected": False, "database": "Offline"}})


# ============================================================ register =======
@api.post("/auth/register")
def register():
    """Create a new User ID."""
    data = request.get_json(silent=True) or {}
    user_id = (data.get("user_id") or "").strip().lower()
    password = (data.get("password") or "").strip()
    name = (data.get("name") or "").strip() or user_id
    email = (data.get("email") or "").strip()

    if not user_id:
        return jsonify({"success": False, "error": {"code": "INVALID_USER_ID", "message": "User ID is required."}}), 400
    if len(user_id) < 3:
        return jsonify({"success": False, "error": {"code": "USER_ID_TOO_SHORT", "message": "User ID must be at least 3 characters."}}), 400
    if not password:
        return jsonify({"success": False, "error": {"code": "INVALID_PASSWORD", "message": "Password is required."}}), 400
    if len(password) < 4:
        return jsonify({"success": False, "error": {"code": "PASSWORD_TOO_SHORT", "message": "Password must be at least 4 characters."}}), 400

    salt = secrets.token_hex(16)
    pwd_hash = hash_password(password, salt)

    # --- MongoDB path ---
    if _storage == "MongoDB":
        from pymongo.errors import DuplicateKeyError, PyMongoError

        db = get_mongo()
        if db is None:
            return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "Database is offline."}}), 503
        try:
            db.users.insert_one(
                {
                    "user_id": user_id, "name": name, "email": email,
                    "password_hash": pwd_hash, "salt": salt, "created_at": time.time(),
                }
            )
        except DuplicateKeyError:
            return jsonify({"success": False, "error": {"code": "USER_EXISTS", "message": f"User ID '{user_id}' already exists. Please choose a different ID or login."}}), 409
        except PyMongoError as err:
            return jsonify({"success": False, "error": {"code": "MONGO_ERROR", "message": f"MongoDB error: {err}"}}), 500

    # --- SQLite path ---
    elif _storage == "SQLite":
        conn = get_sqlite()
        if conn is None:
            return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "Database is offline."}}), 503
        with _sqlite_lock:
            try:
                conn.execute(
                    "INSERT INTO users (user_id, name, email, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, name, email, pwd_hash, salt, time.time()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return jsonify({"success": False, "error": {"code": "USER_EXISTS", "message": f"User ID '{user_id}' already exists. Please choose a different ID or login."}}), 409
            except Exception as err:
                return jsonify({"success": False, "error": {"code": "DB_ERROR", "message": f"Database error: {err}"}}), 500

    else:
        return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "No database available."}}), 503

    token = secrets.token_hex(24)
    return jsonify({
        "success": True,
        "data": {
            "user": {"user_id": user_id, "name": name, "email": email},
            "token": token,
            "storage": _storage,
            "message": "User ID created successfully!",
        },
    }), 201


# ============================================================ login ==========
@api.post("/auth/login")
def login():
    """Sign in with existing User ID and password."""
    data = request.get_json(silent=True) or {}
    user_id = (data.get("user_id") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not user_id or not password:
        return jsonify({"success": False, "error": {"code": "MISSING_CREDENTIALS", "message": "User ID and password are required."}}), 400

    user = None

    # --- MongoDB path ---
    if _storage == "MongoDB":
        from pymongo.errors import PyMongoError

        db = get_mongo()
        if db is None:
            return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "Database is offline."}}), 503
        try:
            user = db.users.find_one({"user_id": user_id})
        except PyMongoError as err:
            return jsonify({"success": False, "error": {"code": "MONGO_ERROR", "message": f"MongoDB error: {err}"}}), 500

        if not user:
            return jsonify({"success": False, "error": {"code": "USER_NOT_FOUND", "message": f"User ID '{user_id}' not found. Click 'Create User ID' to register."}}), 404
        salt = user.get("salt", "")
        expected_hash = user.get("password_hash", "")

    # --- SQLite path ---
    elif _storage == "SQLite":
        conn = get_sqlite()
        if conn is None:
            return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "Database is offline."}}), 503
        with _sqlite_lock:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return jsonify({"success": False, "error": {"code": "USER_NOT_FOUND", "message": f"User ID '{user_id}' not found. Click 'Create User ID' to register."}}), 404
        salt = row["salt"]
        expected_hash = row["password_hash"]
        user = {"user_id": row["user_id"], "name": row["name"] or row["user_id"], "email": row["email"]}

    else:
        return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "No database available."}}), 503

    if hash_password(password, salt) != expected_hash:
        return jsonify({"success": False, "error": {"code": "INVALID_PASSWORD", "message": "Incorrect password. Please try again."}}), 401

    token = secrets.token_hex(24)
    name = user.get("name", user.get("user_id", user_id)) if isinstance(user, dict) else user_id
    return jsonify({
        "success": True,
        "data": {
            "user": {
                "user_id": user.get("user_id", user_id) if isinstance(user, dict) else user_id,
                "name": name,
                "email": user.get("email", "") if isinstance(user, dict) else "",
            },
            "token": token,
            "storage": _storage,
            "message": f"Welcome back, {name}!",
        },
    })


# ============================================================ me =============
@api.get("/auth/me")
def me():
    """Verify session."""
    return jsonify({"success": True, "data": {"status": "authenticated", "database": _storage}})
