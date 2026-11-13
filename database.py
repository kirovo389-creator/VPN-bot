"""Shared SQLite storage for the demo bot and API. Production should use PostgreSQL."""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("DB_PATH", "vpn_demo.sqlite3")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now_utc()).isoformat()


def connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                telegram_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
                amount_minor INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def upsert_user(telegram_id: int, username: str | None = None, first_name: str | None = None) -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO users(telegram_id, username, first_name, created_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
              username=COALESCE(excluded.username, users.username),
              first_name=COALESCE(excluded.first_name, users.first_name)
            """,
            (telegram_id, username, first_name, iso()),
        )


def get_account(telegram_id: int) -> dict[str, Any]:
    with connect() as db:
        sub = db.execute(
            "SELECT plan, status, expires_at, is_demo FROM subscriptions WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        devices = db.execute(
            "SELECT id, name, platform, created_at, last_seen FROM devices WHERE telegram_id=? ORDER BY created_at",
            (telegram_id,),
        ).fetchall()
    return {
        "telegram_id": telegram_id,
        "subscription": dict(sub) if sub else None,
        "devices": [dict(row) for row in devices],
        "device_limit": 5,
    }


def activate_demo(telegram_id: int) -> dict[str, Any]:
    expires = now_utc() + timedelta(days=30)
    with connect() as db:
        db.execute(
            """
            INSERT INTO subscriptions(telegram_id, plan, status, expires_at, is_demo)
            VALUES(?, 'Demo Premium', 'active', ?, 1)
            ON CONFLICT(telegram_id) DO UPDATE SET
              plan='Demo Premium', status='active', expires_at=excluded.expires_at, is_demo=1
            """,
            (telegram_id, expires.isoformat()),
        )
    return get_account(telegram_id)


def add_device(telegram_id: int, name: str, platform: str) -> dict[str, Any]:
    if len(name.strip()) < 2 or len(name) > 40:
        raise ValueError("Название устройства должно быть от 2 до 40 символов.")
    if len(platform) > 24:
        raise ValueError("Слишком длинное название платформы.")
    device_id = uuid.uuid4().hex[:12]
    with connect() as db:
        count = db.execute("SELECT COUNT(*) FROM devices WHERE telegram_id=?", (telegram_id,)).fetchone()[0]
        if count >= 5:
            raise ValueError("Достигнут лимит в 5 устройств.")
        db.execute(
            "INSERT INTO devices(id, telegram_id, name, platform, created_at) VALUES(?, ?, ?, ?, ?)",
            (device_id, telegram_id, name.strip(), platform.strip(), iso()),
        )
    return {"id": device_id, "name": name.strip(), "platform": platform.strip()}


def delete_device(telegram_id: int, device_id: str) -> bool:
    with connect() as db:
        cur = db.execute(
            "DELETE FROM devices WHERE id=? AND telegram_id=?",
            (device_id, telegram_id),
        )
        return cur.rowcount > 0


def create_demo_payment(telegram_id: int) -> str:
    payment_id = uuid.uuid4().hex[:12]
    with connect() as db:
        db.execute(
            """
            INSERT INTO payments(id, telegram_id, amount_minor, currency, status, provider, created_at)
            VALUES(?, ?, 0, 'EUR', 'demo_success', 'simulator', ?)
            """,
            (payment_id, telegram_id, iso()),
        )
    return payment_id
