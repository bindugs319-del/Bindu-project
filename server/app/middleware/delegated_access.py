"""
Read-only guard for client-authorized admin view access.

Any request carrying X-Delegated-Grant that would write (non-GET, a GET
known to write, or a grant-management endpoint) is rejected here, before
routing — a second, independent layer on top of the same check in
resolve_delegation(). The attempt is recorded as WRITE_BLOCKED.
"""
import json
import logging

from app.services.delegated_access_service import (
    DELEGATION_HEADER, Events, is_write_blocked, resource_for_path, log_event, ensure_tables,
)

logger = logging.getLogger(__name__)

_HEADER_KEY = DELEGATION_HEADER.lower().encode()
_BRANCH_HEADER_KEY = b"x-branch-view"

# Overridable in tests; defaults to the app's session factory.
session_factory = None


def _get_session_factory():
    if session_factory is not None:
        return session_factory
    from app.database import AsyncSessionLocal
    return AsyncSessionLocal


class DelegatedReadOnlyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        grant_id = None
        branch_view = False
        for key, value in scope.get("headers", []):
            if key == _HEADER_KEY:
                grant_id = value.decode("latin-1").strip()
            elif key == _BRANCH_HEADER_KEY:
                branch_view = True  # head office viewing a branch: same read-only rule

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if not (grant_id or branch_view) or not is_write_blocked(method, path):
            await self.app(scope, receive, send)
            return

        if grant_id:
            await self._log_blocked(grant_id, scope)
        body = json.dumps({
            "detail": {
                "code": "DELEGATION_READ_ONLY",
                "msg": "Read-only view: changes are not allowed while viewing another account.",
            }
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({"type": "http.response.body", "body": body})

    async def _log_blocked(self, grant_id, scope):
        try:
            from starlette.requests import Request
            from app.models.admin_access import AdminAccessGrant

            request = Request(scope)
            async with _get_session_factory()() as db:
                await ensure_tables(db)
                grant = await db.get(AdminAccessGrant, grant_id)
                if grant is None:
                    return  # unknown grant id: nothing to attribute it to
                log_event(db, Events.WRITE_BLOCKED, grant=grant, request=request,
                          resource=resource_for_path(scope.get("path", "")))
                await db.commit()
        except Exception as e:  # logging must never turn a 403 into a 500
            logger.warning(f"[ADMIN ACCESS] Could not log blocked write: {e}")
