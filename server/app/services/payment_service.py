"""
Payment service for handling payment transactions
"""
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from app.models import Payment, Plan, User, PaymentStatus, PaymentMethod
from app.exceptions import PlanNotFound, UserNotFound
from app.services.subscription_service import SubscriptionService
import logging
import secrets
import string

logger = logging.getLogger(__name__)


def generate_reference_id() -> str:
    """Generate unique reference ID for payment"""
    chars = string.ascii_uppercase + string.digits
    return f"REF{''.join(secrets.choice(chars) for _ in range(10))}"


def generate_transaction_id() -> str:
    """Generate transaction ID (simulated gateway ID)"""
    chars = string.ascii_uppercase + string.digits
    return f"TXN{''.join(secrets.choice(chars) for _ in range(12))}"


class PaymentService:
    """Handle payment processing and verification"""

    @staticmethod
    async def initiate_payment(
        user_id: str,
        plan_id: str,
        payment_method: str,
        db: AsyncSession
    ) -> tuple[Payment, Dict[str, Any]]:
        """
        Initiate payment for a plan
        
        Args:
            user_id: User ID
            plan_id: Plan ID to purchase
            payment_method: Payment method (upi, credit_card, etc.)
            db: Database session
            
        Returns:
            Tuple of (Payment object, payment_options dict)
            
        Raises:
            UserNotFound: If user doesn't exist
            PlanNotFound: If plan doesn't exist or is inactive
        """
        # Verify user exists
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if not user:
            raise UserNotFound()
        
        # Verify plan exists and is active
        plan_stmt = select(Plan).where(
            (Plan.id == plan_id) & 
            (Plan.is_active == True)
        )
        plan_result = await db.execute(plan_stmt)
        plan = plan_result.scalars().first()
        
        if not plan:
            raise PlanNotFound()
        
        # Cancel any pending payments for this user
        pending_stmt = select(Payment).where(
            (Payment.user_id == user_id) &
            (Payment.status == PaymentStatus.PENDING)
        )
        pending_result = await db.execute(pending_stmt)
        pending_payments = pending_result.scalars().all()
        
        for payment in pending_payments:
            payment.status = PaymentStatus.CANCELLED
            payment.updated_at = datetime.utcnow()
        
        # Create new payment record
        now = datetime.utcnow()
        reference_id = generate_reference_id()
        
        payment = Payment(
            id=str(uuid4()),
            user_id=user_id,
            plan_id=plan_id,
            amount=plan.price,
            currency="INR",
            payment_method=PaymentMethod(payment_method),
            payment_provider=None,  # Set when integrating real gateway
            status=PaymentStatus.PENDING,
            reference_id=reference_id,
            payment_metadata={},
            initiated_at=now,
            created_at=now,
            updated_at=now,
        )
        
        db.add(payment)
        await db.flush()
        
        # Generate payment options based on method
        payment_options = PaymentService._generate_payment_options(
            payment_method, payment.reference_id, plan.price
        )
        
        logger.info(
            f"Payment initiated: user_id={user_id}, plan_id={plan_id}, "
            f"payment_id={payment.id}, reference_id={reference_id}"
        )
        
        return payment, payment_options

    @staticmethod
    def _generate_payment_options(
        payment_method: str,
        reference_id: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Generate payment options based on payment method
        
        Args:
            payment_method: Payment method selected
            reference_id: Payment reference ID
            amount: Payment amount
            
        Returns:
            Dictionary with payment options
        """
        options = {}
        
        if payment_method == PaymentMethod.UPI or payment_method == PaymentMethod.QR_CODE:
            # Generate UPI QR code and UPI ID
            upi_id = "YOUR_UPI_ID_HERE"  # e.g. "yourname@okicici", "yourname@oksbi", "yourname@ybl"
            upi_string = f"upi://pay?pa={upi_id}&pn=CreditDataWatch&am={amount}&cu=INR&tn={reference_id}"
            qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={upi_string}"
            
            options["upi"] = {
                "qr_code_url": qr_code_url,
                "upi_id": upi_id,
                "upi_string": upi_string,
                "instructions": "Scan QR code or send money to UPI ID",
                "amount": amount,
                "reference_id": reference_id
            }
        
        if payment_method == PaymentMethod.CREDIT_CARD or payment_method == PaymentMethod.DEBIT_CARD:
            options["card"] = {
                "gateway_url": "https://checkout.razorpay.com/v1/checkout.js",
                "order_id": f"order_{reference_id}",
                "amount": amount,
                "currency": "INR",
                "instructions": "Enter your card details",
                "supported_cards": ["Visa", "Mastercard", "RuPay"]
            }
        
        if payment_method == PaymentMethod.NET_BANKING:
            options["net_banking"] = {
                "gateway_url": "https://checkout.razorpay.com/v1/checkout.js",
                "order_id": f"order_{reference_id}",
                "banks": ["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank", "Kotak Mahindra Bank"],
                "amount": amount,
                "currency": "INR",
                "instructions": "Select your bank and complete payment"
            }
        
        return options

    @staticmethod
    async def verify_payment(
        payment_id: str,
        transaction_id: str,
        gateway_order_id: Optional[str] = None,
        gateway_payment_id: Optional[str] = None,
        db: AsyncSession = None
    ) -> tuple[Payment, Optional[Any]]:
        """
        Verify payment completion
        
        Args:
            payment_id: Payment ID
            transaction_id: Transaction ID from gateway
            gateway_order_id: Gateway order ID
            gateway_payment_id: Gateway payment ID
            db: Database session
            
        Returns:
            Tuple of (Payment object, Subscription object if created)
            
        Raises:
            UserNotFound: If payment not found
        """
        # Get payment
        payment_stmt = select(Payment).where(Payment.id == payment_id)
        payment_result = await db.execute(payment_stmt)
        payment = payment_result.scalars().first()
        
        if not payment:
            raise UserNotFound()
        
        # Check if already verified
        if payment.status == PaymentStatus.SUCCESS:
            logger.warning(f"Payment {payment_id} already verified")
            # Return existing subscription if any
            subscription = await SubscriptionService.get_active_subscription(
                payment.user_id, db
            )
            return payment, subscription

        # Guard against duplicate transaction IDs (the column is UNIQUE) —
        # give a clear, actionable error instead of a raw DB constraint failure.
        if transaction_id:
            dup_stmt = select(Payment).where(
                Payment.transaction_id == transaction_id,
                Payment.id != payment_id,
            )
            dup_result = await db.execute(dup_stmt)
            if dup_result.scalars().first():
                from app.exceptions import DuplicateTransactionId
                raise DuplicateTransactionId(
                    "This transaction ID has already been used for another payment. "
                    "Please enter the correct UPI transaction ID/UTR number for this payment."
                )

        # In real implementation, verify with payment gateway here
        # For simulation, we'll just mark as success
        
        # Update payment status
        now = datetime.utcnow()
        payment.status = PaymentStatus.SUCCESS
        payment.transaction_id = transaction_id
        payment.gateway_order_id = gateway_order_id
        payment.gateway_payment_id = gateway_payment_id
        payment.completed_at = now
        payment.updated_at = now
        
        await db.flush()
        
        # Activate subscription workflow
        from app.services.workflow_service import WorkflowService
        from app.models import User, Plan, Company
        
        user_stmt = select(User).where(User.id == payment.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalars().first()
        
        plan_stmt = select(Plan).where(Plan.id == payment.plan_id)
        plan_res = await db.execute(plan_stmt)
        plan = plan_res.scalars().first()
        
        company_name = "Unknown Company"
        if user and user.company_id:
            comp_stmt = select(Company.company_name).where(Company.id == user.company_id)
            comp_res = await db.execute(comp_stmt)
            company_name = comp_res.scalar() or "Unknown Company"
        elif user:
            company_name = user.company_name or "Unknown Company"

        subscription = None
        try:
            # Start the subscription workflow instead of activating immediately
            sub_id = await WorkflowService.start_subscription(
                db=db,
                user_id=payment.user_id,
                user_email=user.email if user else "unknown",
                company_name=company_name,
                plan_name=plan.display_name if plan else "Unknown Plan",
                amount=payment.amount
            )
            logger.info(
                f"Subscription workflow started after payment: payment_id={payment_id}, "
                f"subscription_request_id={sub_id}"
            )
        except Exception as e:
            logger.error(f"Failed to start subscription workflow after payment: {e}", exc_info=True)
            raise
        
        return payment, None # subscription is now in workflow, not yet a Subscription object


    @staticmethod
    async def get_payment_status(
        payment_id: str,
        db: AsyncSession
    ) -> Optional[Payment]:
        """
        Get payment status
        
        Args:
            payment_id: Payment ID
            db: Database session
            
        Returns:
            Payment object or None
        """
        payment_stmt = select(Payment).where(Payment.id == payment_id)
        payment_result = await db.execute(payment_stmt)
        return payment_result.scalars().first()

    @staticmethod
    async def get_user_payment_history(
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        db: AsyncSession = None
    ) -> list[Payment]:
        """
        Get user's payment history
        
        Args:
            user_id: User ID
            limit: Maximum number of payments to return
            offset: Offset for pagination
            db: Database session
            
        Returns:
            List of Payment objects
        """
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def cancel_payment(
        payment_id: str,
        user_id: str,
        db: AsyncSession
    ) -> Payment:
        """
        Cancel a pending payment
        
        Args:
            payment_id: Payment ID
            user_id: User ID (for verification)
            db: Database session
            
        Returns:
            Updated Payment object
            
        Raises:
            UserNotFound: If payment not found or doesn't belong to user
        """
        payment_stmt = select(Payment).where(
            (Payment.id == payment_id) &
            (Payment.user_id == user_id)
        )
        payment_result = await db.execute(payment_stmt)
        payment = payment_result.scalars().first()
        
        if not payment:
            raise UserNotFound()
        
        if payment.status != PaymentStatus.PENDING:
            raise ValueError(f"Cannot cancel payment with status: {payment.status}")
        
        payment.status = PaymentStatus.CANCELLED
        payment.updated_at = datetime.utcnow()
        
        await db.flush()
        
        logger.info(f"Payment cancelled: payment_id={payment_id}")
        
        return payment
