"""
Shared constants and logger used across the core route modules.
"""
import logging

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)
PO_MANAGEMENT = "PO_MANAGEMENT"
PO_FEATURE_NAME = "PO Management"
REPORT_OVERDUE = "REPORT_OVERDUE"
DEFAULTER_FEATURE_NAME = "Defaulter Reporting"
CREDIT_REPORT = "CREDIT_REPORT"
CREDIT_REPORT_FEATURE_NAME = "Credit Report"
SETTLEMENT = "SETTLEMENT"
SETTLEMENT_FEATURE_NAME = "Settlement"
NOT_FOUND_ERROR = "not found"
PO_NOT_FOUND_ERROR = "Purchase order not found"
ACCESS_DENIED_ERROR = "Access denied"
CANNOT_UPDATE_REVIEWED = "Cannot update case that has been reviewed"
EITHER_GSTIN_PAN = "Either GSTIN or PAN must be provided"
INVALID_PAN_FORMAT = "Invalid PAN format"

