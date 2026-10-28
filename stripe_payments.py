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
* ``python -m stripe_payments export`` lists the account's PaymentIntents,
  Refunds and Customers and writes them into a directory, so the operator can
  take the data elsewhere.  ``--format csv|json|both`` picks the file types
  (``both`` by default), so an operator who only needs CSV no longer has to
  delete the JSON files by hand.  ``--customer cus_...`` narrows the export to
  one customer's payments and refunds (``payments.csv`` then carries a
  ``customer`` column); omitted, the whole account is exported as before.
* ``python -m stripe_payments summary`` prints the payments total, the refunds
  total and the net income per currency, one currency per line, so a daily
  check does not need the exported CSV files.

The live secret key is read from the ``STRIPE_LIVE_SECRET_KEY`` environment
variable (an environment secret of the protected ``stripe-live`` GitHub
Actions environment).  It is never passed on the command line and never
written to disk.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
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

# Issue #106 `export`: how many records to pull per list call (Stripe caps a
# single list call at 100), and where the exported files land by default.
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
DEFAULT_OUTPUT_DIR = "export"
EXPORT_COLUMNS = {
    "payments": ("id", "amount", "currency", "status", "created"),
    "refunds": (
        "id",
        "payment_intent",
        "amount",
        "currency",
        "status",
        "created",
    ),
    "customers": ("id", "email", "created"),
}

# Stripe keeps amounts in the smallest currency unit, but these currencies have
# no minor unit: 500 is 500 JPY, not 5.00 JPY (docs.stripe.com/currencies,
# "Zero-decimal currencies").  Every other currency uses two decimals.
# UGX is listed as zero-decimal on that page, but the "Special cases" section on
# the same page requires its amount values to be the two-decimal value (500
# means 5 UGX), so UGX is formatted like the two-decimal currencies.
ZERO_DECIMAL_CURRENCIES = frozenset(
    "bif clp djf gnf jpy kmf krw mga pyg rwf vnd vuv xaf xof xpf".split()
)


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


def _list_all(resource, *, limit: int, params: dict | None = None):
    """Yield every record of a Stripe list, following pagination to the end.

    ``limit`` is the page size (Stripe caps one list call at 100); the
    official SDK's ``auto_paging_iter()`` keeps requesting the next page
    (``starting_after`` = last id) until ``has_more`` is false, so no record
    beyond the first page is dropped.  ``params`` are the documented list
    filters (for example the PaymentIntents list's ``customer``).
    """
    return resource.list(limit=limit, **(params or {})).auto_paging_iter()


def export_data(
    *,
    output_dir: str,
    formats: Sequence[str],
    limit: int,
    customer: str | None = None,
) -> tuple[int, int, int]:
    """Read the three Stripe lists, then write CSV/JSON files for them.

    ``customer`` narrows payments and refunds to one customer (Issue #223).
    The PaymentIntents list takes a documented ``customer`` filter, so Stripe
    returns only that customer's payments.  The Refunds list has no
    ``customer`` filter, so the refunds are narrowed to the ones whose
    ``payment_intent`` is one of those payments.

    Every page of all three lists is fetched before any file is written, so a
    failing Stripe call (anywhere in the pagination) leaves no half-written
    export behind.
    """
    stripe.api_key = live_secret_key()
    payment_filters = {"customer": customer} if customer else {}
    payments = list(
        _list_all(stripe.PaymentIntent, limit=limit, params=payment_filters)
    )
    payment_intent_ids = {payment.id for payment in payments}
    refunds = [
        refund
        for refund in _list_all(stripe.Refund, limit=limit)
        if customer is None or refund.payment_intent in payment_intent_ids
    ]
    rows = {
        "payments": [
            _payment_row(payment, customer=customer) for payment in payments
        ],
        "refunds": [_refund_row(refund) for refund in refunds],
        "customers": [
            _customer_row(customer_record)
            for customer_record in _list_all(stripe.Customer, limit=limit)
        ],
    }

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    for category, columns in EXPORT_COLUMNS.items():
        if category == "payments" and customer is not None:
            columns = _payment_columns()
        category_rows = rows[category]
        if "csv" in formats:
            _write_csv(directory / f"{category}.csv", columns, category_rows)
        if "json" in formats:
            _write_json(directory / f"{category}.json", category_rows)
    return len(rows["payments"]), len(rows["refunds"]), len(rows["customers"])


def summarize_data() -> dict[str, tuple[int, int]]:
    """Return ``{currency: (payments_total, refunds_total)}`` for the account.

    Every page of the PaymentIntents and Refunds lists is read, so the totals
    cover the whole account, not only the first page.
    """
    stripe.api_key = live_secret_key()
    totals: dict[str, list[int]] = {}
    for payment in _list_all(stripe.PaymentIntent, limit=DEFAULT_LIMIT):
        totals.setdefault(payment.currency.lower(), [0, 0])[0] += payment.amount
    for refund in _list_all(stripe.Refund, limit=DEFAULT_LIMIT):
        totals.setdefault(refund.currency.lower(), [0, 0])[1] += refund.amount
    return {
        currency: (payments, refunds)
        for currency, (payments, refunds) in totals.items()
    }


def _format_number(amount: int, currency: str) -> str:
    """Format a Stripe minor-unit amount without the currency code."""
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return f"{amount:,}"
    sign = "-" if amount < 0 else ""
    major, minor = divmod(abs(amount), 100)
    return f"{sign}{major:,}.{minor:02d}"


def format_amount(amount: int, currency: str) -> str:
    """Format a Stripe amount as ``1,234.56 USD`` (Issue #221)."""
    return f"{_format_number(amount, currency)} {currency.upper()}"


def _summary_line(currency: str, payments: int, refunds: int) -> str:
    """One summary line for a currency, e.g. ``USD 付款 1,234.56 ...``."""
    return (
        f"{currency.upper()} 付款 {_format_number(payments, currency)} "
        f"退款 {_format_number(refunds, currency)} "
        f"净额 {_format_number(payments - refunds, currency)}"
    )


def _created(value: object) -> str:
    """Format Stripe's UTC epoch seconds as ``YYYY-MM-DDTHH:MM:SSZ``."""
    return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _payment_columns() -> tuple[str, ...]:
    """The payments columns of a ``--customer`` export: the filter is a column."""
    columns = EXPORT_COLUMNS["payments"]
    return (columns[0], "customer") + columns[1:]


def _payment_row(
    payment: "stripe.PaymentIntent", *, customer: str | None = None
) -> dict:
    """One payments row; a ``--customer`` export carries that customer id.

    The list itself is filtered by this customer on Stripe's side, so every
    exported payment belongs to it.
    """
    row = {"id": payment.id}
    if customer is not None:
        row["customer"] = customer
    row.update(
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        created=_created(payment.created),
    )
    return row


def _refund_row(refund: "stripe.Refund") -> dict:
    return {
        "id": refund.id,
        "payment_intent": refund.payment_intent,
        "amount": refund.amount,
        "currency": refund.currency,
        "status": refund.status,
        "created": _created(refund.created),
    }


def _customer_row(customer: "stripe.Customer") -> dict:
    return {
        "id": customer.id,
        "email": getattr(customer, "email", None) or "",
        "created": _created(customer.created),
    }


def _write_csv(path: Path, columns: Sequence[str], rows: Sequence[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: Sequence[dict]) -> None:
    path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


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

    subcommands.add_parser(
        "summary",
        help=(
            "print payments, refunds and net income totals per currency, "
            "one currency per line"
        ),
    )

    export = subcommands.add_parser(
        "export",
        help="export payments, refunds and customers to CSV and JSON files",
    )
    export.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"directory to write the export files into (default {DEFAULT_OUTPUT_DIR})",
    )
    export.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            f"records per list request, 1-{MAX_LIMIT} "
            f"(default {DEFAULT_LIMIT}); every record is exported"
        ),
    )
    export.add_argument(
        "--format",
        choices=("csv", "json", "both"),
        default="both",
        help="which files to write (default both)",
    )
    export.add_argument(
        "--customer",
        default=None,
        help=(
            "only export this customer's payments and refunds (cus_...); "
            "omitted, every record is exported"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command in ("checkout", "verify") and args.amount <= 0:
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
        if args.command == "verify":
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
        if args.command == "summary":
            totals = summarize_data()
            for currency in sorted(totals):
                payments, refunds = totals[currency]
                print(_summary_line(currency, payments, refunds))
            return 0
        if args.limit < 1 or args.limit > MAX_LIMIT:
            raise ConfigurationError(
                f"--limit must be between 1 and {MAX_LIMIT}, got {args.limit}"
            )
        if args.customer is not None and not args.customer.strip():
            raise ConfigurationError(
                f"--customer must not be empty, got {args.customer!r}"
            )
        formats = ("csv", "json") if args.format == "both" else (args.format,)
        payments, refunds, customers = export_data(
            output_dir=args.output_dir,
            formats=formats,
            limit=args.limit,
            customer=args.customer or None,
        )
        print(
            f"exported payments={payments} refunds={refunds} "
            f"customers={customers} to {Path(args.output_dir)}/"
        )
        return 0
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
