"""src/api/routes/stripe_billing.py — Stripe billing endpoints.

Handles the entire Stripe integration for Gaitway subscriptions:
  - List available subscription plans
  - Create a Stripe Checkout Session (new subscription)
  - Create a Stripe Billing Portal Session (manage/cancel)
  - Stripe webhook receiver (sync subscription status)

Pricing: $1,200/year — annual auto-renewing subscription.

Endpoints
---------
GET  /api/v1/billing/plans      list available subscription plans
POST /api/v1/billing/checkout   create a Stripe Checkout session
POST /api/v1/billing/portal     create a Stripe Billing Portal session
POST /api/v1/billing/webhook    Stripe webhook event receiver

Authentication:
  - /plans — public
  - /checkout, /portal — require authenticated user (Phase 6 Cognito JWT)
  - /webhook — validated by Stripe-Signature header
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/billing",
    tags=["billing"],
)


# ─────────────────────────────────────────────────────────────
# Response / Request Models
# ─────────────────────────────────────────────────────────────


class PlanResponse(BaseModel):
    """A Stripe subscription plan."""

    id: int
    stripe_price_id: str
    name: str
    price_usd: float
    interval: str
    description: str = ""

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    """Request body for creating a Stripe Checkout session."""

    price_id: str
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None
    user_id: Optional[int] = None


class CheckoutResponse(BaseModel):
    """Response with Stripe Checkout URL."""

    checkout_url: str
    session_id: str


class PortalRequest(BaseModel):
    """Request body for creating a Stripe Billing Portal session."""

    stripe_customer_id: str
    return_url: str


class PortalResponse(BaseModel):
    """Response with Stripe Billing Portal URL."""

    portal_url: str


class WebhookResponse(BaseModel):
    """Acknowledgement response for Stripe webhook events."""

    received: bool
    event_type: Optional[str] = None
    message: str = "ok"


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans():
    """Return the available Gaitway subscription plans.

    Currently a single plan: $1,200/year (annual auto-renew).
    Reads from the database subscription_plans table.

    .. note::
        Returns a hardcoded plan in Phase 1 (no DB integration yet).
    """
    # TODO (Phase 6): query subscription_plans table
    return [
        PlanResponse(
            id=1,
            stripe_price_id=os.getenv("STRIPE_PRICE_ID", "price_placeholder"),
            name="Gaitway Professional Annual",
            price_usd=1200.0,
            interval="year",
            description=(
                "Full access to the Gaitway Footwear Intelligence Database. "
                "Unlimited crime scene searches, full shoe catalog, "
                "forensic audit logging. $1,200/year, auto-renews annually."
            ),
        )
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(body: CheckoutRequest):
    """Create a Stripe Checkout session for a new subscription.

    Redirects the user to Stripe's hosted checkout page to complete
    payment.  On success, Stripe redirects to ``success_url`` and
    sends a ``checkout.session.completed`` webhook.

    Args:
        body: Price ID, success/cancel URLs, optional customer email.

    Returns:
        CheckoutResponse with the Stripe Checkout URL.

    Raises:
        HTTPException 400: if the price_id is invalid.
        HTTPException 503: if Stripe is unreachable or not configured.
    """
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured (STRIPE_SECRET_KEY missing)",
        )

    try:
        import stripe

        stripe.api_key = stripe_secret

        session_params = {
            "mode": "subscription",
            "line_items": [{"price": body.price_id, "quantity": 1}],
            "success_url": body.success_url,
            "cancel_url": body.cancel_url,
        }
        if body.customer_email:
            session_params["customer_email"] = body.customer_email

        session = stripe.checkout.Session.create(**session_params)

        logger.info(
            "create_checkout_session session_id=%s price_id=%s",
            session.id,
            body.price_id,
        )
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Stripe checkout session error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe error: {exc}",
        ) from exc


@router.post("/portal", response_model=PortalResponse)
async def create_billing_portal_session(body: PortalRequest):
    """Create a Stripe Billing Portal session for managing a subscription.

    Allows the customer to update payment methods, view invoices, and
    cancel their subscription.

    Args:
        body: Stripe customer ID and return URL.

    Returns:
        PortalResponse with the Stripe Billing Portal URL.

    Raises:
        HTTPException 503: if Stripe is not configured or unreachable.
    """
    stripe_secret = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured (STRIPE_SECRET_KEY missing)",
        )

    try:
        import stripe

        stripe.api_key = stripe_secret
        portal = stripe.billing_portal.Session.create(
            customer=body.stripe_customer_id,
            return_url=body.return_url,
        )

        logger.info(
            "create_billing_portal customer=%s", body.stripe_customer_id
        )
        return PortalResponse(portal_url=portal.url)
    except Exception as exc:  # noqa: BLE001
        logger.error("Stripe billing portal error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe error: {exc}",
        ) from exc


@router.post("/webhook", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    """Receive and process Stripe webhook events.

    Validates the ``Stripe-Signature`` header using the webhook secret
    (``STRIPE_WEBHOOK_SECRET`` env var) to prevent replay attacks.

    Handled events:
      - ``checkout.session.completed``     — provision subscription
      - ``customer.subscription.updated``  — sync status changes
      - ``customer.subscription.deleted``  — mark subscription canceled
      - ``invoice.payment_failed``         — mark subscription past_due

    Args:
        request:          Raw FastAPI Request (body read as bytes for signature check).
        stripe_signature: The ``Stripe-Signature`` header value.

    Returns:
        WebhookResponse acknowledging receipt.

    Raises:
        HTTPException 400: if signature validation fails.
        HTTPException 503: if Stripe is not configured.
    """
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_WEBHOOK_SECRET not configured",
        )

    payload = await request.body()

    try:
        import stripe

        stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
        event = stripe.Webhook.construct_event(
            payload, stripe_signature or "", webhook_secret
        )
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature invalid: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Stripe webhook parsing error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {exc}",
        ) from exc

    event_type: str = event["type"]
    logger.info("Stripe webhook received: event_type=%s", event_type)

    # ── Route by event type ──────────────────────────────────────────────────
    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"])
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"])
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"])
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return WebhookResponse(received=True, event_type=event_type)


# ─────────────────────────────────────────────────────────────
# Webhook Handlers (stubs — wired to DB in Phase 6)
# ─────────────────────────────────────────────────────────────


def _handle_checkout_completed(session) -> None:
    """Provision a new subscription after successful Stripe Checkout.

    TODO (Phase 6): create/update UserSubscription record in DB.
    """
    logger.info(
        "checkout.session.completed: session_id=%s customer=%s",
        session.get("id"),
        session.get("customer"),
    )


def _handle_subscription_updated(subscription) -> None:
    """Sync subscription status after any Stripe subscription change.

    TODO (Phase 6): update UserSubscription.status in DB.
    """
    logger.info(
        "customer.subscription.updated: sub_id=%s status=%s",
        subscription.get("id"),
        subscription.get("status"),
    )


def _handle_subscription_deleted(subscription) -> None:
    """Mark subscription as canceled after Stripe deletion.

    TODO (Phase 6): set UserSubscription.status = 'canceled'.
    """
    logger.info(
        "customer.subscription.deleted: sub_id=%s",
        subscription.get("id"),
    )


def _handle_payment_failed(invoice) -> None:
    """Mark subscription as past_due after failed payment.

    TODO (Phase 6): set UserSubscription.status = 'past_due'.
    """
    logger.info(
        "invoice.payment_failed: invoice_id=%s customer=%s",
        invoice.get("id"),
        invoice.get("customer"),
    )
