"""Tests for the Stripe live payment entry points.

The tests drive the *real* official `stripe` SDK against a local HTTP
recorder, so they assert Stripe's documented wire contract (request path,
``Authorization`` header and form fields), not a shape the implementation
guessed.  No network and no keys are required.
"""

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
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                recorder_self.record(self.path, self.headers, body)
                raw = json.dumps(recorder_self.payload).encode()
                self.send_response(recorder_self.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

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
