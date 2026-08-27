"""
Shared helpers for the manual (non-pytest) end-to-end scripts in this
folder — extracted because e2e_workflow_test.py and
test_credibility_workflow.py each had their own copy of create_test_user()
that only differed in the subscription-related fields set on a freshly
created user.

These are debug/verification scripts run by hand, not part of the
automated test suite or CI — see the top of each script for how to run it.
"""
from uuid import uuid4
from sqlalchemy import select

from app.models import Company, User


async def create_test_user(
    session,
    email: str,
    role: str,
    company_name: str,
    gstin: str,
    *,
    subscription_status: str = "INACTIVE",
    subscription_bypass: bool = False,
    full_access: bool = False,
):
    """
    Gets or creates a Company (matched by GSTIN) and a User (matched by
    email) for use in a manual workflow test. If the user already exists,
    only its role is updated (matches the original scripts' behavior of
    reusing existing test data across repeated runs rather than erroring).

    The three keyword-only params default to what e2e_workflow_test.py
    used; test_credibility_workflow.py passes subscription_status="ACTIVE",
    subscription_bypass=True, full_access=True to skip subscription gating
    when testing the credibility workflow specifically.
    """
    res_comp = await session.execute(select(Company).where(Company.gstin == gstin))
    comp = res_comp.scalars().first()
    if not comp:
        comp = Company(
            id=str(uuid4()),
            company_name=company_name,
            gstin=gstin,
            domain_name=email.split("@")[1],
            is_verified=True,
        )
        session.add(comp)
        await session.flush()

    res_user = await session.execute(select(User).where(User.email == email))
    user = res_user.scalars().first()
    if not user:
        user = User(
            id=str(uuid4()),
            company_id=comp.id,
            name=company_name,
            email=email,
            password_hash="test_hash",
            role=role,
            status="ACTIVE",
            phone="+919999999999",
            gstin=gstin,
            company_name=company_name,
            is_active=True,
            subscription_status=subscription_status,
            subscription_bypass=subscription_bypass,
            full_access=full_access,
        )
        session.add(user)
        await session.flush()
    else:
        user.role = role
        await session.flush()
    return user
