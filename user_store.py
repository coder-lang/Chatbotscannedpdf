"""
services/user_store.py
=======================
Simple JSON-based user registry (swap for CosmosDB/Postgres in production).

Stores: { email → { user_id, name, hashed_password } }
"""
import json
import os
from typing import Optional

from core.security import hash_password, verify_password, new_user_id

_USER_DB_FILE = "user_store/users.json"


def _load() -> dict:
    os.makedirs(os.path.dirname(_USER_DB_FILE), exist_ok=True)
    if not os.path.exists(_USER_DB_FILE):
        return {}
    with open(_USER_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(db: dict) -> None:
    with open(_USER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def register_user(name: str, email: str, password: str) -> Optional[str]:
    """
    Create a new user. Returns the new user_id, or None if email already taken.
    """
    db = _load()
    if email in db:
        return None                 # email already registered

    user_id = new_user_id()
    db[email] = {
        "user_id":         user_id,
        "name":            name,
        "hashed_password": hash_password(password),
    }
    _save(db)
    return user_id


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns user record dict or None if invalid.
    """
    db = _load()
    record = db.get(email)
    if not record:
        return None
    if not verify_password(password, record["hashed_password"]):
        return None
    return record   # { user_id, name, hashed_password }
