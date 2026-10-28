"""Tests for the Stripe live payment entry points.

The tests drive the *real* official `stripe` SDK against a local HTTP
recorder, so they assert Stripe's documented wire contract (request path,
``Authorization`` header and form fields), not a shape the implementation
guessed.  No network and no keys are required.
"""

import csv
import json
import os
import re
import runpy
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import stripe

import stripe_payments

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Recorder:
    def __init__(self):
        self.requests = []
        self.status = 200
        self.payload = {}
        # Per-path responses for the list (GET) endpoints: the export command
        # queries three different resources in one run.
        self.list_payloads = {}
        self.list_statuses = {}
        # Per-path cursor pages, keyed by the `starting_after` cursor the SDK
        # sends (``None`` for the first request).  Stripe paginates by the id
        # of the last record on the previous page.
        self.list_pages = {}
        self.list_page_statuses = {}

    def record(self, path, headers, body):
        self.requests.append(
            {
                "path": path,
                "authorization": headers.get("Authorization"),
                "idempotency_key": headers.get("Idempotency-Key"),
                "form": urllib.parse.parse_qs(body),
            }
        )


class _StripeServer:
    """A local HTTP server that records the requests the Stripe SDK sends."""

    def __init__(self, recorder):
        recorder_self = recorder

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status, payload):
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                recorder_self.record(self.path, self.headers, body)
                self._send_json(recorder_self.status, recorder_self.payload)

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                recorder_self.record(
                    parsed.path, self.headers, parsed.query
                )
                params = urllib.parse.parse_qs(parsed.query)
                starting_after = params.get("starting_after", [None])[0]
                if parsed.path in recorder_self.list_pages:
                    status = recorder_self.list_page_statuses.get(
                        (parsed.path, starting_after), recorder_self.status
                    )
                    payload = recorder_self.list_pages[parsed.path][starting_after]
                else:
                    status = recorder_self.list_statuses.get(
                        parsed.path, recorder_self.status
                    )
                    payload = recorder_self.list_payloads.get(
                        parsed.path, {"object": "list", "data": []}
                    )
                # Stripe's list responses carry the collection ``url``; the SDK
                # needs it to follow pagination to the next page.
                if payload.get("object") == "list" and "url" not in payload:
                    payload = {**payload, "url": parsed.path}
                self._send_json(status, payload)

            def log_message(self, *args):  # keep pytest output clean
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True
        )
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def stop(self):
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def stripe_api(monkeypatch):
    recorder = _Recorder()
    server = _StripeServer(recorder)
    monkeypatch.setattr(stripe, "api_base", server.base_url)
    yield recorder
    server.stop()


@pytest.fixture
def live_key(monkeypatch):
    monkeypatch.setenv(stripe_payments.LIVE_SECRET_KEY_ENV, "sk_live_test_key")


def test_live_secret_key_names_the_missing_environment_variable(monkeypatch):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    with pytest.raises(stripe_payments.ConfigurationError) as excinfo:
        stripe_payments.live_secret_key()
    assert stripe_payments.LIVE_SECRET_KEY_ENV in str(excinfo.value)


def test_live_secret_key_refuses_a_non_live_key(monkeypatch):
    monkeypatch.setenv(stripe_payments.LIVE_SECRET_KEY_ENV, "sk_test_123")
    with pytest.raises(stripe_payments.ConfigurationError) as excinfo:
        stripe_payments.live_secret_key()
    assert "sk_live_" in str(excinfo.value)


def test_create_live_charge_sends_the_documented_request(live_key, stripe_api):
    stripe_api.payload = {
        "id": "pi_live_123",
        "object": "payment_intent",
        "amount": 50,
        "currency": "usd",
        "status": "succeeded",
    }
    intent = stripe_payments.create_live_charge(
        payment_method="pm_abc", amount=50, currency="usd"
    )

    assert intent.id == "pi_live_123"
    assert intent.status == "succeeded"

    request = stripe_api.requests[-1]
    assert request["path"] == "/v1/payment_intents"
    assert request["authorization"] == "Bearer sk_live_test_key"
    form = request["form"]
    assert form["amount"] == ["50"]
    assert form["currency"] == ["usd"]
    assert form["payment_method"] == ["pm_abc"]
    assert form["confirm"] == ["true"]
    assert form["automatic_payment_methods[enabled]"] == ["true"]
    assert form["automatic_payment_methods[allow_redirects]"] == ["never"]
    assert "customer" not in form


def test_create_live_charge_sends_the_idempotency_key(live_key, stripe_api):
    stripe_api.payload = {
        "id": "pi_live_123",
        "object": "payment_intent",
        "status": "succeeded",
    }
    stripe_payments.create_live_charge(
        payment_method="pm_abc", idempotency_key="20261005"
    )

    request = stripe_api.requests[-1]
    assert request["path"] == "/v1/payment_intents"
    assert request["idempotency_key"] == "20261005"


def test_create_live_charge_sends_the_customer_when_provided(live_key, stripe_api):
    stripe_api.payload = {
        "id": "pi_live_1",
        "object": "payment_intent",
        "status": "succeeded",
    }
    stripe_payments.create_live_charge(payment_method="pm_abc", customer="cus_123")

    form = stripe_api.requests[-1]["form"]
    assert form["customer"] == ["cus_123"]


def test_create_checkout_session_sends_the_documented_request(live_key, stripe_api):
    stripe_api.payload = {
        "id": "cs_live_123",
        "object": "checkout.session",
        "url": "https://checkout.stripe.com/c/pay/cs_live_123",
    }
    session = stripe_payments.create_checkout_session(
        amount=100,
        currency="cny",
        success_url="https://example.com/ok",
        cancel_url="https://example.com/no",
    )

    assert session.url == "https://checkout.stripe.com/c/pay/cs_live_123"

    request = stripe_api.requests[-1]
    assert request["path"] == "/v1/checkout/sessions"
    form = request["form"]
    assert form["mode"] == ["payment"]
    assert form["line_items[0][quantity]"] == ["1"]
    assert form["line_items[0][price_data][currency]"] == ["cny"]
    assert form["line_items[0][price_data][unit_amount]"] == ["100"]
    assert form["success_url"] == ["https://example.com/ok"]
    assert form["cancel_url"] == ["https://example.com/no"]


def test_a_bad_key_raises_stripe_authentication_error(live_key, stripe_api):
    stripe_api.status = 401
    stripe_api.payload = {
        "error": {
            "type": "invalid_request_error",
            "message": "Invalid API Key provided",
        }
    }
    with pytest.raises(stripe.AuthenticationError) as excinfo:
        stripe_payments.create_live_charge(payment_method="pm_abc")
    assert excinfo.value.http_status == 401


def test_cli_verify_logs_the_payment_intent_and_succeeds(live_key, stripe_api, capsys):
    stripe_api.payload = {
        "id": "pi_live_123",
        "object": "payment_intent",
        "status": "succeeded",
    }
    exit_code = stripe_payments.main(["verify", "--payment-method", "pm_abc"])

    assert exit_code == 0
    assert "payment_intent id=pi_live_123 status=succeeded" in capsys.readouterr().out


def test_cli_verify_sends_the_idempotency_key(live_key, stripe_api, capsys):
    stripe_api.payload = {
        "id": "pi_live_123",
        "object": "payment_intent",
        "status": "succeeded",
    }
    exit_code = stripe_payments.main(
        [
            "verify",
            "--payment-method",
            "pm_abc",
            "--idempotency-key",
            "20261005",
        ]
    )

    assert exit_code == 0
    assert stripe_api.requests[-1]["idempotency_key"] == "20261005"


def test_cli_verify_rejects_an_empty_idempotency_key(
    live_key, stripe_api, capsys
):
    exit_code = stripe_payments.main(
        ["verify", "--payment-method", "pm_abc", "--idempotency-key", ""]
    )

    assert exit_code == 2
    assert "--idempotency-key must not be empty" in capsys.readouterr().err
    assert stripe_api.requests == []


def test_verify_help_lists_the_idempotency_key_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["verify", "--help"])

    assert excinfo.value.code == 0
    assert "--idempotency-key" in capsys.readouterr().out


def test_cli_verify_fails_when_the_charge_did_not_succeed(live_key, stripe_api, capsys):
    stripe_api.payload = {
        "id": "pi_live_9",
        "object": "payment_intent",
        "status": "requires_action",
    }
    exit_code = stripe_payments.main(["verify", "--payment-method", "pm_abc"])

    assert exit_code == 1
    assert "status=requires_action" in capsys.readouterr().out


def test_cli_verify_without_the_secret_fails_and_names_it(
    monkeypatch, stripe_api, capsys
):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    exit_code = stripe_payments.main(["verify", "--payment-method", "pm_abc"])

    assert exit_code == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err
    assert stripe_api.requests == []


def test_cli_verify_surfaces_the_stripe_401(live_key, stripe_api, capsys):
    stripe_api.status = 401
    stripe_api.payload = {
        "error": {
            "type": "invalid_request_error",
            "message": "Invalid API Key provided",
        }
    }
    exit_code = stripe_payments.main(["verify", "--payment-method", "pm_abc"])

    assert exit_code == 1
    assert "HTTP 401" in capsys.readouterr().err


def test_cli_checkout_prints_the_hosted_page_url(live_key, stripe_api, capsys):
    stripe_api.payload = {
        "id": "cs_live_1",
        "object": "checkout.session",
        "url": "https://checkout.stripe.com/c/pay/cs_live_1",
    }
    exit_code = stripe_payments.main(
        ["checkout", "--amount", "100", "--currency", "cny"]
    )

    assert exit_code == 0
    assert (
        "checkout_session id=cs_live_1 "
        "url=https://checkout.stripe.com/c/pay/cs_live_1"
        in capsys.readouterr().out
    )


def test_cli_rejects_a_non_positive_amount(live_key, stripe_api, capsys):
    exit_code = stripe_payments.main(
        ["verify", "--payment-method", "pm_abc", "--amount", "0"]
    )

    assert exit_code == 2
    assert "--amount must be positive" in capsys.readouterr().err
    assert stripe_api.requests == []


def test_module_runs_as_a_command_and_fails_without_the_secret(monkeypatch):
    """The real user entry point: ``python -m stripe_payments verify``."""
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stripe_payments",
            "verify",
            "--payment-method",
            "pm_abc",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# Issue #254: `python -m stripe_payments --version` prints the version number
# and exits 0; without `--version` every other command behaves as before.
def test_cli_version_prints_the_version_number_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["--version"])

    assert excinfo.value.code == 0
    assert (
        capsys.readouterr().out.strip()
        == f"stripe_payments {stripe_payments.VERSION}"
    )


def test_module_version_prints_the_version_number_and_exits_zero():
    """The real user entry point: ``python -m stripe_payments --version``."""
    result = subprocess.run(
        [sys.executable, "-m", "stripe_payments", "--version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0
    assert re.fullmatch(r"\d+\.\d+\.\d+", stripe_payments.VERSION)
    assert result.stdout.strip() == f"stripe_payments {stripe_payments.VERSION}"
    assert result.stderr == ""


def test_cli_without_version_still_requires_a_subcommand(capsys):
    """Without `--version` the command line keeps its old behaviour."""
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main([])

    assert excinfo.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_guard_exits_with_the_cli_result(monkeypatch, capsys):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["stripe_payments", "verify", "--payment-method", "pm_abc"],
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("stripe_payments", run_name="__main__", alter_sys=True)

    assert excinfo.value.code == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err


# --- export (Issue #106) -------------------------------------------------


def _list_payload(*items, has_more=False):
    return {"object": "list", "data": list(items), "has_more": has_more}


# Issue #230: every exported file carries the UTC export date in its name.
EXPORT_DATE = "2026-10-28"


@pytest.fixture
def export_date(monkeypatch):
    """Pin the export date, so the exported file names are deterministic."""
    monkeypatch.setattr(stripe_payments, "export_date", lambda: EXPORT_DATE)
    return EXPORT_DATE


def _export_file(output_dir, name, extension, date=EXPORT_DATE):
    """The dated export file, e.g. ``payments-2026-10-28.csv``."""
    return output_dir / f"{name}-{date}.{extension}"


@pytest.fixture
def stripe_lists(stripe_api):
    """The three GET list responses the export command reads."""
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            {
                "id": "pi_1",
                "object": "payment_intent",
                "customer": "cus_1",
                "amount": 100,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000000,
            }
        ),
        "/v1/refunds": _list_payload(
            {
                "id": "re_1",
                "object": "refund",
                "payment_intent": "pi_1",
                "amount": 100,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000100,
            }
        ),
        "/v1/customers": _list_payload(
            {
                "id": "cus_1",
                "object": "customer",
                "email": "buyer@example.com",
                "created": 1700000200,
            },
            {
                "id": "cus_2",
                "object": "customer",
                "created": 1700000300,
            },
        ),
    }
    return stripe_api


def test_cli_export_writes_csv_and_json_for_every_category(
    live_key, stripe_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(["export", "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (
        f"exported payments=1 refunds=1 customers=2 to {output_dir}/"
        in capsys.readouterr().out
    )
    assert [
        request["form"].get("limit") for request in stripe_lists.requests
    ] == [["10"], ["10"], ["10"]]

    csv_rows = {
        name: list(
            csv.reader(
                _export_file(output_dir, name, "csv").open(
                    newline="", encoding="utf-8"
                )
            )
        )
        for name in ("payments", "refunds", "customers")
    }
    # Issue #235: the CSV header row is the Chinese column name the operator
    # reads in a spreadsheet; the JSON keys stay the English field names.
    # Issue #239: the payments CSV ends with the paying customer's email.
    assert csv_rows["payments"] == [
        ["编号", "金额", "币种", "状态", "创建时间", "客户邮箱"],
        [
            "pi_1",
            "100",
            "usd",
            "succeeded",
            "2023-11-14T22:13:20Z",
            "buyer@example.com",
        ],
    ]
    assert csv_rows["refunds"] == [
        ["编号", "付款编号", "金额", "币种", "状态", "创建时间"],
        ["re_1", "pi_1", "100", "usd", "succeeded", "2023-11-14T22:15:00Z"],
    ]
    assert csv_rows["customers"] == [
        ["编号", "邮箱", "创建时间"],
        ["cus_1", "buyer@example.com", "2023-11-14T22:16:40Z"],
        ["cus_2", "", "2023-11-14T22:18:20Z"],
    ]

    json_data = {
        name: json.loads(
            _export_file(output_dir, name, "json").read_text(encoding="utf-8")
        )
        for name in ("payments", "refunds", "customers")
    }
    assert json_data["payments"] == [
        {
            "id": "pi_1",
            "amount": 100,
            "currency": "usd",
            "status": "succeeded",
            "created": "2023-11-14T22:13:20Z",
            "customer_email": "buyer@example.com",
        }
    ]
    assert json_data["refunds"] == [
        {
            "id": "re_1",
            "payment_intent": "pi_1",
            "amount": 100,
            "currency": "usd",
            "status": "succeeded",
            "created": "2023-11-14T22:15:00Z",
        }
    ]
    assert json_data["customers"] == [
        {"id": "cus_1", "email": "buyer@example.com", "created": "2023-11-14T22:16:40Z"},
        {"id": "cus_2", "email": "", "created": "2023-11-14T22:18:20Z"},
    ]


def test_export_queries_the_three_documented_list_endpoints(
    live_key, stripe_lists, tmp_path
):
    stripe_payments.main(
        [
            "export",
            "--output-dir",
            str(tmp_path / "export"),
            "--limit",
            "25",
        ]
    )

    assert [
        (request["path"], request["form"].get("limit"))
        for request in stripe_lists.requests
    ] == [
        ("/v1/payment_intents", ["25"]),
        ("/v1/refunds", ["25"]),
        ("/v1/customers", ["25"]),
    ]
    assert all(
        request["authorization"] == "Bearer sk_live_test_key"
        for request in stripe_lists.requests
    )


def test_cli_export_format_narrows_the_written_files(
    live_key, stripe_lists, export_date, tmp_path
):
    csv_dir = tmp_path / "csv"
    json_dir = tmp_path / "json"
    assert (
        stripe_payments.main(
            ["export", "--output-dir", str(csv_dir), "--format", "csv"]
        )
        == 0
    )
    assert sorted(path.name for path in csv_dir.iterdir()) == [
        "customers-2026-10-28.csv",
        "payments-2026-10-28.csv",
        "refunds-2026-10-28.csv",
    ]
    assert (
        stripe_payments.main(
            ["export", "--output-dir", str(json_dir), "--format", "json"]
        )
        == 0
    )
    assert sorted(path.name for path in json_dir.iterdir()) == [
        "customers-2026-10-28.json",
        "payments-2026-10-28.json",
        "refunds-2026-10-28.json",
    ]


def test_cli_export_format_both_writes_both_files(
    live_key, stripe_lists, export_date, tmp_path
):
    output_dir = tmp_path / "both"
    assert (
        stripe_payments.main(
            ["export", "--output-dir", str(output_dir), "--format", "both"]
        )
        == 0
    )
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "customers-2026-10-28.csv",
        "customers-2026-10-28.json",
        "payments-2026-10-28.csv",
        "payments-2026-10-28.json",
        "refunds-2026-10-28.csv",
        "refunds-2026-10-28.json",
    ]
    # Explicit `both` writes the same content as the default (no flag).
    assert json.loads(
        _export_file(output_dir, "payments", "json").read_text(encoding="utf-8")
    ) == [
        {
            "id": "pi_1",
            "amount": 100,
            "currency": "usd",
            "status": "succeeded",
            "created": "2023-11-14T22:13:20Z",
            "customer_email": "buyer@example.com",
        }
    ]
    csv_header = next(
        csv.reader(
            _export_file(output_dir, "payments", "csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert csv_header == [
        "编号",
        "金额",
        "币种",
        "状态",
        "创建时间",
        "客户邮箱",
    ]


def test_every_exported_csv_header_is_a_chinese_column_name(
    live_key, stripe_lists, export_date, tmp_path
):
    """Issue #235 Acceptance: the first CSV line is readable Chinese headers.

    The internal column keys stay English so the JSON files keep the field
    names their consumers already read; only the CSV header row is translated.
    """
    output_dir = tmp_path / "export"
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    expected_headers = {
        "payments": ["编号", "金额", "币种", "状态", "创建时间", "客户邮箱"],
        "refunds": ["编号", "付款编号", "金额", "币种", "状态", "创建时间"],
        "customers": ["编号", "邮箱", "创建时间"],
    }
    for name, expected in expected_headers.items():
        rows = _csv_rows(output_dir, name)
        assert rows[0] == expected
        # No header cell may fall back to the internal English key (a missed
        # translation would show up as an ASCII cell).
        assert all(not cell.isascii() for cell in rows[0]), rows[0]

    # The data rows are unchanged: the same number of rows as the JSON lists.
    for name in expected_headers:
        assert len(_csv_rows(output_dir, name)) - 1 == len(
            json.loads(
                _export_file(output_dir, name, "json").read_text(encoding="utf-8")
            )
        )


def test_export_file_names_carry_todays_utc_date(live_key, stripe_lists, tmp_path):
    """Issue #230: by default every file is named after today's UTC date."""
    output_dir = tmp_path / "export"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    # A run that crosses midnight UTC may legitimately use either day; the
    # test reads it independently from the implementation.
    dates = {today, datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    names = {path.name for path in output_dir.iterdir()}
    assert len(names) == 6
    for name in ("payments", "refunds", "customers"):
        for extension in ("csv", "json"):
            assert any(
                f"{name}-{date}.{extension}" in names for date in dates
            ), f"missing a dated {name}.{extension}: {sorted(names)}"


def test_exports_from_different_days_keep_both_file_sets(
    live_key, stripe_lists, tmp_path, monkeypatch
):
    """Issue #230: yesterday's export is not overwritten by today's."""
    output_dir = tmp_path / "export"
    monkeypatch.setattr(stripe_payments, "export_date", lambda: "2026-10-27")
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0
    monkeypatch.setattr(stripe_payments, "export_date", lambda: "2026-10-28")
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    assert sorted(path.name for path in output_dir.iterdir()) == sorted(
        f"{name}-{date}.{extension}"
        for date in ("2026-10-27", "2026-10-28")
        for name in ("payments", "refunds", "customers")
        for extension in ("csv", "json")
    )


def test_cli_export_without_the_secret_creates_nothing(
    monkeypatch, stripe_api, tmp_path, capsys
):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(["export", "--output-dir", str(output_dir)])

    assert exit_code == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err
    assert not output_dir.exists()
    assert stripe_api.requests == []


@pytest.mark.parametrize("limit", ["0", "-1", "101"])
def test_cli_export_rejects_an_out_of_range_limit(
    live_key, stripe_api, tmp_path, capsys, limit
):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        ["export", "--output-dir", str(output_dir), "--limit", limit]
    )

    assert exit_code == 2
    assert "--limit" in capsys.readouterr().err
    assert not output_dir.exists()
    assert stripe_api.requests == []


def test_cli_export_rejects_an_unknown_format(live_key, stripe_api, tmp_path, capsys):
    output_dir = tmp_path / "export"
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(
            ["export", "--output-dir", str(output_dir), "--format", "xml"]
        )

    assert excinfo.value.code == 2
    assert "--format" in capsys.readouterr().err
    assert not output_dir.exists()
    assert stripe_api.requests == []


def test_export_writes_nothing_when_a_later_list_fails(
    live_key, stripe_api, tmp_path, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            {
                "id": "pi_1",
                "object": "payment_intent",
                "amount": 100,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000000,
            }
        ),
        "/v1/refunds": {
            "error": {"type": "invalid_request_error", "message": "boom"}
        },
    }
    stripe_api.list_statuses = {"/v1/refunds": 401}

    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(["export", "--output-dir", str(output_dir)])

    assert exit_code == 1
    assert [request["path"] for request in stripe_api.requests] == [
        "/v1/payment_intents",
        "/v1/refunds",
    ]
    assert not output_dir.exists()


def test_export_help_lists_its_options(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["export", "--help"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--output-dir" in out
    assert "--limit" in out
    # The documented contract: exactly these three choices, both by default.
    assert "--format {csv,json,both}" in out
    assert "default both" in out


def test_module_export_fails_without_the_secret_and_creates_nothing(tmp_path):
    """The real user entry point: ``python -m stripe_payments export``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    output_dir = tmp_path / "export"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stripe_payments",
            "export",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr
    assert not output_dir.exists()


# --- export pagination (Issue #112) -------------------------------------


def _payment(index):
    return {
        "id": f"pi_{index}",
        "object": "payment_intent",
        "amount": 100 * index,
        "currency": "usd",
        "status": "succeeded",
        "created": 1700000000 + index,
    }


def _refund(index):
    return {
        "id": f"re_{index}",
        "object": "refund",
        "payment_intent": f"pi_{index}",
        "amount": 100 * index,
        "currency": "usd",
        "status": "succeeded",
        "created": 1700000100 + index,
    }


def _customer(index):
    return {
        "id": f"cus_{index}",
        "object": "customer",
        "email": f"buyer{index}@example.com",
        "created": 1700000200 + index,
    }


def _csv_data_rows(output_dir, name):
    rows = list(
        csv.reader(
            _export_file(output_dir, name, "csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    return rows[1:]


def test_export_follows_pagination_to_the_end(
    live_key, stripe_api, export_date, tmp_path, capsys
):
    """The first page is followed to ``has_more: false`` (Issue #112)."""
    stripe_api.list_payloads = {
        "/v1/refunds": _list_payload(_refund(1)),
        "/v1/customers": _list_payload(_customer(1)),
    }
    stripe_api.list_pages = {
        "/v1/payment_intents": {
            None: _list_payload(_payment(1), has_more=True),
            "pi_1": _list_payload(_payment(2), _payment(3)),
        }
    }

    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(["export", "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (
        f"exported payments=3 refunds=1 customers=1 to {output_dir}/"
        in capsys.readouterr().out
    )

    payment_requests = [
        request
        for request in stripe_api.requests
        if request["path"] == "/v1/payment_intents"
    ]
    assert [
        request["form"].get("starting_after") for request in payment_requests
    ] == [None, ["pi_1"]]
    assert [
        request["form"].get("limit") for request in payment_requests
    ] == [["10"], ["10"]]

    assert [row[0] for row in _csv_data_rows(output_dir, "payments")] == [
        "pi_1",
        "pi_2",
        "pi_3",
    ]

    json_payments = json.loads(
        _export_file(output_dir, "payments", "json").read_text(encoding="utf-8")
    )
    assert [row["id"] for row in json_payments] == ["pi_1", "pi_2", "pi_3"]

    # Acceptance: the stdout numbers are the CSV data row counts.
    for name, expected in (("payments", 3), ("refunds", 1), ("customers", 1)):
        assert len(_csv_data_rows(output_dir, name)) == expected


def test_export_single_page_makes_exactly_one_request_per_category(
    live_key, stripe_lists, tmp_path
):
    stripe_payments.main(["export", "--output-dir", str(tmp_path / "export")])

    assert [request["path"] for request in stripe_lists.requests] == [
        "/v1/payment_intents",
        "/v1/refunds",
        "/v1/customers",
    ]


def test_export_writes_nothing_when_a_later_page_fails(
    live_key, stripe_api, tmp_path, capsys
):
    stripe_api.list_pages = {
        "/v1/payment_intents": {
            None: _list_payload(_payment(1), has_more=True),
            "pi_1": {
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid API Key provided",
                }
            },
        }
    }
    stripe_api.list_page_statuses = {("/v1/payment_intents", "pi_1"): 401}

    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(["export", "--output-dir", str(output_dir)])

    assert exit_code == 1
    assert "HTTP 401" in capsys.readouterr().err
    assert [request["path"] for request in stripe_api.requests] == [
        "/v1/payment_intents",
        "/v1/payment_intents",
    ]
    assert [
        request["form"].get("starting_after") for request in stripe_api.requests
    ] == [None, ["pi_1"]]
    assert not output_dir.exists()


# --- summary (Issue #221) -----------------------------------------------


def _intent(identifier, amount, currency):
    return {
        "id": identifier,
        "object": "payment_intent",
        "amount": amount,
        "currency": currency,
        "status": "succeeded",
        "created": 1700000000,
    }


def _refund_record(identifier, amount, currency):
    return {
        "id": identifier,
        "object": "refund",
        "payment_intent": "pi_1",
        "amount": amount,
        "currency": currency,
        "status": "succeeded",
        "created": 1700000100,
    }


@pytest.fixture
def stripe_summary_lists(stripe_api):
    """Two currencies of payments and one refund, as the summary command reads them."""
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            _intent("pi_1", 123456, "usd"),
            _intent("pi_2", 1, "usd"),
            _intent("pi_3", 1000, "eur"),
        ),
        "/v1/refunds": _list_payload(_refund_record("re_1", 100, "usd")),
    }
    return stripe_api


def test_cli_summary_prints_one_formatted_line_per_currency(
    live_key, stripe_summary_lists, capsys
):
    exit_code = stripe_payments.main(["summary"])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        # One line per currency, sorted by currency code; thousands separators
        # and an upper-case currency code.
        "EUR 付款 10.00 退款 0.00 净额 10.00",
        "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        # Issue #243: the printed values add up to one total line.
        "合计 付款 1,244.57 退款 1.00 净额 1,243.57",
    ]


def test_summary_reads_payments_and_refunds_only(
    live_key, stripe_summary_lists, capsys
):
    stripe_payments.main(["summary"])

    assert [
        (request["path"], request["form"].get("limit"))
        for request in stripe_summary_lists.requests
    ] == [
        ("/v1/payment_intents", ["10"]),
        ("/v1/refunds", ["10"]),
    ]
    assert all(
        request["authorization"] == "Bearer sk_live_test_key"
        for request in stripe_summary_lists.requests
    )


def test_summary_totals_every_page(live_key, stripe_api, capsys):
    stripe_api.list_payloads = {"/v1/refunds": _list_payload()}
    stripe_api.list_pages = {
        "/v1/payment_intents": {
            None: _list_payload(_intent("pi_1", 123456, "usd"), has_more=True),
            "pi_1": _list_payload(_intent("pi_2", 1, "usd")),
        }
    }

    assert stripe_payments.main(["summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "USD 付款 1,234.57 退款 0.00 净额 1,234.57",
        "合计 付款 1,234.57 退款 0.00 净额 1,234.57",
    ]


def test_summary_prints_nothing_when_the_account_has_no_records(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }

    # No printed currency line means no total line either.
    assert stripe_payments.main(["summary"]) == 0
    assert capsys.readouterr().out == ""
    assert [request["path"] for request in stripe_api.requests] == [
        "/v1/payment_intents",
        "/v1/refunds",
    ]


def test_cli_summary_without_the_secret_names_the_variable(
    monkeypatch, stripe_api, capsys
):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)

    assert stripe_payments.main(["summary"]) == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err
    assert stripe_api.requests == []


def test_summary_help_describes_the_command(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "summary" in output
    assert "--currency" in output


# Issue #243: the command list promises the total line.
def test_cli_help_lists_the_summary_total_line(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["--help"])

    assert excinfo.value.code == 0
    # argparse wraps the subcommand help, so compare on collapsed whitespace.
    help_text = " ".join(capsys.readouterr().out.split())
    assert "one total line adding them up" in help_text


# Issue #234: `summary --currency usd` prints only the usd line; omitted, every
# currency is printed as before.
def test_cli_summary_currency_prints_only_that_currency_line(
    live_key, stripe_summary_lists, capsys
):
    exit_code = stripe_payments.main(["summary", "--currency", "usd"])

    assert exit_code == 0
    # Issue #243: the total only adds up the lines actually printed, so the
    # filtered run shows the usd total, not the all-currency one.
    assert capsys.readouterr().out.splitlines() == [
        "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        "合计 付款 1,234.57 退款 1.00 净额 1,233.57",
    ]


def test_cli_summary_currency_is_case_insensitive(
    live_key, stripe_summary_lists, capsys
):
    assert stripe_payments.main(["summary", "--currency", "USD"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        "合计 付款 1,234.57 退款 1.00 净额 1,233.57",
    ]


def test_cli_summary_currency_without_records_prints_nothing(
    live_key, stripe_summary_lists, capsys
):
    assert stripe_payments.main(["summary", "--currency", "jpy"]) == 0

    assert capsys.readouterr().out == ""
    # The totals still come from the real lists, so the account is read even
    # when the requested currency has no records.
    assert [
        request["path"] for request in stripe_summary_lists.requests
    ] == ["/v1/payment_intents", "/v1/refunds"]


def test_cli_summary_with_empty_currency_fails_before_calling_stripe(
    live_key, stripe_summary_lists, capsys
):
    assert stripe_payments.main(["summary", "--currency", ""]) == 2

    assert capsys.readouterr().err.strip() == (
        "error: --currency must not be empty, got ''"
    )
    assert stripe_summary_lists.requests == []


def test_module_summary_currency_fails_without_the_secret():
    """The real user entry point: ``python -m stripe_payments summary --currency usd``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stripe_payments",
            "summary",
            "--currency",
            "usd",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# Issue #243: the summary ends with one line adding up the printed currencies.
SUMMARY_FIELDS = ("付款", "退款", "净额")


def _printed_value(line, field):
    """The printed value after ``field`` in a summary line, e.g. ``1,234.57``."""
    fields = line.split()
    return Decimal(fields[fields.index(field) + 1].replace(",", ""))


def test_cli_summary_ends_with_the_all_currency_total_line(
    live_key, stripe_summary_lists, capsys
):
    """Acceptance: one extra line at the end of the output shows the total."""
    assert stripe_payments.main(["summary"]) == 0

    printed = capsys.readouterr().out.splitlines()
    assert printed[-1] == "合计 付款 1,244.57 退款 1.00 净额 1,243.57"


def test_summary_total_equals_the_sum_of_the_printed_currency_values(
    live_key, stripe_summary_lists, capsys
):
    """Acceptance: the total adds up exactly the values printed above it."""
    assert stripe_payments.main(["summary"]) == 0

    printed = capsys.readouterr().out.splitlines()
    currency_lines, total_line = printed[:-1], printed[-1]
    assert total_line.split()[0] == stripe_payments.SUMMARY_TOTAL_LABEL
    for field in SUMMARY_FIELDS:
        assert _printed_value(total_line, field) == sum(
            (_printed_value(line, field) for line in currency_lines),
            Decimal(0),
        )


def test_summary_total_adds_zero_decimal_currency_values(
    live_key, stripe_api, capsys
):
    """JPY 1,000 prints as 1,000, so the total counts 1,000, not 10.00."""
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            _intent("pi_1", 1000, "jpy"),
            _intent("pi_2", 123456, "usd"),
        ),
        "/v1/refunds": _list_payload(),
    }

    assert stripe_payments.main(["summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "JPY 付款 1,000 退款 0 净额 1,000",
        "USD 付款 1,234.56 退款 0.00 净额 1,234.56",
        "合计 付款 2,234.56 退款 0.00 净额 2,234.56",
    ]


def test_summary_total_keeps_a_negative_net(live_key, stripe_api, capsys):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(_intent("pi_1", 50, "usd")),
        "/v1/refunds": _list_payload(_refund_record("re_1", 100, "usd")),
    }

    assert stripe_payments.main(["summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "USD 付款 0.50 退款 1.00 净额 -0.50",
        "合计 付款 0.50 退款 1.00 净额 -0.50",
    ]


# Issue #240: `summary --csv` writes the printed summary rows into a CSV file
# the operator opens in Excel.

SUMMARY_CSV_HEADER = ["币种", "付款", "退款", "净额"]
SUMMARY_SAMPLE_LINES = [
    "EUR 付款 10.00 退款 0.00 净额 10.00",
    "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
]
SUMMARY_TOTAL_LINE = "合计 付款 1,244.57 退款 1.00 净额 1,243.57"


def _summary_csv_file(output_dir, date=EXPORT_DATE):
    """The dated summary CSV, e.g. ``summary-2026-10-28.csv``."""
    return output_dir / f"summary-{date}.csv"


def _summary_csv_rows(output_dir, date=EXPORT_DATE):
    return list(
        csv.reader(
            _summary_csv_file(output_dir, date).open(
                newline="", encoding="utf-8"
            )
        )
    )


def _summary_lines(printed):
    """The printed per-currency rows (the total and confirmation are not rows)."""
    return [
        line
        for line in printed
        if line.split()[1:2] == ["付款"]
        and not line.startswith(stripe_payments.SUMMARY_TOTAL_LABEL)
    ]


def test_cli_summary_csv_writes_a_dated_file_next_to_the_printed_lines(
    live_key, stripe_summary_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    exit_code = stripe_payments.main(
        ["summary", "--csv", "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    printed = capsys.readouterr().out.splitlines()
    assert _summary_lines(printed) == SUMMARY_SAMPLE_LINES
    # Issue #243: the total line prints after the currency rows, before the
    # file notice, so the notice stays the last printed line.
    assert printed[-2] == SUMMARY_TOTAL_LINE
    # The user sees where the file went, like `export` prints its destination.
    assert printed[-1] == (
        f"exported summary rows=2 to {_summary_csv_file(output_dir)}"
    )
    assert sorted(path.name for path in output_dir.iterdir()) == [
        f"summary-{EXPORT_DATE}.csv"
    ]
    assert _summary_csv_rows(output_dir) == [
        SUMMARY_CSV_HEADER,
        ["EUR", "10.00", "0.00", "10.00"],
        ["USD", "1,234.57", "1.00", "1,233.57"],
    ]


def test_summary_csv_rows_match_the_printed_summary_lines(
    live_key, stripe_summary_lists, export_date, tmp_path, capsys
):
    """Acceptance: the CSV rows and fields are the printed summary result."""
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            ["summary", "--csv", "--output-dir", str(output_dir)]
        )
        == 0
    )

    printed = _summary_lines(capsys.readouterr().out.splitlines())
    rows = _summary_csv_rows(output_dir)
    header, data_rows = rows[0], rows[1:]
    assert len(data_rows) == len(printed)
    for line, row in zip(printed, data_rows):
        fields = line.split()
        # The printed line is ``<币种> 付款 <值> 退款 <值> 净额 <值>``, so the
        # field labels must be the CSV header and the values the CSV row.
        assert fields[1::2] == header[1:]
        assert [fields[0], *fields[2::2]] == row


def test_summary_csv_has_one_column_per_summary_field_for_excel(
    live_key, stripe_summary_lists, export_date, tmp_path
):
    """Acceptance: Excel shows 币种/付款/退款/净额 as one column each."""
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            ["summary", "--csv", "--output-dir", str(output_dir)]
        )
        == 0
    )

    rows = _summary_csv_rows(output_dir)
    assert {len(row) for row in rows} == {len(SUMMARY_CSV_HEADER)}
    # The thousand separators are quoted, so Excel keeps `1,234.57` in one cell
    # instead of splitting the amount over two columns.
    text = _summary_csv_file(output_dir).read_text(encoding="utf-8")
    assert '"1,234.57"' in text


def test_summary_csv_follows_the_currency_filter(
    live_key, stripe_summary_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            [
                "summary",
                "--currency",
                "usd",
                "--csv",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert _summary_lines(capsys.readouterr().out.splitlines()) == [
        SUMMARY_SAMPLE_LINES[1]
    ]
    assert _summary_csv_rows(output_dir) == [
        SUMMARY_CSV_HEADER,
        ["USD", "1,234.57", "1.00", "1,233.57"],
    ]


def test_summary_csv_without_records_writes_only_the_header(
    live_key, stripe_api, export_date, tmp_path, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            ["summary", "--csv", "--output-dir", str(output_dir)]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == (
        f"exported summary rows=0 to {_summary_csv_file(output_dir)}"
    )
    assert _summary_csv_rows(output_dir) == [SUMMARY_CSV_HEADER]


def test_summary_without_the_csv_option_writes_no_file(
    live_key, stripe_summary_lists, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(["summary", "--output-dir", str(output_dir)]) == 0
    )

    # The default output is unchanged: the printed lines, no file.
    assert capsys.readouterr().out.splitlines() == [
        *SUMMARY_SAMPLE_LINES,
        SUMMARY_TOTAL_LINE,
    ]
    assert not output_dir.exists()


def test_cli_summary_csv_without_the_secret_creates_nothing(
    monkeypatch, stripe_api, tmp_path, capsys
):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            ["summary", "--csv", "--output-dir", str(output_dir)]
        )
        == 2
    )

    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err
    assert not output_dir.exists()


def test_summary_help_describes_the_csv_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "--csv" in output
    assert "--output-dir" in output


# --- summary --by-month (Issue #248) -----------------------------------


def _by_month_intent(identifier, amount, currency, created):
    return {
        "id": identifier,
        "object": "payment_intent",
        "amount": amount,
        "currency": currency,
        "status": "succeeded",
        "created": created,
    }


def _by_month_refund(identifier, amount, currency, created):
    return {
        "id": identifier,
        "object": "refund",
        "payment_intent": "pi_by_month_1",
        "amount": amount,
        "currency": currency,
        "status": "succeeded",
        "created": created,
    }


# September and October 2026 records with their own currencies and amounts, so
# a record leaking into the wrong month shows up as a wrong group value.
def _by_month_payments():
    return (
        _by_month_intent("pi_by_month_1", 1000, "usd", _utc(2026, 9, 10, 12)),
        _by_month_intent("pi_by_month_2", 500, "jpy", _utc(2026, 9, 11, 12)),
        _by_month_intent("pi_by_month_3", 1000, "eur", _utc(2026, 10, 5, 12)),
        _by_month_intent("pi_by_month_4", 123456, "usd", _utc(2026, 10, 6, 12)),
        # The last second of October still belongs to October.
        _by_month_intent("pi_by_month_5", 1, "usd", _utc(2026, 10, 31, 23, 59)),
    )


def _by_month_refunds():
    return (
        _by_month_refund("re_by_month_1", 50, "usd", _utc(2026, 9, 12, 12)),
        _by_month_refund("re_by_month_2", 200, "eur", _utc(2026, 9, 13, 12)),
        _by_month_refund("re_by_month_3", 100, "usd", _utc(2026, 10, 8, 12)),
    )
BY_MONTH_SAMPLE_LINES = [
    "2026-09 EUR 付款 0.00 退款 2.00 净额 -2.00",
    "2026-09 JPY 付款 500 退款 0 净额 500",
    "2026-09 USD 付款 10.00 退款 0.50 净额 9.50",
    "2026-10 EUR 付款 10.00 退款 0.00 净额 10.00",
    "2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57",
]
BY_MONTH_TOTAL_LINE = "合计 付款 1,754.57 退款 3.50 净额 1,751.07"


@pytest.fixture
def stripe_by_month_lists(stripe_api):
    """Payments and refunds of two months, as `summary --by-month` reads them."""
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(*_by_month_payments()),
        "/v1/refunds": _list_payload(*_by_month_refunds()),
    }


def _decimal(printed):
    """Parse a printed amount (thousands separators dropped) for comparison."""
    return Decimal(printed.replace(",", ""))


def _printed_amounts(line):
    """The three printed amounts of a summary line, as Decimals."""
    fields = line.split()
    return tuple(_decimal(value) for value in (fields[-5], fields[-3], fields[-1]))


def _by_month_groups(printed):
    """Parse the printed month lines into ``{(month, currency): amounts}``."""
    return {
        (fields[0], fields[1]): _printed_amounts(line)
        for line in printed
        if not line.startswith(stripe_payments.SUMMARY_TOTAL_LABEL)
        for fields in [line.split()]
    }


def _expected_by_month_groups():
    """The ``{(month, currency): amounts}`` the fixtures must produce."""
    totals = {}
    for position, records in enumerate(
        (_by_month_payments(), _by_month_refunds())
    ):
        for record in records:
            month = datetime.fromtimestamp(
                record["created"], tz=timezone.utc
            ).strftime("%Y-%m")
            key = (month, record["currency"].upper())
            totals.setdefault(key, [0, 0])[position] += record["amount"]
    return {
        key: tuple(
            _decimal(
                stripe_payments._format_number(amount, key[1])
            )
            for amount in (payments, refunds, payments - refunds)
        )
        for key, (payments, refunds) in totals.items()
    }


def test_cli_summary_by_month_groups_each_currency_per_month(
    live_key, stripe_by_month_lists, capsys
):
    """Acceptance: one line per month and currency, then the total line."""
    assert stripe_payments.main(["summary", "--by-month"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        *BY_MONTH_SAMPLE_LINES,
        BY_MONTH_TOTAL_LINE,
    ]


def test_summary_by_month_values_match_each_months_records(
    live_key, stripe_by_month_lists, capsys
):
    """Acceptance: every group's values are that month's own records."""
    assert stripe_payments.main(["summary", "--by-month"]) == 0
    groups = _by_month_groups(capsys.readouterr().out.splitlines())

    assert groups == _expected_by_month_groups()

    # The months add up to what plain `summary` prints per currency, so no
    # record is counted twice or dropped by the grouping.
    assert stripe_payments.main(["summary"]) == 0
    plain = {}
    for line in capsys.readouterr().out.splitlines():
        if line.startswith(stripe_payments.SUMMARY_TOTAL_LABEL):
            continue
        fields = line.split()
        plain[fields[0]] = _printed_amounts(line)
    grouped = {}
    for (month, currency), amounts in groups.items():
        running = grouped.setdefault(currency.upper(), [Decimal(0)] * 3)
        for index, amount in enumerate(amounts):
            running[index] += amount
    assert {code: tuple(amounts) for code, amounts in grouped.items()} == plain


def test_summary_by_month_total_line_adds_up_the_printed_groups(
    live_key, stripe_by_month_lists, capsys
):
    assert stripe_payments.main(["summary", "--by-month"]) == 0

    printed = capsys.readouterr().out.splitlines()
    assert printed[-1] == BY_MONTH_TOTAL_LINE
    payments, refunds, net = _printed_amounts(BY_MONTH_TOTAL_LINE)
    expected_payments = sum(
        (amounts[0] for amounts in _by_month_groups(printed[:-1]).values()),
        Decimal(0),
    )
    assert payments == expected_payments
    assert net == payments - refunds


def test_summary_by_month_totals_every_page(live_key, stripe_api, capsys):
    stripe_api.list_payloads = {"/v1/refunds": _list_payload()}
    stripe_api.list_pages = {
        "/v1/payment_intents": {
            None: _list_payload(
                _by_month_intent("pi_page_1", 1000, "usd", _utc(2026, 9, 10)),
                has_more=True,
            ),
            "pi_page_1": _list_payload(
                _by_month_intent("pi_page_2", 2000, "usd", _utc(2026, 10, 10))
            ),
        }
    }

    assert stripe_payments.main(["summary", "--by-month"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "2026-09 USD 付款 10.00 退款 0.00 净额 10.00",
        "2026-10 USD 付款 20.00 退款 0.00 净额 20.00",
        "合计 付款 30.00 退款 0.00 净额 30.00",
    ]


def test_summary_by_month_follows_the_currency_filter(
    live_key, stripe_by_month_lists, capsys
):
    assert stripe_payments.main(
        ["summary", "--by-month", "--currency", "USD"]
    ) == 0

    assert capsys.readouterr().out.splitlines() == [
        "2026-09 USD 付款 10.00 退款 0.50 净额 9.50",
        "2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        "合计 付款 1,244.57 退款 1.50 净额 1,243.07",
    ]


def test_summary_by_month_without_records_prints_nothing(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }

    assert stripe_payments.main(["summary", "--by-month"]) == 0
    assert capsys.readouterr().out == ""


def test_summary_by_month_csv_adds_the_month_column(
    live_key, stripe_by_month_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            [
                "summary",
                "--by-month",
                "--csv",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    printed = capsys.readouterr().out.splitlines()
    assert printed[-2] == BY_MONTH_TOTAL_LINE
    assert printed[-1] == (
        f"exported summary rows=5 to {_summary_csv_file(output_dir)}"
    )
    assert _summary_csv_rows(output_dir) == [
        ["月份", "币种", "付款", "退款", "净额"],
        ["2026-09", "EUR", "0.00", "2.00", "-2.00"],
        ["2026-09", "JPY", "500", "0", "500"],
        ["2026-09", "USD", "10.00", "0.50", "9.50"],
        ["2026-10", "EUR", "10.00", "0.00", "10.00"],
        ["2026-10", "USD", "1,234.57", "1.00", "1,233.57"],
    ]


def test_summary_help_describes_the_by_month_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--help"])

    assert excinfo.value.code == 0
    assert "--by-month" in capsys.readouterr().out


def test_module_summary_by_month_fails_without_the_secret():
    """The real user entry point: ``python -m stripe_payments summary --by-month``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [sys.executable, "-m", "stripe_payments", "summary", "--by-month"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# Issue #260: `summary --quiet` prints only the net total per currency.
QUIET_SAMPLE_LINES = [
    "EUR 10.00",
    "USD 1,233.57",
]


def _quiet_line(currency, net):
    """The net-only line the README documents, e.g. ``USD 1,233.57``."""
    return f"{currency} {stripe_payments._format_number(net, currency)}"


def test_cli_summary_quiet_prints_only_the_net_total_per_currency(
    live_key, stripe_summary_lists, capsys
):
    """Acceptance: one line per currency, only the net total, exit code 0."""
    exit_code = stripe_payments.main(["summary", "--quiet"])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        _quiet_line("EUR", 1000 - 0),
        _quiet_line("USD", 123457 - 100),
    ]
    # Quiet changes the printout only: the same two Stripe lists are read.
    assert [
        request["path"] for request in stripe_summary_lists.requests
    ] == ["/v1/payment_intents", "/v1/refunds"]


def test_summary_quiet_net_values_equal_the_plain_summary_nets(
    live_key, stripe_summary_lists, capsys
):
    """Acceptance: quiet reports the same net the full summary already prints."""
    assert stripe_payments.main(["summary"]) == 0
    plain = {}
    for line in capsys.readouterr().out.splitlines():
        if line.startswith(stripe_payments.SUMMARY_TOTAL_LABEL):
            continue
        fields = line.split()
        plain[fields[0]] = fields[-1]

    assert stripe_payments.main(["summary", "--quiet"]) == 0
    quiet = {
        fields[0]: fields[1]
        for fields in (
            line.split()
            for line in capsys.readouterr().out.splitlines()
        )
    }

    assert quiet == plain


def test_summary_quiet_follows_the_currency_filter(
    live_key, stripe_summary_lists, capsys
):
    assert (
        stripe_payments.main(["summary", "--quiet", "--currency", "usd"])
        == 0
    )

    assert capsys.readouterr().out.splitlines() == [_quiet_line("USD", 123357)]


def test_summary_quiet_by_month_keeps_the_month_prefix(
    live_key, stripe_by_month_lists, capsys
):
    assert stripe_payments.main(["summary", "--quiet", "--by-month"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "2026-09 EUR -2.00",
        "2026-09 JPY 500",
        "2026-09 USD 9.50",
        "2026-10 EUR 10.00",
        "2026-10 USD 1,233.57",
    ]


def test_summary_quiet_without_records_prints_nothing(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }

    assert stripe_payments.main(["summary", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


def test_summary_quiet_with_csv_prints_no_file_notice_and_writes_the_rows(
    live_key, stripe_summary_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            [
                "summary",
                "--quiet",
                "--csv",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    # Quiet prints only the net totals, but --csv still writes the same file.
    assert capsys.readouterr().out.splitlines() == QUIET_SAMPLE_LINES
    assert _summary_csv_rows(output_dir) == [
        SUMMARY_CSV_HEADER,
        ["EUR", "10.00", "0.00", "10.00"],
        ["USD", "1,234.57", "1.00", "1,233.57"],
    ]


def test_summary_help_describes_the_quiet_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--help"])

    assert excinfo.value.code == 0
    assert "--quiet" in capsys.readouterr().out


def test_module_summary_quiet_fails_without_the_secret():
    """The real user entry point: ``python -m stripe_payments summary --quiet``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [sys.executable, "-m", "stripe_payments", "summary", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# Issue #262: `summary --top N` prints only the N largest net currencies.
# The sample data the README's `--top` block describes: usd 1,233.57,
# eur 500.00, jpy 500 (500.00 in hundredths, the unit the total line uses) and
# gbp -2.00, deliberately unsorted on the wire.
TOP_SAMPLE_LINES = [
    "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
    "EUR 付款 500.00 退款 0.00 净额 500.00",
]
# The `合计` line of the two rows above: 1,234.57 + 500.00, 1.00 + 0.00.
TOP_SAMPLE_TOTAL_LINE = "合计 付款 1,734.57 退款 1.00 净额 1,733.57"
# `--top` larger than the currency count prints every currency, largest net
# first, so the zero-decimal JPY (printed 500) sorts with those values.
TOP_ALL_LINES = [
    "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
    "EUR 付款 500.00 退款 0.00 净额 500.00",
    "JPY 付款 500 退款 0 净额 500",
    "GBP 付款 0.00 退款 2.00 净额 -2.00",
]


@pytest.fixture
def stripe_top_lists(stripe_api):
    """Four currencies whose net totals differ, read by the summary command."""
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            _intent("pi_1", 123456, "usd"),
            _intent("pi_2", 1, "usd"),
            _intent("pi_3", 50000, "eur"),
            _intent("pi_4", 500, "jpy"),
        ),
        "/v1/refunds": _list_payload(
            _refund_record("re_1", 100, "usd"),
            _refund_record("re_2", 200, "gbp"),
        ),
    }
    return stripe_api


def test_cli_summary_top_prints_only_the_largest_net_currencies(
    live_key, stripe_top_lists, capsys
):
    """Acceptance: at most N currency lines, largest net total first, exit 0."""
    exit_code = stripe_payments.main(["summary", "--top", "2"])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        *TOP_SAMPLE_LINES,
        TOP_SAMPLE_TOTAL_LINE,
    ]
    # --top changes the printout only: the same two Stripe lists are read.
    assert [
        request["path"] for request in stripe_top_lists.requests
    ] == ["/v1/payment_intents", "/v1/refunds"]


def test_summary_without_top_prints_every_currency_as_before(
    live_key, stripe_top_lists, capsys
):
    """Acceptance: without --top the summary output is unchanged."""
    assert stripe_payments.main(["summary"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "EUR 付款 500.00 退款 0.00 净额 500.00",
        "GBP 付款 0.00 退款 2.00 净额 -2.00",
        "JPY 付款 500 退款 0 净额 500",
        "USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        "合计 付款 2,234.57 退款 3.00 净额 2,231.57",
    ]


def test_summary_top_larger_than_the_currency_count_prints_every_currency(
    live_key, stripe_top_lists, capsys
):
    assert stripe_payments.main(["summary", "--top", "10"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        *TOP_ALL_LINES,
        "合计 付款 2,234.57 退款 3.00 净额 2,231.57",
    ]


def test_summary_top_breaks_equal_net_totals_by_currency(
    live_key, stripe_top_lists, capsys
):
    """eur 500.00 and jpy 500 have the same printed net: eur prints first."""
    assert stripe_payments.main(["summary", "--top", "3"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        *TOP_ALL_LINES[:3],
        "合计 付款 2,234.57 退款 1.00 净额 2,233.57",
    ]


def test_summary_top_without_records_prints_nothing(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }

    assert stripe_payments.main(["summary", "--top", "2"]) == 0
    assert capsys.readouterr().out == ""


def test_summary_top_composes_with_quiet(live_key, stripe_top_lists, capsys):
    assert stripe_payments.main(["summary", "--top", "2", "--quiet"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        _quiet_line("USD", 123457 - 100),
        _quiet_line("EUR", 50000),
    ]


def test_summary_top_follows_the_currency_filter(
    live_key, stripe_top_lists, capsys
):
    assert (
        stripe_payments.main(["summary", "--top", "2", "--currency", "usd"])
        == 0
    )

    assert capsys.readouterr().out.splitlines() == [
        TOP_SAMPLE_LINES[0],
        "合计 付款 1,234.57 退款 1.00 净额 1,233.57",
    ]


def test_summary_top_by_month_keeps_the_largest_month_currency_groups(
    live_key, stripe_by_month_lists, capsys
):
    assert stripe_payments.main(["summary", "--top", "2", "--by-month"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57",
        "2026-09 JPY 付款 500 退款 0 净额 500",
        TOP_SAMPLE_TOTAL_LINE,
    ]


def test_summary_top_csv_writes_only_the_selected_rows(
    live_key, stripe_top_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"

    assert (
        stripe_payments.main(
            [
                "summary",
                "--top",
                "1",
                "--csv",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    printed = capsys.readouterr().out.splitlines()
    assert printed[:2] == [
        TOP_SAMPLE_LINES[0],
        "合计 付款 1,234.57 退款 1.00 净额 1,233.57",
    ]
    assert printed[2].startswith("exported summary rows=1 to ")
    assert _summary_csv_rows(output_dir) == [
        SUMMARY_CSV_HEADER,
        ["USD", "1,234.57", "1.00", "1,233.57"],
    ]


@pytest.mark.parametrize("count", ["0", "-1"])
def test_summary_top_rejects_a_non_positive_count(
    count, live_key, stripe_top_lists, capsys
):
    assert stripe_payments.main(["summary", "--top", count]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"--top must be positive, got {count}" in captured.err
    # The argument is checked before any Stripe call.
    assert stripe_top_lists.requests == []


def test_summary_top_requires_an_integer(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--top", "two"])

    assert excinfo.value.code == 2
    assert "--top" in capsys.readouterr().err


def test_summary_help_describes_the_top_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["summary", "--help"])

    assert excinfo.value.code == 0
    assert "--top" in capsys.readouterr().out


def test_module_summary_top_fails_without_the_secret():
    """The real user entry point: ``python -m stripe_payments summary --top 2``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [sys.executable, "-m", "stripe_payments", "summary", "--top", "2"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# --- refunds-summary (Issue #224) ---------------------------------------


def _utc(*parts):
    """Stripe's UTC epoch seconds for a wall-clock UTC date/time."""
    return int(datetime(*parts, tzinfo=timezone.utc).timestamp())


def _refund_on(identifier, amount, currency, created):
    return {
        "id": identifier,
        "object": "refund",
        "payment_intent": "pi_1",
        "amount": amount,
        "currency": currency,
        "status": "succeeded",
        "created": created,
    }


@pytest.fixture
def stripe_refund_weeks(stripe_api):
    """Refunds across two ISO weeks and two currencies, as the command reads them."""
    stripe_api.list_payloads = {
        "/v1/refunds": _list_payload(
            # 2026-10-28 and 2026-10-30 are in the same ISO week (2026-W44).
            _refund_on("re_1", 100, "usd", _utc(2026, 10, 28)),
            _refund_on("re_2", 250, "usd", _utc(2026, 10, 30)),
            _refund_on("re_3", 500, "eur", _utc(2026, 10, 28)),
            # 2026-09-28 is the Monday of ISO week 40.
            _refund_on("re_4", 900, "usd", _utc(2026, 9, 28)),
        )
    }
    return stripe_api


def test_cli_refunds_summary_prints_one_line_per_week_and_currency(
    live_key, stripe_refund_weeks, capsys
):
    exit_code = stripe_payments.main(["refunds-summary"])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        # Sorted by ISO week, then currency.  One row per week: the two usd
        # refunds of 2026-W44 (1.00 + 2.50) add up to 3.50.
        "2026-W40 usd 退款 1 笔 9.00",
        "2026-W44 eur 退款 1 笔 5.00",
        "2026-W44 usd 退款 2 笔 3.50",
    ]


REFUND_WEEK_LINE_RE = re.compile(
    r"^(?P<week>\d{4}-W\d{2}) (?P<currency>[a-z]{3}) 退款 "
    r"(?P<count>\d+) 笔 (?P<amount>[\d,]+\.\d{2})$"
)


def _parse_refund_week_line(line):
    """Return ``(week, currency, count, amount)`` from one printed line."""
    match = REFUND_WEEK_LINE_RE.match(line)
    assert match, f"unexpected refunds-summary line: {line!r}"
    return (
        match["week"],
        match["currency"],
        int(match["count"]),
        float(match["amount"].replace(",", "")),
    )


def test_refunds_summary_week_rows_add_up_to_every_refund(
    live_key, stripe_api, capsys
):
    """The Issue #249 acceptance: the week rows cover every refund record."""
    stripe_api.list_payloads = {
        "/v1/refunds": _list_payload(
            _refund_on("re_1", 100, "usd", _utc(2026, 10, 3)),
            _refund_on("re_2", 250, "usd", _utc(2026, 10, 28)),
            _refund_on("re_3", 500, "eur", _utc(2026, 10, 29)),
            _refund_on("re_4", 900, "usd", _utc(2026, 11, 2)),
            _refund_on("re_5", 125, "usd", _utc(2026, 11, 2)),
        )
    }

    assert stripe_payments.main(["refunds-summary"]) == 0
    parsed = [
        _parse_refund_week_line(line)
        for line in capsys.readouterr().out.splitlines()
    ]

    # Four week/currency rows: 2026-W40 usd, 2026-W44 eur, 2026-W44 usd and
    # 2026-W45 usd.  Every row is exactly one week, and no refund is dropped.
    assert [week for week, _, _, _ in parsed] == [
        "2026-W40",
        "2026-W44",
        "2026-W44",
        "2026-W45",
    ]
    assert sum(count for _, _, count, _ in parsed) == 5
    totals = {}
    for _, currency, _, amount in parsed:
        totals[currency] = round(totals.get(currency, 0.0) + amount, 2)
    assert totals == {"usd": 13.75, "eur": 5.00}


def test_refunds_summary_reads_the_refunds_list_only(
    live_key, stripe_refund_weeks
):
    stripe_payments.main(["refunds-summary"])

    assert [
        (request["path"], request["form"].get("limit"))
        for request in stripe_refund_weeks.requests
    ] == [("/v1/refunds", ["10"])]
    assert all(
        request["authorization"] == "Bearer sk_live_test_key"
        for request in stripe_refund_weeks.requests
    )


def test_refunds_summary_totals_every_page(live_key, stripe_api, capsys):
    stripe_api.list_pages = {
        "/v1/refunds": {
            None: _list_payload(
                _refund_on("re_1", 100, "usd", _utc(2026, 10, 3)),
                has_more=True,
            ),
            "re_1": _list_payload(
                _refund_on("re_2", 250, "usd", _utc(2026, 10, 4))
            ),
        }
    }

    assert stripe_payments.main(["refunds-summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "2026-W40 usd 退款 2 笔 3.50",
    ]


def test_refunds_summary_uses_the_utc_iso_week_and_documented_amounts(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/refunds": _list_payload(
            # 2026-11-01T23:30:00Z is Sunday, still ISO week 44 in UTC.
            _refund_on("re_1", 500, "jpy", _utc(2026, 11, 1, 23, 30)),
            # The next UTC day is Monday, the first day of ISO week 45.
            _refund_on("re_2", 100, "usd", _utc(2026, 11, 2, 0, 30)),
        )
    }

    assert stripe_payments.main(["refunds-summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        # 500 JPY is 500 (zero-decimal), not 5.00.
        "2026-W44 jpy 退款 1 笔 500",
        "2026-W45 usd 退款 1 笔 1.00",
    ]


def test_refunds_summary_uses_the_iso_week_year_across_a_year_boundary(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {
        "/v1/refunds": _list_payload(
            # 2027-01-01 is a Friday of ISO week 53 of ISO year 2026, so the
            # labels come from the ISO week year, not the calendar year.
            _refund_on("re_1", 100, "usd", _utc(2027, 1, 1)),
            _refund_on("re_2", 250, "usd", _utc(2026, 12, 31)),
            # 2027-01-04 is the Monday that starts ISO week 1 of 2027.
            _refund_on("re_3", 500, "usd", _utc(2027, 1, 4)),
        )
    }

    assert stripe_payments.main(["refunds-summary"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "2026-W53 usd 退款 2 笔 3.50",
        "2027-W01 usd 退款 1 笔 5.00",
    ]


def test_refunds_summary_prints_nothing_when_the_account_has_no_refunds(
    live_key, stripe_api, capsys
):
    stripe_api.list_payloads = {"/v1/refunds": _list_payload()}

    assert stripe_payments.main(["refunds-summary"]) == 0
    assert capsys.readouterr().out == ""
    assert [request["path"] for request in stripe_api.requests] == [
        "/v1/refunds"
    ]


def test_cli_refunds_summary_without_the_secret_names_the_variable(
    monkeypatch, stripe_api, capsys
):
    monkeypatch.delenv(stripe_payments.LIVE_SECRET_KEY_ENV, raising=False)

    assert stripe_payments.main(["refunds-summary"]) == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in capsys.readouterr().err
    assert stripe_api.requests == []


def test_refunds_summary_help_describes_the_command(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["refunds-summary", "--help"])

    assert excinfo.value.code == 0
    assert "refunds-summary" in capsys.readouterr().out


def test_module_refunds_summary_fails_without_the_secret():
    """The real user entry point: ``python -m stripe_payments refunds-summary``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    result = subprocess.run(
        [sys.executable, "-m", "stripe_payments", "refunds-summary"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr


# --- export --customer (Issue #223) -------------------------------------


@pytest.fixture
def stripe_customer_lists(stripe_api):
    """The lists a `--customer cus_1` export reads.

    Stripe filters PaymentIntents server-side by the documented `customer`
    list parameter, so that list only holds cus_1's payment.  The Refunds
    list has no `customer` parameter (only `charge` / `payment_intent`, see
    `stripe.params.RefundListParams`), so it returns every account refund and
    the command keeps the ones whose payment_intent belongs to cus_1.
    """
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            {
                "id": "pi_1",
                "object": "payment_intent",
                "customer": "cus_1",
                "amount": 2500,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000000,
            }
        ),
        "/v1/refunds": _list_payload(
            {
                "id": "re_1",
                "object": "refund",
                "payment_intent": "pi_1",
                "amount": 500,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000100,
            },
            {
                # Another customer's refund, reached through a payment that
                # is not in the filtered payment list.
                "id": "re_2",
                "object": "refund",
                "payment_intent": "pi_9",
                "amount": 900,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000200,
            },
        ),
        "/v1/customers": _list_payload(_customer(1)),
    }
    return stripe_api


def _csv_rows(output_dir, name):
    return list(
        csv.reader(
            _export_file(output_dir, name, "csv").open(
                newline="", encoding="utf-8"
            )
        )
    )


def test_cli_export_customer_exports_only_that_customers_payments_and_refunds(
    live_key, stripe_customer_lists, export_date, tmp_path, capsys
):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        ["export", "--output-dir", str(output_dir), "--customer", "cus_1"]
    )

    assert exit_code == 0
    assert (
        f"exported payments=1 refunds=1 customers=1 to {output_dir}/"
        in capsys.readouterr().out
    )

    requests = stripe_customer_lists.requests
    assert [request["path"] for request in requests] == [
        "/v1/payment_intents",
        "/v1/refunds",
        "/v1/customers",
    ]
    # The documented contract: the PaymentIntents list takes `customer`, the
    # Refunds list does not, so the refunds are narrowed by the payments of
    # the exported customer instead of an unsupported request parameter.
    assert requests[0]["form"]["customer"] == ["cus_1"]
    assert "customer" not in requests[1]["form"]
    assert requests[1]["form"]["limit"] == ["10"]

    assert _csv_rows(output_dir, "payments") == [
        ["编号", "客户", "金额", "币种", "状态", "创建时间", "客户邮箱"],
        [
            "pi_1",
            "cus_1",
            "2500",
            "usd",
            "succeeded",
            "2023-11-14T22:13:20Z",
            "buyer1@example.com",
        ],
    ]
    # Acceptance: every payments.csv row carries the requested customer id, and
    # the value is the payment record's own customer (see the provenance test
    # below), so the assertion holds for the data and not for the argument.
    assert {row[1] for row in _csv_rows(output_dir, "payments")[1:]} == {"cus_1"}

    assert _csv_rows(output_dir, "refunds") == [
        ["编号", "付款编号", "金额", "币种", "状态", "创建时间"],
        ["re_1", "pi_1", "500", "usd", "succeeded", "2023-11-14T22:15:00Z"],
    ]

    assert json.loads(
        _export_file(output_dir, "payments", "json").read_text(encoding="utf-8")
    ) == [
        {
            "id": "pi_1",
            "customer": "cus_1",
            "amount": 2500,
            "currency": "usd",
            "status": "succeeded",
            "created": "2023-11-14T22:13:20Z",
            "customer_email": "buyer1@example.com",
        }
    ]


def test_export_without_customer_sends_no_customer_parameter_and_keeps_the_columns(
    live_key, stripe_lists, export_date, tmp_path
):
    """Not passing --customer adds no 客户 column (Issue #239 kept the email)."""
    output_dir = tmp_path / "export"
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    for request in stripe_lists.requests:
        assert "customer" not in request["form"]

    assert _csv_rows(output_dir, "payments")[0] == [
        "编号",
        "金额",
        "币种",
        "状态",
        "创建时间",
        "客户邮箱",
    ]
    assert "customer" not in json.loads(
        _export_file(output_dir, "payments", "json").read_text(encoding="utf-8")
    )[0]


def test_export_customer_column_comes_from_the_payment_record(
    live_key, stripe_customer_lists, export_date, tmp_path
):
    """The column reports the row's own customer, never the CLI argument.

    If a record ever came back belonging to another customer (a filter
    regression on Stripe's side, or a page fetched without the filter), the
    export must show that customer instead of stamping the requested id on
    every row.
    """
    stripe_customer_lists.list_payloads["/v1/payment_intents"] = _list_payload(
        {
            "id": "pi_1",
            "object": "payment_intent",
            "customer": "cus_1",
            "amount": 2500,
            "currency": "usd",
            "status": "succeeded",
            "created": 1700000000,
        },
        {
            "id": "pi_2",
            "object": "payment_intent",
            "customer": "cus_9",
            "amount": 700,
            "currency": "usd",
            "status": "succeeded",
            "created": 1700000300,
        },
    )
    output_dir = tmp_path / "export"
    assert (
        stripe_payments.main(
            ["export", "--output-dir", str(output_dir), "--customer", "cus_1"]
        )
        == 0
    )

    assert {(row[0], row[1]) for row in _csv_rows(output_dir, "payments")[1:]} == {
        ("pi_1", "cus_1"),
        ("pi_2", "cus_9"),
    }
    # The email is looked up from each row's own customer id, so a record of a
    # customer outside the exported customer list stays blank instead of
    # inheriting another customer's email.
    assert {row[0]: row[6] for row in _csv_rows(output_dir, "payments")[1:]} == {
        "pi_1": "buyer1@example.com",
        "pi_2": "",
    }


def test_export_payments_csv_carries_the_customer_email(
    live_key, stripe_api, export_date, tmp_path
):
    """Issue #239: 对账时 payments CSV 直接显示付款客户的邮箱。

    The email comes from the Customers list the export already reads, looked
    up by each payment's own ``customer`` id.  A guest payment (no customer),
    a customer without an email and a customer id outside the exported list
    all stay blank so the operator sees a missing value instead of a stale or
    borrowed address.
    """
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(
            {
                "id": "pi_1",
                "object": "payment_intent",
                "customer": "cus_1",
                "amount": 100,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000000,
            },
            {
                "id": "pi_2",
                "object": "payment_intent",
                "amount": 200,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000001,
            },
            {
                "id": "pi_3",
                "object": "payment_intent",
                "customer": "cus_2",
                "amount": 300,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000002,
            },
            {
                "id": "pi_4",
                "object": "payment_intent",
                "customer": "cus_missing",
                "amount": 400,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000003,
            },
        ),
        "/v1/refunds": _list_payload(),
        "/v1/customers": _list_payload(
            _customer(1),
            {
                "id": "cus_2",
                "object": "customer",
                "created": 1700000300,
            },
        ),
    }
    output_dir = tmp_path / "export"
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    rows = _csv_rows(output_dir, "payments")
    assert rows[0] == ["编号", "金额", "币种", "状态", "创建时间", "客户邮箱"]
    assert {row[0]: row[5] for row in rows[1:]} == {
        "pi_1": "buyer1@example.com",
        "pi_2": "",
        "pi_3": "",
        "pi_4": "",
    }


def test_export_customer_without_payments_writes_no_payment_and_no_refund(
    live_key, stripe_api, export_date, tmp_path, capsys
):
    stripe_api.list_payloads = {
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(_refund_record("re_1", 100, "usd")),
        "/v1/customers": _list_payload(_customer(1)),
    }
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        ["export", "--output-dir", str(output_dir), "--customer", "cus_1"]
    )

    assert exit_code == 0
    assert "exported payments=0 refunds=0 customers=1" in capsys.readouterr().out
    assert _csv_data_rows(output_dir, "payments") == []
    assert _csv_data_rows(output_dir, "refunds") == []


def test_cli_export_rejects_an_empty_customer(live_key, stripe_api, tmp_path, capsys):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        ["export", "--output-dir", str(output_dir), "--customer", ""]
    )

    assert exit_code == 2
    assert "--customer must not be empty" in capsys.readouterr().err
    assert stripe_api.requests == []
    assert not output_dir.exists()


def test_export_help_lists_the_customer_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["export", "--help"])

    assert excinfo.value.code == 0
    assert "--customer" in capsys.readouterr().out


def test_module_export_accepts_the_customer_option(tmp_path):
    """The real user entry point: ``python -m stripe_payments export --customer``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    output_dir = tmp_path / "export"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stripe_payments",
            "export",
            "--customer",
            "cus_1",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr
    assert not output_dir.exists()


# --- export --email (Issue #247) ----------------------------------------


@pytest.fixture
def stripe_email_lists(stripe_api):
    """The lists an `export --email buyer1@example.com` export reads.

    ``stripe.params.CustomerListParams`` documents an ``email`` filter ("A
    case-sensitive filter on the list based on the customer's `email` field"),
    so the Customers list returns only that address's customer.  The
    PaymentIntents list has no ``email`` filter, only ``customer``
    (``stripe.params.PaymentIntentListParams``), so the payments are read with
    the id the email resolved to.  The Refunds list has neither filter
    (``stripe.params.RefundListParams``: ``charge`` / ``payment_intent``), so
    it returns every account refund and the command keeps the ones whose
    ``payment_intent`` belongs to those payments.
    """
    stripe_api.list_payloads = {
        "/v1/customers": _list_payload(_customer(1)),
        "/v1/payment_intents": _list_payload(
            {
                "id": "pi_1",
                "object": "payment_intent",
                "customer": "cus_1",
                "amount": 2500,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000000,
            }
        ),
        "/v1/refunds": _list_payload(
            {
                "id": "re_1",
                "object": "refund",
                "payment_intent": "pi_1",
                "amount": 500,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000100,
            },
            {
                # Another customer's refund, reached through a payment that is
                # not in the filtered payment list.
                "id": "re_2",
                "object": "refund",
                "payment_intent": "pi_9",
                "amount": 900,
                "currency": "usd",
                "status": "succeeded",
                "created": 1700000200,
            },
        ),
    }
    return stripe_api


def test_cli_export_email_exports_only_that_customers_records(
    live_key, stripe_email_lists, export_date, tmp_path, capsys
):
    """Acceptance: `export --email` keeps only that address's records."""
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        [
            "export",
            "--output-dir",
            str(output_dir),
            "--email",
            "buyer1@example.com",
        ]
    )

    assert exit_code == 0
    assert (
        f"exported payments=1 refunds=1 customers=1 to {output_dir}/"
        in capsys.readouterr().out
    )

    requests = stripe_email_lists.requests
    assert [request["path"] for request in requests] == [
        "/v1/customers",
        "/v1/payment_intents",
        "/v1/refunds",
    ]
    # The documented contract: the Customers list filters by `email`, the
    # PaymentIntents list by `customer`, the Refunds list by neither.
    assert requests[0]["form"]["email"] == ["buyer1@example.com"]
    assert requests[0]["form"]["limit"] == ["10"]
    assert requests[1]["form"]["customer"] == ["cus_1"]
    assert "email" not in requests[1]["form"]
    assert "customer" not in requests[2]["form"]
    assert "email" not in requests[2]["form"]

    # The payments keep the usual columns (no 客户 column for --email) and
    # every row belongs to the requested address.
    assert _csv_rows(output_dir, "payments") == [
        ["编号", "金额", "币种", "状态", "创建时间", "客户邮箱"],
        [
            "pi_1",
            "2500",
            "usd",
            "succeeded",
            "2023-11-14T22:13:20Z",
            "buyer1@example.com",
        ],
    ]
    assert {row[5] for row in _csv_rows(output_dir, "payments")[1:]} == {
        "buyer1@example.com"
    }

    # Only the refunds of that customer's payments, and only that customer.
    assert _csv_rows(output_dir, "refunds")[1:] == [
        ["re_1", "pi_1", "500", "usd", "succeeded", "2023-11-14T22:15:00Z"]
    ]
    assert _csv_rows(output_dir, "customers")[1:] == [
        ["cus_1", "buyer1@example.com", "2023-11-14T22:16:41Z"]
    ]

    assert json.loads(
        _export_file(output_dir, "payments", "json").read_text(encoding="utf-8")
    ) == [
        {
            "id": "pi_1",
            "amount": 2500,
            "currency": "usd",
            "status": "succeeded",
            "created": "2023-11-14T22:13:20Z",
            "customer_email": "buyer1@example.com",
        }
    ]


def test_export_email_narrows_to_every_customer_with_that_address(
    live_key, monkeypatch, export_date, tmp_path
):
    """A shared address exports every matching customer (Stripe emails are not unique).

    The Customers ``email`` filter can return more than one customer while the
    PaymentIntents list only takes a single ``customer``, so the export reads
    each matched customer's payments and narrows the refunds to that union.
    The lists are faked here because the wire contract of the single-customer
    case is asserted against the real SDK above.
    """
    customer_1 = SimpleNamespace(
        id="cus_1", email="buyer@example.com", created=1700000000
    )
    customer_2 = SimpleNamespace(
        id="cus_2", email="buyer@example.com", created=1700000001
    )
    payments = {
        "cus_1": SimpleNamespace(
            id="pi_1",
            customer="cus_1",
            amount=100,
            currency="usd",
            status="succeeded",
            created=1700000100,
        ),
        "cus_2": SimpleNamespace(
            id="pi_2",
            customer="cus_2",
            amount=200,
            currency="usd",
            status="succeeded",
            created=1700000101,
        ),
    }
    refunds = [
        SimpleNamespace(
            id=identifier,
            payment_intent=payment_intent,
            amount=amount,
            currency="usd",
            status="succeeded",
            created=1700000200,
        )
        for identifier, payment_intent, amount in (
            ("re_1", "pi_1", 10),
            ("re_2", "pi_2", 20),
            ("re_9", "pi_9", 90),
        )
    ]
    calls = []

    def fake_list_all(resource, *, limit, params=None):
        calls.append((resource, dict(params or {})))
        if resource is stripe.Customer:
            return iter([customer_1, customer_2])
        if resource is stripe.PaymentIntent:
            return iter([payments[params["customer"]]])
        return iter(refunds)

    monkeypatch.setattr(stripe_payments, "_list_all", fake_list_all)

    output_dir = tmp_path / "export"
    counts = stripe_payments.export_data(
        output_dir=str(output_dir),
        formats=("csv",),
        limit=10,
        email="buyer@example.com",
    )

    assert counts == (2, 2, 2)
    assert calls == [
        (stripe.Customer, {"email": "buyer@example.com"}),
        (stripe.PaymentIntent, {"customer": "cus_1"}),
        (stripe.PaymentIntent, {"customer": "cus_2"}),
        (stripe.Refund, {}),
    ]
    assert [row[0] for row in _csv_rows(output_dir, "payments")[1:]] == [
        "pi_1",
        "pi_2",
    ]
    assert [row[0] for row in _csv_rows(output_dir, "refunds")[1:]] == [
        "re_1",
        "re_2",
    ]
    assert [row[0] for row in _csv_rows(output_dir, "customers")[1:]] == [
        "cus_1",
        "cus_2",
    ]


def test_export_without_email_sends_no_email_filter(
    live_key, stripe_lists, export_date, tmp_path
):
    """Not passing --email keeps the whole-account export as before."""
    output_dir = tmp_path / "export"
    assert stripe_payments.main(["export", "--output-dir", str(output_dir)]) == 0

    for request in stripe_lists.requests:
        assert "email" not in request["form"]
    assert len(_csv_data_rows(output_dir, "customers")) == 2


def test_cli_export_email_unknown_address_fails_before_writing_files(
    live_key, stripe_api, tmp_path, capsys
):
    """A typo must be reported, not silently exported as an empty account.

    Stripe's ``email`` filter is an exact, case-sensitive match, so an address
    that matches no customer returns an empty list instead of an error.
    """
    stripe_api.list_payloads = {"/v1/customers": _list_payload()}
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        [
            "export",
            "--output-dir",
            str(output_dir),
            "--email",
            "nobody@example.com",
        ]
    )

    assert exit_code == 2
    assert (
        "no Stripe customer has the email 'nobody@example.com'"
        in capsys.readouterr().err
    )
    # Only the customer lookup ran; no payment/refund request and no file.
    assert [request["path"] for request in stripe_api.requests] == [
        "/v1/customers"
    ]
    assert stripe_api.requests[0]["form"]["email"] == ["nobody@example.com"]
    assert not output_dir.exists()


def test_cli_export_email_with_only_the_filtered_customer_file(
    live_key, stripe_api, export_date, tmp_path
):
    """The customers file follows the email filter instead of the whole account."""
    stripe_api.list_payloads = {
        "/v1/customers": _list_payload(_customer(2)),
        "/v1/payment_intents": _list_payload(),
        "/v1/refunds": _list_payload(),
    }
    output_dir = tmp_path / "export"
    assert (
        stripe_payments.main(
            [
                "export",
                "--output-dir",
                str(output_dir),
                "--email",
                "buyer2@example.com",
            ]
        )
        == 0
    )

    assert _csv_rows(output_dir, "customers")[1:] == [
        ["cus_2", "buyer2@example.com", "2023-11-14T22:16:42Z"]
    ]


def test_cli_export_rejects_an_empty_email(live_key, stripe_api, tmp_path, capsys):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        ["export", "--output-dir", str(output_dir), "--email", ""]
    )

    assert exit_code == 2
    assert "--email must not be empty" in capsys.readouterr().err
    assert stripe_api.requests == []
    assert not output_dir.exists()


def test_cli_export_rejects_email_and_customer_together(
    live_key, stripe_api, tmp_path, capsys
):
    output_dir = tmp_path / "export"
    exit_code = stripe_payments.main(
        [
            "export",
            "--output-dir",
            str(output_dir),
            "--email",
            "buyer1@example.com",
            "--customer",
            "cus_1",
        ]
    )

    assert exit_code == 2
    error = capsys.readouterr().err
    assert "--email" in error and "--customer" in error
    assert stripe_api.requests == []
    assert not output_dir.exists()


def test_export_help_lists_the_email_option(capsys):
    with pytest.raises(SystemExit) as excinfo:
        stripe_payments.main(["export", "--help"])

    assert excinfo.value.code == 0
    assert "--email" in capsys.readouterr().out


def test_module_export_accepts_the_email_option(tmp_path):
    """The real user entry point: ``python -m stripe_payments export --email``."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key != stripe_payments.LIVE_SECRET_KEY_ENV
    }
    output_dir = tmp_path / "export"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "stripe_payments",
            "export",
            "--email",
            "buyer@example.com",
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert result.returncode == 2
    assert stripe_payments.LIVE_SECRET_KEY_ENV in result.stderr
    assert not output_dir.exists()
