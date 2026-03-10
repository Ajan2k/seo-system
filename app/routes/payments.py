import json
import razorpay
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.future import select
from sqlalchemy import update, insert
from core.config import settings
from app.models import AsyncSessionLocal, User, Transaction
from app.routes.auth import get_user_id
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Initialize Razorpay client
try:
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
except Exception as e:
    logger.error(f"Failed to initialize Razorpay client: {e}")
    razorpay_client = None

PLANS = {
    "starter": {"amount": 74900, "credits": 10}, # amount in paise (₹749)
    "professional": {"amount": 329900, "credits": 50}, # ₹3299
    "business": {"amount": 589900, "credits": 100}, # ₹5899
}

class CreateOrderRequest(BaseModel):
    plan: str

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan: str

@router.post("/payments/create-order")
async def create_order(request: CreateOrderRequest, user_id: int = Depends(get_user_id)):
    """Create a Razorpay order for the selected plan."""
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")

    plan_key = request.plan.lower()
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")

    amount = PLANS[plan_key]["amount"]
    
    # Create order in Razorpay
    data = {
        "amount": amount,
        "currency": "INR", # Mutated to INR to support UPI/Netbanking
        "payment_capture": "1" # Auto capture
    }

    try:
        payment = razorpay_client.order.create(data=data)
        
        # Save transaction as created
        async with AsyncSessionLocal() as session:
            new_tx = Transaction(
                user_id=user_id,
                razorpay_order_id=payment['id'],
                amount=amount / 100.0,
                currency="INR",
                status="created",
                plan_purchased=plan_key
            )
            session.add(new_tx)
            await session.commit()

        return {
            "success": True,
            "order_id": payment['id'],
            "amount": amount,
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID
        }
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        raise HTTPException(status_code=500, detail="Error creating order")

@router.post("/payments/verify")
async def verify_payment(request: VerifyPaymentRequest, user_id: int = Depends(get_user_id)):
    """Verify a Razorpay payment signature and update user plan."""
    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Payment gateway not configured.")

    try:
        # Verify signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': request.razorpay_order_id,
            'razorpay_payment_id': request.razorpay_payment_id,
            'razorpay_signature': request.razorpay_signature
        })
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    plan_key = request.plan.lower()
    if plan_key not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan selected.")

    credits_to_add = PLANS[plan_key]["credits"]

    async with AsyncSessionLocal() as session:
        # Update transaction
        stmt = update(Transaction).where(
            Transaction.razorpay_order_id == request.razorpay_order_id
        ).values(
            razorpay_payment_id=request.razorpay_payment_id,
            status="paid"
        )
        await session.execute(stmt)
        
        # Get user current credits
        user_query = select(User).where(User.id == user_id)
        result = await session.execute(user_query)
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update user plan and credits
        new_credits = (user.credits or 0) + credits_to_add
        stmt_user = update(User).where(User.id == user_id).values(
            plan=plan_key,
            credits=new_credits
        )
        await session.execute(stmt_user)
        await session.commit()

    return {"success": True, "message": "Payment verified and plan updated successfully."}
