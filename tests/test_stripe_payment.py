"""Stripe payment check (test mode) for the CI `test` job.

The check walks the same Stripe API path a real charge uses: it creates a
PaymentIntent with a fixed amount and confirms it with Stripe's documented
test PaymentMethod ``pm_card_visa``, then asserts the returned status is
``succeeded``.  The API is called for real (no mock) — only the key mode
differs from a live charge.

Per the Issue #65 decisions the check FAILS — never skips — when
``STRIPE_SECRET_KEY`` is missing: a deleted, renamed or expired secret must
turn CI red instead of silently passing.  The secret itself is never printed.
"""

import os

import pytest
import stripe

# Issue #65 fixes the charged amount: 1.00 USD in the smallest unit.
AMOUNT = 100
CURRENCY = "usd"

# Stripe's documented test PaymentMethod (test mode only):
# https://docs.stripe.com/testing
TEST_PAYMENT_METHOD = "pm_card_visa"

SECRET_ENV = "STRIPE_SECRET_KEY"
MISSING_SECRET_MESSAGE = (
    "未配置 STRIPE_SECRET_KEY，无法执行 Stripe 收款检查；"
    "请在仓库 Settings → Secrets and variables → Actions 中配置测试模式密钥"
)


def create_test_payment_intent():
    """Create and confirm one fixed-amount PaymentIntent in test mode."""
    secret = os.environ.get(SECRET_ENV, "").strip()
    if not secret:
        pytest.fail(MISSING_SECRET_MESSAGE)
    stripe.api_key = secret
    return stripe.PaymentIntent.create(
        amount=AMOUNT,
        currency=CURRENCY,
        payment_method=TEST_PAYMENT_METHOD,
        confirm=True,
        # Cards never redirect; `never` keeps the confirm call free of a
        # return_url (https://docs.stripe.com/api/payment_intents/create).
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
    )


def test_stripe_payment_intent_succeeds_in_test_mode():
    intent = create_test_payment_intent()
    # The public Stripe id/amount/status are the CI log evidence the Issue
    # asks for; the secret is never part of this line.
    print(
        f"stripe payment_intent id={intent.id} amount={intent.amount} "
        f"currency={intent.currency} status={intent.status}"
    )
    assert intent.status == "succeeded", (
        f"Stripe PaymentIntent {intent.id} did not succeed: {intent.status}"
    )
