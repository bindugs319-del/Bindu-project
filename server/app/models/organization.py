"""
Company organisations: a head office with branch companies.

Each branch is its own company (own GSTIN, own login, sees only its own
data). A branch links to a head office only after the head office
approves, and both GSTINs must share the same PAN. Platform Super Admins
decide how many branches each head office may have (branch_limit).

Kept in separate tables so the existing `companies` table is unchanged.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index

from app.database import Base


class CompanyOrgSettings(Base):
    """Per-company organisation settings (one row per company that has any)."""

    __tablename__ = "company_org_settings"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    is_headquarters = Column(Boolean, default=False, nullable=False, index=True)
    branch_limit = Column(Integer, default=0, nullable=False)  # set by platform Super Admins
    limit_set_by = Column(String(36), nullable=True)
    limit_set_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CompanyBranchLink(Base):
    """A branch company's link to its head office (pending until approved)."""

    __tablename__ = "company_branch_links"

    id = Column(String(36), primary_key=True, index=True)
    hq_company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_name = Column(String(120), nullable=False)  # e.g. "Bengaluru"
    status = Column(String(20), nullable=False, default="PENDING", index=True)  # PENDING / APPROVED / REJECTED / REMOVED / CANCELLED
    requested_by = Column(String(36), nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_by = Column(String(36), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_branch_link_hq_status", "hq_company_id", "status"),
    )
