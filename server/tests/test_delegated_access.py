"""
Tests for client-authorized read-only admin view access.

Needs a throwaway PostgreSQL database (the schema uses Postgres features):
    TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5433/creditdatawatch_test
Run from the server/ folder:
    venv/Scripts/python -m pytest tests/test_delegated_access.py -v
Skipped automatically if the test database is unreachable.
"""
import os
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import Request
from fastapi import HTTPException

from app.database import Base, get_db
from app.main import app
from app.middleware import delegated_access as ro_middleware
from app.middleware.rate_limit import request_tracker
from app.models import User, UserRole
from app.models.admin_access import AdminAccessCode, AdminAccessGrant, DelegatedAccessAudit
from app.services import delegated_access_service as das
from app.services.notification_service import NotificationService
from app.utils import create_access_token, hash_password

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5433/creditdatawatch_test"
)
API = "/api/v1"
HEADER = das.DELEGATION_HEADER


# ------------------------------------------------------------------ fixtures

@pytest.fixture
async def session_factory(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # pragma: no cover - environment dependent
        await engine.dispose()
        pytest.skip(f"Test database not available: {e}")

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(ro_middleware, "session_factory", factory)
    monkeypatch.setattr(das, "_tables_ready", False)
    # Don't try to send real emails from tests
    monkeypatch.setattr(NotificationService, "_send_email_background", staticmethod(_noop_email))
    request_tracker.clear()

    yield factory

    app.dependency_overrides.pop(get_db, None)
    request_tracker.clear()
    await engine.dispose()


async def _noop_email(*args, **kwargs):
    return None


@pytest.fixture
async def http(session_factory):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _make_user(factory, role: UserRole, name: str) -> User:
    async with factory() as db:
        user = User(
            id=str(uuid.uuid4()),
            name=name,
            email=f"{name}-{uuid.uuid4().hex[:8]}@test.local",
            password_hash=hash_password("Passw0rd!"),
            role=role,
            status="ACTIVE",
            phone="+919800000000",
            gstin="29ABCDE1234F1Z5",
            company_name=f"{name} Pvt Ltd",
            is_active=True,
            subscription_status="ACTIVE",
        )
        db.add(user)
        await db.commit()
        return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


@pytest.fixture
async def people(session_factory):
    return {
        "client": await _make_user(session_factory, UserRole.COMPANY_ADMIN, "client"),
        "ops": await _make_user(session_factory, UserRole.OPERATION, "ops"),
        "ops2": await _make_user(session_factory, UserRole.OPERATION, "ops2"),
        "super": await _make_user(session_factory, UserRole.MASTER_ADMIN, "super"),
    }


async def _generate(http, client, hours=24) -> dict:
    r = await http.post(f"{API}/access-grants/codes", json={"duration_hours": hours}, headers=_auth(client))
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _redeem(http, admin, code):
    return await http.post(f"{API}/admin/client-access/redeem", json={"code": code}, headers=_auth(admin))


async def _grant_for(http, people, admin_key="ops") -> str:
    data = await _generate(http, people["client"])
    r = await _redeem(http, people[admin_key], data["code"])
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


# ------------------------------------------------------------------ code expiry

async def test_code_expires_if_not_redeemed_in_time(http, people, session_factory):
    data = await _generate(http, people["client"])
    async with session_factory() as db:
        code = await db.get(AdminAccessCode, data["code_id"])
        code.redeem_by = das._now() - timedelta(seconds=1)
        await db.commit()

    r = await _redeem(http, people["ops"], data["code"])
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_CODE"


async def test_only_hash_of_code_is_stored(http, people, session_factory):
    data = await _generate(http, people["client"])
    async with session_factory() as db:
        code = await db.get(AdminAccessCode, data["code_id"])
    assert data["code"] not in (code.code_hash or "")
    assert code.code_hash == das.hash_code(data["code"])


async def test_grant_stops_working_after_expiry(http, people, session_factory):
    grant_id = await _grant_for(http, people)
    async with session_factory() as db:
        grant = await db.get(AdminAccessGrant, grant_id)
        grant.expires_at = das._now() - timedelta(seconds=1)
        await db.commit()

    r = await http.get(f"{API}/user/profile", headers={**_auth(people["ops"]), HEADER: grant_id})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "DELEGATION_ENDED"


# ------------------------------------------------------------------ single use

async def test_code_is_single_use_and_bound_to_redeeming_admin(http, people):
    data = await _generate(http, people["client"])
    first = await _redeem(http, people["ops"], data["message"])  # whole pasted message works
    assert first.status_code == 200, first.text
    grant_id = first.json()["data"]["id"]

    again = await _redeem(http, people["super"], data["code"])
    assert again.status_code == 400
    assert again.json()["detail"]["code"] == "INVALID_CODE"

    # The grant is bound to the admin who redeemed it
    other = await http.get(f"{API}/user/profile", headers={**_auth(people["ops2"]), HEADER: grant_id})
    assert other.status_code == 403


async def test_delegated_read_returns_client_data(http, people):
    grant_id = await _grant_for(http, people)
    r = await http.get(f"{API}/user/profile", headers={**_auth(people["ops"]), HEADER: grant_id})
    assert r.status_code == 200, r.text
    assert people["client"].email in r.text
    assert people["ops"].email not in r.text


async def test_clients_cannot_redeem_codes(http, people):
    data = await _generate(http, people["client"])
    r = await _redeem(http, people["client"], data["code"])
    assert r.status_code == 403


# ------------------------------------------------------------------ revocation

async def test_revocation_takes_effect_on_next_request(http, people):
    grant_id = await _grant_for(http, people)
    headers = {**_auth(people["ops"]), HEADER: grant_id}
    assert (await http.get(f"{API}/user/profile", headers=headers)).status_code == 200

    r = await http.post(f"{API}/access-grants/{grant_id}/revoke", headers=_auth(people["client"]))
    assert r.status_code == 200

    r = await http.get(f"{API}/user/profile", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "DELEGATION_ENDED"


async def test_super_admin_can_revoke_any_grant(http, people):
    grant_id = await _grant_for(http, people)
    r = await http.post(f"{API}/admin/client-access/grants/{grant_id}/revoke", headers=_auth(people["super"]))
    assert r.status_code == 200
    r = await http.get(f"{API}/user/profile", headers={**_auth(people["ops"]), HEADER: grant_id})
    assert r.status_code == 403


# ------------------------------------------------------------------ read-only

@pytest.mark.parametrize("method,path", [
    ("POST", "/purchase-orders"),
    ("PUT", "/user/profile"),
    ("DELETE", "/purchase-orders/some-id"),
    ("PATCH", "/user/profile"),
    ("POST", "/access-grants/codes"),
    ("GET", "/sales-invoices/next-number"),  # a GET that writes
    ("GET", "/access-grants"),               # grant management is never delegated
])
async def test_write_endpoints_reject_delegated_access(http, people, session_factory, method, path):
    grant_id = await _grant_for(http, people)
    r = await http.request(method, f"{API}{path}", json={}, headers={**_auth(people["ops"]), HEADER: grant_id})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "DELEGATION_READ_ONLY"

    async with session_factory() as db:
        from sqlalchemy import select
        events = (await db.execute(
            select(DelegatedAccessAudit.event).where(DelegatedAccessAudit.grant_id == grant_id)
        )).scalars().all()
    assert das.Events.WRITE_BLOCKED in events


async def test_dependency_blocks_writes_even_without_middleware(people, session_factory):
    """Second layer: resolve_delegation itself rejects writes."""
    async with session_factory() as db:
        grant = AdminAccessGrant(
            id=str(uuid.uuid4()), admin_id=people["ops"].id, client_user_id=people["client"].id,
            granted_at=das._now(), expires_at=das._now() + timedelta(hours=1),
        )
        db.add(grant)
        await db.commit()
        admin = await db.get(User, people["ops"].id)
        scope = {"type": "http", "method": "POST", "path": "/api/v1/purchase-orders", "headers": [],
                 "query_string": b"", "client": ("127.0.0.1", 1), "server": ("test", 80), "scheme": "http"}
        with pytest.raises(HTTPException) as exc:
            await das.resolve_delegation(Request(scope), db, admin, grant.id)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "DELEGATION_READ_ONLY"


# ------------------------------------------------------------------ isolation between admins

async def test_operation_admin_cannot_see_other_admins_grants(http, people):
    grant_id = await _grant_for(http, people, admin_key="ops")

    mine = await http.get(f"{API}/admin/client-access/mine", headers=_auth(people["ops2"]))
    assert mine.status_code == 200
    assert all(g["id"] != grant_id for g in mine.json()["data"]["grants"])

    for path in ("/admin/client-access/all", "/admin/client-access/audit"):
        r = await http.get(f"{API}{path}", headers=_auth(people["ops2"]))
        assert r.status_code == 403, path

    r = await http.get(f"{API}/admin/client-access/grants/{grant_id}", headers=_auth(people["ops2"]))
    assert r.status_code == 404
    r = await http.post(f"{API}/admin/client-access/grants/{grant_id}/revoke", headers=_auth(people["ops2"]))
    assert r.status_code == 404

    # Super Admin sees it
    r = await http.get(f"{API}/admin/client-access/all", headers=_auth(people["super"]))
    assert any(g["id"] == grant_id for g in r.json()["data"]["grants"])


# ------------------------------------------------------------------ audit + notification

async def test_audit_trail_and_client_notification(http, people, session_factory):
    grant_id = await _grant_for(http, people)
    await http.get(f"{API}/user/profile", headers={**_auth(people["ops"]), HEADER: grant_id})

    r = await http.get(f"{API}/admin/client-access/audit?grant_id={grant_id}", headers=_auth(people["super"]))
    events = {i["event"] for i in r.json()["data"]["items"]}
    assert {das.Events.REDEEMED, das.Events.VIEWED} <= events

    r = await http.get(f"{API}/access-grants/activity", headers=_auth(people["client"]))
    texts = [i["text"] for i in r.json()["data"]["items"]]
    assert any("Operation Team viewed your profile" in t for t in texts)

    async with session_factory() as db:
        from sqlalchemy import text
        n = (await db.execute(
            text("SELECT count(*) FROM notifications WHERE user_id = :u AND title = 'Admin view access granted'"),
            {"u": people["client"].id},
        )).scalar()
    assert n == 1


async def test_failed_redeems_are_rate_limited_per_admin(http, people, session_factory, monkeypatch):
    monkeypatch.setattr(das, "MAX_FAILED_REDEEMS", 3)
    for _ in range(3):
        request_tracker.clear()  # isolate the per-admin limit from the per-IP one
        r = await _redeem(http, people["ops"], "CDW-AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH")
        assert r.status_code == 400
    request_tracker.clear()
    r = await _redeem(http, people["ops"], "CDW-AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH")
    assert r.status_code == 429
