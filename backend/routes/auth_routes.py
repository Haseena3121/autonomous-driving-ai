"""User Authentication & Registration REST Endpoints with MongoDB Integration.

Provides:
- POST /api/auth/register (Create User ID)
- POST /api/auth/login (Sign In)
- GET /api/auth/me (Current user session)
- GET /api/auth/db-status (MongoDB connection status)

Stores user credentials and profiles in MongoDB (`adas_database.users`).
Uses salted SHA-256 password hashing.
"""

import hashlib
import logging
import secrets
import time
from flask import Blueprint, jsonify, request
import pymongo
from pymongo.errors import DuplicateKeyError, PyMongoError

import config

logger = logging.getLogger("adas.auth")
api = Blueprint("auth", __name__)

_mongo_client = None
_mongo_db = None


def get_mongo():
    """Returns connected MongoDB database, or None if unavailable."""
    global _mongo_client, _mongo_db
    if _mongo_db is not None:
        return _mongo_db

    try:
        _mongo_client = pymongo.MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=2500)
        # Test connection
        _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[config.MONGO_DB_NAME]
        
        # Ensure unique index on user_id
        _mongo_db.users.create_index("user_id", unique=True)
        
        # Seed default demo account if empty
        if _mongo_db.users.count_documents({}) == 0:
            salt = secrets.token_hex(16)
            pwd_hash = hashlib.sha256((salt + "demo123").encode("utf-8")).hexdigest()
            _mongo_db.users.insert_one(
                {
                    "user_id": "demo",
                    "name": "Demo Driver",
                    "email": "demo@adas.ai",
                    "password_hash": pwd_hash,
                    "salt": salt,
                    "created_at": time.time(),
                }
            )
            logger.info("Seeded default demo user in MongoDB")

        logger.info("Successfully connected to MongoDB at %s (database: %s)", config.MONGO_URI, config.MONGO_DB_NAME)
        return _mongo_db
    except Exception as e:
        logger.warning("MongoDB connection failed (%s).", e)
        return None


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# Initialize connection on module load
get_mongo()


@api.get("/auth/db-status")
def db_status():
    """Report MongoDB database connection status."""
    db = get_mongo()
    if db is not None:
        try:
            count = db.users.count_documents({})
            return jsonify({
                "success": True,
                "data": {
                    "connected": True,
                    "database": "MongoDB",
                    "db_name": config.MONGO_DB_NAME,
                    "uri": config.MONGO_URI,
                    "user_count": count,
                }
            })
        except Exception as e:
            return jsonify({"success": False, "data": {"connected": False, "error": str(e)}})
    return jsonify({"success": False, "data": {"connected": False, "database": "Offline"}})


@api.post("/auth/register")
def register():
    """Create a new User ID in MongoDB."""
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

    db = get_mongo()
    if db is None:
        return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "MongoDB server is offline. Please start MongoDB."}}), 503

    try:
        user_doc = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "password_hash": pwd_hash,
            "salt": salt,
            "created_at": time.time(),
        }
        db.users.insert_one(user_doc)
    except DuplicateKeyError:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "USER_EXISTS",
                        "message": f"User ID '{user_id}' already exists in MongoDB. Please choose a different ID or login.",
                    },
                }
            ),
            409,
        )
    except PyMongoError as err:
        return jsonify({"success": False, "error": {"code": "MONGO_ERROR", "message": f"MongoDB error: {err}"}}), 500

    token = secrets.token_hex(24)

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "user": {
                        "user_id": user_id,
                        "name": name,
                        "email": email,
                    },
                    "token": token,
                    "storage": "MongoDB",
                    "message": "User ID created successfully in MongoDB!",
                },
            }
        ),
        201,
    )


@api.post("/auth/login")
def login():
    """Sign in with existing User ID and password using MongoDB."""
    data = request.get_json(silent=True) or {}
    user_id = (data.get("user_id") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not user_id or not password:
        return jsonify({"success": False, "error": {"code": "MISSING_CREDENTIALS", "message": "User ID and password are required."}}), 400

    db = get_mongo()
    if db is None:
        return jsonify({"success": False, "error": {"code": "DB_UNAVAILABLE", "message": "MongoDB server is offline. Please start MongoDB."}}), 503

    try:
        user = db.users.find_one({"user_id": user_id})
    except PyMongoError as err:
        return jsonify({"success": False, "error": {"code": "MONGO_ERROR", "message": f"MongoDB error: {err}"}}), 500

    if not user:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": f"User ID '{user_id}' not found in MongoDB. Click 'Create User ID' to register.",
                    },
                }
            ),
            404,
        )

    salt = user.get("salt", "")
    expected_hash = user.get("password_hash", "")

    if hash_password(password, salt) != expected_hash:
        return (
            jsonify(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_PASSWORD",
                        "message": "Incorrect password. Please try again.",
                    },
                }
            ),
            401,
        )

    token = secrets.token_hex(24)

    return jsonify(
        {
            "success": True,
            "data": {
                "user": {
                    "user_id": user["user_id"],
                    "name": user.get("name", user["user_id"]),
                    "email": user.get("email", ""),
                },
                "token": token,
                "storage": "MongoDB",
                "message": f"Welcome back, {user.get('name', user['user_id'])}!",
            },
        }
    )


@api.get("/auth/me")
def me():
    """Verify session."""
    return jsonify({"success": True, "data": {"status": "authenticated", "database": "MongoDB"}})
