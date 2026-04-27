from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .settings import settings


ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_ADMIN, ROLE_VIEWER}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 240_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64_encode(salt)}${_b64_encode(digest)}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64_decode(salt_raw)
        expected = _b64_decode(digest_raw)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(digest, expected)


def _clean_username(username: str) -> str:
    value = str(username or "").strip()
    if len(value) < 2:
        raise ValueError("用户名至少需要 2 个字符")
    if len(value) > 40:
        raise ValueError("用户名不能超过 40 个字符")
    if any(ch.isspace() for ch in value):
        raise ValueError("用户名不能包含空格")
    return value


def _clean_role(role: str) -> str:
    value = str(role or ROLE_VIEWER).strip()
    if value not in VALID_ROLES:
        raise ValueError("角色只能是 admin 或 viewer")
    return value


def _clean_password(password: str) -> str:
    value = str(password or "")
    if len(value) < 6:
        raise ValueError("密码至少需要 6 个字符")
    return value


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "display_name": user.get("display_name") or user.get("username"),
        "role": user.get("role", ROLE_VIEWER),
        "is_active": bool(user.get("is_active", True)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "last_login_at": user.get("last_login_at"),
    }


def _public_login_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": event.get("id"),
        "user_id": event.get("user_id"),
        "username": event.get("username"),
        "display_name": event.get("display_name") or event.get("username"),
        "role": event.get("role", ROLE_VIEWER),
        "logged_at": event.get("logged_at"),
        "ip_address": event.get("ip_address") or "",
        "user_agent": event.get("user_agent") or "",
    }


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def _bootstrap_store(self) -> dict[str, Any]:
        now = _utc_now()
        username = _clean_username(settings.bootstrap_admin_username)
        password = _clean_password(settings.bootstrap_admin_password)
        return {
            "version": 1,
            "users": [
                {
                    "id": uuid.uuid4().hex,
                    "username": username,
                    "display_name": settings.bootstrap_admin_display_name.strip() or username,
                    "role": ROLE_ADMIN,
                    "is_active": True,
                    "password_hash": _hash_password(password),
                    "created_at": now,
                    "updated_at": now,
                    "last_login_at": None,
                }
            ],
            "login_events": [],
        }

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            store = self._bootstrap_store()
            self._write_unlocked(store)
            return store
        try:
            store = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"用户存储文件损坏: {self.path}") from exc
        if not isinstance(store, dict):
            store = {"version": 1, "users": []}
        users = store.get("users")
        if not isinstance(users, list) or not users:
            store = self._bootstrap_store()
            self._write_unlocked(store)
        if not isinstance(store.get("login_events"), list):
            store["login_events"] = []
        return store

    def _write_unlocked(self, store: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(store, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(self.path.parent),
            delete=False,
        ) as tmp:
            tmp.write(payload)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)

    def _find_user(self, users: list[dict[str, Any]], user_id: str) -> dict[str, Any] | None:
        for user in users:
            if str(user.get("id")) == str(user_id):
                return user
        return None

    def _find_by_username(self, users: list[dict[str, Any]], username: str) -> dict[str, Any] | None:
        username_key = username.casefold()
        for user in users:
            if str(user.get("username", "")).casefold() == username_key:
                return user
        return None

    def _assert_active_admin_remains(self, users: list[dict[str, Any]]) -> None:
        has_active_admin = any(
            user.get("role") == ROLE_ADMIN and bool(user.get("is_active", True))
            for user in users
        )
        if not has_active_admin:
            raise ValueError("至少需要保留一个启用的管理员")

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock:
            store = self._read_unlocked()
            return [_public_user(user) for user in store.get("users", [])]

    def get_public_user(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            store = self._read_unlocked()
            user = self._find_user(store.get("users", []), user_id)
            if not user:
                return None
            return _public_user(user)

    def list_login_events(self, user_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(1000, int(limit or 100)))
        target_user_id = str(user_id or "").strip()
        with self._lock:
            store = self._read_unlocked()
            events = store.get("login_events", [])
            if target_user_id:
                events = [event for event in events if str(event.get("user_id")) == target_user_id]
            events = sorted(events, key=lambda event: str(event.get("logged_at") or ""), reverse=True)
            return [_public_login_event(event) for event in events[:limit]]

    def authenticate(
        self,
        username: str,
        password: str,
        login_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        username = str(username or "").strip()
        password = str(password or "")
        login_context = login_context or {}
        with self._lock:
            store = self._read_unlocked()
            users = store.get("users", [])
            user = self._find_by_username(users, username)
            if not user or not bool(user.get("is_active", True)):
                return None
            if not _verify_password(password, str(user.get("password_hash", ""))):
                return None
            logged_at = _utc_now()
            user["last_login_at"] = logged_at
            user["updated_at"] = user["updated_at"] if user.get("updated_at") else _utc_now()
            events = store.setdefault("login_events", [])
            events.append(
                {
                    "id": uuid.uuid4().hex,
                    "user_id": user.get("id"),
                    "username": user.get("username"),
                    "display_name": user.get("display_name") or user.get("username"),
                    "role": user.get("role", ROLE_VIEWER),
                    "logged_at": logged_at,
                    "ip_address": str(login_context.get("ip_address") or ""),
                    "user_agent": str(login_context.get("user_agent") or "")[:500],
                }
            )
            if len(events) > settings.auth_login_event_limit:
                store["login_events"] = events[-settings.auth_login_event_limit :]
            self._write_unlocked(store)
            return _public_user(user)

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        role: str = ROLE_VIEWER,
        is_active: bool = True,
    ) -> dict[str, Any]:
        username = _clean_username(username)
        password = _clean_password(password)
        role = _clean_role(role)
        now = _utc_now()
        with self._lock:
            store = self._read_unlocked()
            users = store.get("users", [])
            if self._find_by_username(users, username):
                raise ValueError("用户名已存在")
            user = {
                "id": uuid.uuid4().hex,
                "username": username,
                "display_name": str(display_name or "").strip() or username,
                "role": role,
                "is_active": bool(is_active),
                "password_hash": _hash_password(password),
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            }
            users.append(user)
            self._assert_active_admin_remains(users)
            self._write_unlocked(store)
            return _public_user(user)

    def update_user(self, user_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            store = self._read_unlocked()
            users = store.get("users", [])
            user = self._find_user(users, user_id)
            if not user:
                raise ValueError("用户不存在")

            if "display_name" in changes:
                display_name = str(changes.get("display_name") or "").strip()
                user["display_name"] = display_name or user.get("username")
            if "role" in changes and changes.get("role") is not None:
                user["role"] = _clean_role(str(changes["role"]))
            if "is_active" in changes and changes.get("is_active") is not None:
                user["is_active"] = bool(changes["is_active"])
            if "password" in changes and changes.get("password"):
                user["password_hash"] = _hash_password(_clean_password(str(changes["password"])))

            user["updated_at"] = _utc_now()
            self._assert_active_admin_remains(users)
            self._write_unlocked(store)
            return _public_user(user)

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            store = self._read_unlocked()
            users = store.get("users", [])
            next_users = [user for user in users if str(user.get("id")) != str(user_id)]
            if len(next_users) == len(users):
                raise ValueError("用户不存在")
            self._assert_active_admin_remains(next_users)
            store["users"] = next_users
            self._write_unlocked(store)


auth_store = UserStore(settings.auth_store_path)


def create_session_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "iat": now,
        "exp": now + settings.auth_session_hours * 3600,
        "nonce": secrets.token_urlsafe(12),
    }
    body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(settings.auth_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
    return f"{body}.{_b64_encode(signature.digest())}"


def verify_session_token(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(settings.auth_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256)
        if not secrets.compare_digest(_b64_encode(expected.digest()), signature):
            return None
        payload = json.loads(_b64_decode(body).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    user = auth_store.get_public_user(str(payload.get("sub", "")))
    if not user or not user.get("is_active"):
        return None
    return user


def _request_token(request: Request) -> str:
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return ""


async def get_current_user(request: Request) -> dict[str, Any]:
    token = _request_token(request)
    user = verify_session_token(token) if token else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    return user


async def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return user
