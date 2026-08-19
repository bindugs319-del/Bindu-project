"""
Core routes package.

This was previously a single 3,189-line core.py file. It has been split by
domain into separate modules for maintainability; this __init__.py re-exports
every router object so existing imports (`from app.routes import core`,
then `core.upload_router`, `core.po_router`, etc.) continue to work unchanged.
"""
from .upload import upload_router
from .audit import audit_router
from .user import user_router
from .purchase_orders import po_router, pos_router
from .purchase_history import purchase_history_router
from .gstin import gstin_router
from .defaulters import defaulter_router
from .notifications import notifications_router
from .credit_reports import credit_router
from .settlements import settlement_router
from .business_requests import business_requests_router

__all__ = [
    "upload_router", "audit_router", "user_router", "po_router", "pos_router",
    "purchase_history_router", "gstin_router", "defaulter_router",
    "notifications_router", "credit_router", "settlement_router",
    "business_requests_router",
]
