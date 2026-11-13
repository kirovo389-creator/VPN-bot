"""FastAPI companion API. Telegram WebApp initData is verified before user data is returned."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import add_device, activate_demo, delete_device, get_account, init_db, upsert_user

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
ALLOWED_ORIGINS = [x.strip() for x in os.getenv(
    "ALLOWED_ORIGINS",
    "https://kirovo389-creator.github.io,http://localhost:8000",
).split(",") if x.strip()]

app = FastAPI(title="VPN Control Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data"],
)


class DeviceInput(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    platform: str = Field(min_length=2, max_length=24)


def telegram_user_id(init_data: str) -> tuple[int, dict]:
    if not BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram authentication is not configured.")
    if not init_data:
        raise HTTPException(status_code=401, detail="Open this page from the Telegram bot.")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing Telegram signature.")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret_key = hmac.new(BOT_TOKEN.encode(), b"WebAppData", hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature.")

    try:
        auth_date = int(values.get("auth_date", "0"))
        if abs(int(time.time()) - auth_date) > 86400:
            raise HTTPException(status_code=401, detail="Telegram session has expired.")
        user = json.loads(values["user"])
        user_id = int(user["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid Telegram user data.")

    upsert_user(user_id, user.get("username"), user.get("first_name"))
    return user_id, user


def current_user(x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data")) -> int:
    user_id, _ = telegram_user_id(x_telegram_init_data)
    return user_id


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "vpn-control-demo-api", "demo_mode": DEMO_MODE}


@app.get("/api/account")
def account(user_id: int = Depends(current_user)) -> dict:
    return get_account(user_id)


@app.post("/api/devices")
def create_device(payload: DeviceInput, user_id: int = Depends(current_user)) -> dict:
    try:
        device = add_device(user_id, payload.name, payload.platform)
        return {"ok": True, "device": device, "account": get_account(user_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/devices/{device_id}")
def remove_device(device_id: str, user_id: int = Depends(current_user)) -> dict:
    removed = delete_device(user_id, device_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Device not found.")
    return {"ok": True, "account": get_account(user_id)}


@app.post("/api/demo/activate")
def activate_demo_subscription(user_id: int = Depends(current_user)) -> dict:
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo activation is disabled.")
    activate_demo(user_id)
    return {"ok": True, "account": get_account(user_id), "notice": "Simulation only; no payment was taken."}


@app.get("/api/nodes")
def nodes() -> dict:
    return {
        "demo": True,
        "nodes": [
            {"id": "de", "country": "Германия", "flag": "🇩🇪", "status": "preview"},
            {"id": "nl", "country": "Нидерланды", "flag": "🇳🇱", "status": "preview"},
            {"id": "fi", "country": "Финляндия", "flag": "🇫🇮", "status": "preview"},
            {"id": "pl", "country": "Польша", "flag": "🇵🇱", "status": "preview"},
            {"id": "us", "country": "США", "flag": "🇺🇸", "status": "preview"},
        ],
    }
