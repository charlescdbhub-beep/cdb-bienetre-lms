#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LMS Bien-Être — auth.py (fork Rosémary)
Bcrypt + sessions SQLite (tokens opaques httpOnly).
"""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

import db

SESSION_DAYS = 14
COOKIE = "bienetre_session"


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), pw_hash.encode("utf-8"))
    except ValueError:
        return False


def create_session(conn, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.ex(conn, "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
          (token, user_id, db.now(), (now + timedelta(days=SESSION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    return token


def destroy_session(conn, token: str):
    db.ex(conn, "DELETE FROM sessions WHERE token = ?", (token,))


def user_from_token(conn, token: str):
    if not token:
        return None
    row = db.q1(conn, """
        SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ?""", (token, db.now()))
    return row


def get_user(conn, user_id: str):
    return db.q1(conn, "SELECT * FROM users WHERE id = ?", (user_id,))


def sanitize_user(u):
    """Retire le hash du mot de passe d'un Row utilisateur."""
    if u is None:
        return None
    d = dict(u)
    d.pop("password_hash", None)
    return d