"""Tests for the Stripe live payment entry points.

The tests drive the *real* official `stripe` SDK against a local HTTP
recorder, so they assert Stripe's documented wire contract (request path,
``Authorization`` header and form fields), not a shape the implementation
guessed.  No network and no keys are required.
"""

import csv
import json
import os
import runpy
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

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
                status = recorder_self.list_statuses.get(
                    parsed.path, recorder_self.status
                )
                payload = recorder_self.list_payloads.get(
                    parsed.path, {"object": "list", "data": []}
                )
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


def _list_payload(*items):
    return {"object": "list", "data": list(items), "has_more": False}


@pytest.fixture
def stripe_lists(stripe_api):
    """The three GET list responses the export command reads."""
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
    live_key, stripe_lists, tmp_path, capsys
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
                (output_dir / f"{name}.csv").open(newline="", encoding="utf-8")
            )
        )
        for name in ("payments", "refunds", "customers")
    }
    assert csv_rows["payments"] == [
        ["id", "amount", "currency", "status", "created"],
        ["pi_1", "100", "usd", "succeeded", "2023-11-14T22:13:20Z"],
    ]
    assert csv_rows["refunds"] == [
        ["id", "payment_intent", "amount", "currency", "status", "created"],
        ["re_1", "pi_1", "100", "usd", "succeeded", "2023-11-14T22:15:00Z"],
    ]
    assert csv_rows["customers"] == [
        ["id", "email", "created"],
        ["cus_1", "buyer@example.com", "2023-11-14T22:16:40Z"],
        ["cus_2", "", "2023-11-14T22:18:20Z"],
    ]

    json_data = {
        name: json.loads(
            (output_dir / f"{name}.json").read_text(encoding="utf-8")
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
    live_key, stripe_lists, tmp_path
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
        "customers.csv",
        "payments.csv",
        "refunds.csv",
    ]
    assert (
        stripe_payments.main(
            ["export", "--output-dir", str(json_dir), "--format", "json"]
        )
        == 0
    )
    assert sorted(path.name for path in json_dir.iterdir()) == [
        "customers.json",
        "payments.json",
        "refunds.json",
    ]


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
    assert "--format" in out


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
