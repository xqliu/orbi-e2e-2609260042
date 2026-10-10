"""Stripe live payment entry points for this repository.

The repository has no application server: the payment path is a small CLI
that talks to the Stripe API with the operator's live secret key.

* ``python -m stripe_payments checkout`` creates a Stripe Checkout Session
  (the hosted payment page) and prints its URL.  Opening that URL and paying
  produces a real live payment in the operator's Stripe account.
* ``python -m stripe_payments verify`` creates and confirms a PaymentIntent
  against a pre-created payment method id (``pm_...``).  The hosted Checkout
  page needs a browser to complete, so the automated, card-data-free
  verification uses Stripe's server-side PaymentIntent API instead.  This is
  the exact command the manual, protected CI verification run executes.

The live secret key is read from the ``STRIPE_LIVE_SECRET_KEY`` environment
variable (an environment secret of the protected ``stripe-live`` GitHub
Actions environment).  It is never passed on the command line and never
written to disk.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

import stripe

LIVE_SECRET_KEY_ENV = "STRIPE_LIVE_SECRET_KEY"
LIVE_SECRET_KEY_PREFIX = "sk_live_"

# Stripe's smallest USD charge is 0.50 (amounts are in the smallest currency
# unit), so it is the default for the live verification run.
DEFAULT_AMOUNT = 50
DEFAULT_CURRENCY = "usd"
DEFAULT_SUCCESS_URL = "https://example.com/payment/success"
DEFAULT_CANCEL_URL = "https://example.com/payment/cancel"


class ConfigurationError(RuntimeError):
    """The live key is missing or is not a live key."""


def live_secret_key() -> str:
    """Return the live secret key or explain exactly what is missing."""
    key = os.environ.get(LIVE_SECRET_KEY_ENV, "").strip()
    if not key:
        raise ConfigurationError(
            f"{LIVE_SECRET_KEY_ENV} is not set. Add your Stripe live secret "
            f"key as an environment secret of the protected 'stripe-live' "
            f"GitHub Actions environment, then re-run and approve the "
            f"workflow."
        )
    if not key.startswith(LIVE_SECRET_KEY_PREFIX):
        raise ConfigurationError(
            f"{LIVE_SECRET_KEY_ENV} must be a live Stripe secret key "
            f"({LIVE_SECRET_KEY_PREFIX}...); refusing to charge with a "
            f"non-live key."
        )
    return key


def create_checkout_session(
    *,
    amount: int = DEFAULT_AMOUNT,
    currency: str = DEFAULT_CURRENCY,
    success_url: str = DEFAULT_SUCCESS_URL,
    cancel_url: str = DEFAULT_CANCEL_URL,
) -> "stripe.checkout.Session":
    """Create a hosted Checkout Session and return it (``session.url``)."""
    stripe.api_key = live_secret_key()
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount,
                    "product_data": {"name": "Orbi live payment"},
                },
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
    )


def create_live_charge(
    *,
    payment_method: str,
    amount: int = DEFAULT_AMOUNT,
    currency: str = DEFAULT_CURRENCY,
    customer: str | None = None,
    idempotency_key: str | None = None,
) -> "stripe.PaymentIntent":
    """Charge the pre-created payment method with the live key.

    ``customer`` is only needed when the payment method is attached to a
    Stripe customer (Stripe requires the customer id in that case).
    ``idempotency_key`` makes a retried call reuse the first PaymentIntent
    instead of charging the card again; omitted, Stripe generates one per
    request as before.
    """
    stripe.api_key = live_secret_key()
    params = {
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "confirm": True,
        "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
    }
    if customer:
        params["customer"] = customer
    if idempotency_key:
        params["idempotency_key"] = idempotency_key
    return stripe.PaymentIntent.create(**params)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stripe_payments", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    checkout = subcommands.add_parser(
        "checkout", help="create a hosted Checkout Session and print its URL"
    )
    checkout.add_argument("--amount", type=int, default=DEFAULT_AMOUNT)
    checkout.add_argument("--currency", default=DEFAULT_CURRENCY)
    checkout.add_argument("--success-url", default=DEFAULT_SUCCESS_URL)
    checkout.add_argument("--cancel-url", default=DEFAULT_CANCEL_URL)

    verify = subcommands.add_parser(
        "verify",
        help="confirm a live PaymentIntent with a pre-created payment method",
    )
    verify.add_argument("--payment-method", required=True)
    verify.add_argument("--amount", type=int, default=DEFAULT_AMOUNT)
    verify.add_argument("--currency", default=DEFAULT_CURRENCY)
    verify.add_argument(
        "--customer",
        default=None,
        help="customer id (cus_...) of an attached payment method",
    )
    verify.add_argument(
        "--idempotency-key",
        default=None,
        help=(
            "Stripe Idempotency-Key; a re-run with the same key reuses the "
            "first PaymentIntent instead of charging again"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.amount <= 0:
            raise ConfigurationError(f"--amount must be positive, got {args.amount}")
        if args.command == "checkout":
            session = create_checkout_session(
                amount=args.amount,
                currency=args.currency,
                success_url=args.success_url,
                cancel_url=args.cancel_url,
            )
            print(f"checkout_session id={session.id} url={session.url}")
            return 0
        idempotency_key = args.idempotency_key
        if idempotency_key is not None and not idempotency_key.strip():
            raise ConfigurationError(
                f"--idempotency-key must not be empty, got {idempotency_key!r}"
            )
        intent = create_live_charge(
            payment_method=args.payment_method,
            amount=args.amount,
            currency=args.currency,
            customer=args.customer or None,
            idempotency_key=idempotency_key,
        )
        print(f"payment_intent id={intent.id} status={intent.status}")
        return 0 if intent.status == "succeeded" else 1
    except ConfigurationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except stripe.StripeError as error:
        print(
            f"error: Stripe API call failed "
            f"(HTTP {getattr(error, 'http_status', None)}): {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
