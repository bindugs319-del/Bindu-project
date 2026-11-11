"""
Tests for head office / branch organisations.

Uses the same throwaway test database and fixtures as test_delegated_access.py.
Run from server/:  venv/Scripts/python -m pytest tests/test_organization.py -v
"""
import random
import string
import uuid

import pytest

from app.models import Company, User, UserRole
from app.services import organization_service as org
from app.utils import create_access_token, hash_password
from test_delegated_access import session_factory, http  # noqa: F401  (shared fixtures)

API = "/api/v1"
BRANCH = org.BRANCH_VIEW_HEADER


@pytest.fixture(autouse=True)
def _reset_org_tables(monkeypatch):
    monkeypatch.setattr(org, "_tables_ready", False)


def _pan() -> str:
    letters = "".join(random.choices(string.ascii_uppercase, k=5))
    digits = "".join(random.choices(string.digits, k=4))
    return letters + digits + random.choice(string.ascii_uppercase)


def _gstin(pan: str, state: str) -> str:
    return f"{state}{pan}1Z5"


async def _company_admin(factory, gstin: str, name: str, role=UserRole.COMPANY_ADMIN) -> User:
    async with factory() as db:
        company = Company(id=str(uuid.uuid4()), company_name=name, gstin=gstin, domain_name="test.local", is_verified=True)
        db.add(company)
        await db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=company.id, name=name,
            email=f"{uuid.uuid4().hex[:10]}@test.local", password_hash=hash_password("Passw0rd!"),
            role=role, status="ACTIVE", phone="+919800000000", gstin=gstin, company_name=name,
            is_active=True, subscription_status="ACTIVE",
        )
        db.add(user)
        await db.commit()
        return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}


@pytest.fixture
async def infosys(session_factory):  # noqa: F811
    """A head office plus two same-PAN companies (future branches) and a Super Admin."""
    pan = _pan()
    hq = await _company_admin(session_factory, _gstin(pan, "29"), "Infosys HQ")
    blr = await _company_admin(session_factory, _gstin(pan, "27"), "Infosys Pune")
    chn = await _company_admin(session_factory, _gstin(pan, "33"), "Infosys Chennai")
    other = await _company_admin(session_factory, _gstin(_pan(), "07"), "Unrelated Ltd")
    sup = await _company_admin(session_factory, _gstin(_pan(), "22"), "CDW", role=UserRole.MASTER_ADMIN)
    return {"hq": hq, "b1": blr, "b2": chn, "other": other, "super": sup}


async def _make_hq(http, user):  # noqa: F811
    r = await http.post(f"{API}/organization/head-office", headers=_auth(user))
    assert r.status_code == 200, r.text


async def _request(http, branch_user, hq_user, name="Branch"):  # noqa: F811
    return await http.post(f"{API}/organization/branch-request",
                           json={"hq_gstin": hq_user.gstin, "branch_name": name}, headers=_auth(branch_user))


async def _set_limit(http, sup, hq_user, n):  # noqa: F811
    r = await http.put(f"{API}/admin/organizations/{hq_user.company_id}/branch-limit",
                       json={"branch_limit": n}, headers=_auth(sup))
    assert r.status_code == 200, r.text


async def _pending_link_id(http, hq_user):  # noqa: F811
    r = await http.get(f"{API}/organization", headers=_auth(hq_user))
    return [b["id"] for b in r.json()["data"]["branches"] if b["status"] == "PENDING"][0]


async def _approved_branch(http, p, key="b1"):  # noqa: F811
    await _make_hq(http, p["hq"])
    await _set_limit(http, p["super"], p["hq"], 5)
    assert (await _request(http, p[key], p["hq"], key)).status_code == 200
    link_id = await _pending_link_id(http, p["hq"])
    r = await http.post(f"{API}/organization/branches/{link_id}/approve", headers=_auth(p["hq"]))
    assert r.status_code == 200, r.text
    return link_id


# ------------------------------------------------------------ linking rules

async def test_branch_request_requires_same_pan(http, infosys):  # noqa: F811
    await _make_hq(http, infosys["hq"])
    r = await _request(http, infosys["other"], infosys["hq"])
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PAN_MISMATCH"


async def test_branch_request_requires_head_office(http, infosys):  # noqa: F811
    r = await _request(http, infosys["b1"], infosys["hq"])  # hq never became a head office
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NOT_HEAD_OFFICE"


async def test_branch_limit_is_enforced_and_set_by_super_admin(http, infosys):  # noqa: F811
    await _make_hq(http, infosys["hq"])
    assert (await _request(http, infosys["b1"], infosys["hq"])).status_code == 200
    link_id = await _pending_link_id(http, infosys["hq"])

    # Default limit is 0: approval blocked
    r = await http.post(f"{API}/organization/branches/{link_id}/approve", headers=_auth(infosys["hq"]))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BRANCH_LIMIT_REACHED"

    # Companies can't raise their own limit
    r = await http.put(f"{API}/admin/organizations/{infosys['hq'].company_id}/branch-limit",
                       json={"branch_limit": 9}, headers=_auth(infosys["hq"]))
    assert r.status_code == 403

    await _set_limit(http, infosys["super"], infosys["hq"], 1)
    r = await http.post(f"{API}/organization/branches/{link_id}/approve", headers=_auth(infosys["hq"]))
    assert r.status_code == 200

    # Second branch exceeds the limit of 1
    assert (await _request(http, infosys["b2"], infosys["hq"])).status_code == 200
    link2 = await _pending_link_id(http, infosys["hq"])
    r = await http.post(f"{API}/organization/branches/{link2}/approve", headers=_auth(infosys["hq"]))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BRANCH_LIMIT_REACHED"


# ------------------------------------------------------------ visibility

async def test_head_office_views_branch_read_only(http, infosys):  # noqa: F811
    await _approved_branch(http, infosys)
    headers = {**_auth(infosys["hq"]), BRANCH: infosys["b1"].company_id}

    r = await http.get(f"{API}/user/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert infosys["b1"].email in r.text and infosys["hq"].email not in r.text

    r = await http.put(f"{API}/user/profile", json={"company_name": "x"}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "DELEGATION_READ_ONLY"


async def test_branch_cannot_see_head_office_or_other_branches(http, infosys):  # noqa: F811
    await _approved_branch(http, infosys, "b1")
    # Branch tries to view the head office
    r = await http.get(f"{API}/user/profile", headers={**_auth(infosys["b1"]), BRANCH: infosys["hq"].company_id})
    assert r.status_code == 403
    # Branch has no combined totals
    r = await http.get(f"{API}/organization/summary", headers=_auth(infosys["b1"]))
    assert r.status_code == 403


async def test_head_office_cannot_view_pending_or_unrelated_companies(http, infosys):  # noqa: F811
    await _make_hq(http, infosys["hq"])
    await _request(http, infosys["b1"], infosys["hq"])  # pending only
    for target in (infosys["b1"], infosys["other"]):
        r = await http.get(f"{API}/user/profile", headers={**_auth(infosys["hq"]), BRANCH: target.company_id})
        assert r.status_code == 403


async def test_removing_branch_ends_view_on_next_request(http, infosys):  # noqa: F811
    link_id = await _approved_branch(http, infosys)
    headers = {**_auth(infosys["hq"]), BRANCH: infosys["b1"].company_id}
    assert (await http.get(f"{API}/user/profile", headers=headers)).status_code == 200
    r = await http.post(f"{API}/organization/branches/{link_id}/remove", headers=_auth(infosys["hq"]))
    assert r.status_code == 200
    r = await http.get(f"{API}/user/profile", headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "DELEGATION_ENDED"


async def test_summary_lists_head_office_and_approved_branches(http, infosys):  # noqa: F811
    await _approved_branch(http, infosys, "b1")
    r = await http.get(f"{API}/organization/summary", headers=_auth(infosys["hq"]))
    assert r.status_code == 200
    rows = r.json()["data"]["rows"]
    assert [row["label"] for row in rows] == ["Head office", "b1"]
    assert {"invoices", "outstanding", "overdue_invoices", "purchase_orders", "defaulter_cases"} <= set(r.json()["data"]["totals"])


# ------------------------------------------------------------ registration

async def test_register_as_branch_with_wrong_pan_creates_no_account(http, infosys, session_factory):  # noqa: F811
    await _make_hq(http, infosys["hq"])
    gstin = _gstin(_pan(), "24")  # different PAN
    email = f"{uuid.uuid4().hex[:8]}@branchtest.com"
    body = {
        "company_name": "Fake Branch", "email": email, "password": "Passw0rd!",
        "phone": "9845012345", "gstin": gstin, "org_type": "BRANCH",
        "hq_gstin": infosys["hq"].gstin, "branch_name": "Ahmedabad",
    }
    r = await http.post(f"{API}/auth/register", json=body)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "PAN_MISMATCH"

    from sqlalchemy import select
    async with session_factory() as db:
        assert (await db.execute(select(User).where(User.email == email))).scalars().first() is None
