"""Content checks for this repository's artifacts.

The repository ships no application server: its deliverables are the README,
the GitHub Issue templates and a small Stripe payment helper.  The `CI`
workflow runs this suite so every delivery pull request and every commit on
`main` carries a real test result instead of an empty check-run gate (Orbi's
pre-release gate reads the check runs of the frozen base commit).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "user-outcome.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# GitHub shows a markdown issue template by the `name`/`about` fields of
# its YAML front matter; the body sections are the ones the template
# itself promises to the author.
ISSUE_TEMPLATE_FRONT_MATTER_KEYS = ("name", "about")

# Issue #39 appends this exact line as the README's final line.
# Issue #55 appends this exact line as the new README final line.
README_LAST_LINE = "本仓库用于 Orbi Cloud 每次发版前的新用户全流程验收（v0.7.12，2026-10-07）"
ISSUE_TEMPLATE_SECTIONS = (
    "## User outcome",
    "## Preconditions",
    "## Steps to reproduce",
    "## Acceptance",
    "## Evidence",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


def _front_matter(text: str) -> str:
    """Return the YAML front matter block of a markdown file."""
    assert text.startswith("---\n"), "the file must start with a YAML front matter"
    end = text.index("\n---", len("---\n"))
    return text[len("---\n"):end]


def test_readme_is_not_empty():
    assert _read(README).strip(), "README.md is empty"


def test_readme_ends_with_regression_line():
    lines = [line for line in _read(README).splitlines() if line.strip()]
    assert lines[-1] == README_LAST_LINE, (
        f"the README must end with the {README_LAST_LINE!r} line, "
        f"got {lines[-1]!r}"
    )


def test_issue_template_front_matter_has_required_keys():
    keys = {
        line.split(":", 1)[0].strip()
        for line in _front_matter(_read(ISSUE_TEMPLATE)).splitlines()
        if line.strip()
    }
    for key in ISSUE_TEMPLATE_FRONT_MATTER_KEYS:
        assert key in keys, f"the issue template front matter needs {key!r}"


def test_issue_template_documents_every_section():
    text = _read(ISSUE_TEMPLATE)
    for section in ISSUE_TEMPLATE_SECTIONS:
        assert section in text, f"the issue template is missing {section!r}"


def test_ci_has_a_protected_manual_live_payment_verification():
    text = _read(WORKFLOW)
    assert "workflow_dispatch:" in text, "CI needs a manual trigger"
    assert "environment: stripe-live" in text, (
        "the live run must use the protected 'stripe-live' environment"
    )
    assert "STRIPE_LIVE_SECRET_KEY: ${{ secrets.STRIPE_LIVE_SECRET_KEY }}" in text, (
        "the live key must come from the environment secret"
    )
    assert "python -m stripe_payments verify" in text, (
        "the live job must run the Stripe verification command"
    )


def test_live_payment_verification_cannot_run_on_push_or_pull_request():
    text = _read(WORKFLOW)
    assert "github.event_name == 'workflow_dispatch'" in text, (
        "the live job must be gated to workflow_dispatch"
    )
    assert "continue-on-error" not in text, (
        "a failed live charge must fail the workflow, never pass silently"
    )


# Issue #71: the CI run triggered by a push to `main` or a pull request to
# `main` also performs a real live charge, using the repository secret
# `STRIPE_SECRET_KEY`. A missing or empty secret must fail that charge
# (the CLI exits 2), never skip it.
REPOSITORY_CHARGE_SECRET_MAPPING = (
    "STRIPE_LIVE_SECRET_KEY: ${{ secrets.STRIPE_SECRET_KEY }}"
)
VERIFY_COMMAND = "python -m stripe_payments verify"


def test_ci_charges_on_push_and_pull_request_with_the_repository_secret():
    text = _read(WORKFLOW)
    assert text.count(VERIFY_COMMAND) == 2, (
        "both the manual run and the push/PR run must execute "
        "`python -m stripe_payments verify`"
    )
    assert REPOSITORY_CHARGE_SECRET_MAPPING in text, (
        "the push/PR charge must take its key from the STRIPE_SECRET_KEY "
        "repository secret"
    )
    assert "vars.STRIPE_PAYMENT_METHOD" in text, (
        "the push/PR charge must read the pre-created payment method from a "
        "repository variable"
    )


def test_push_and_pull_request_charge_is_never_skipped():
    text = _read(WORKFLOW)
    assert "secrets.STRIPE_SECRET_KEY != ''" not in text, (
        "a missing repository secret must fail the charge, not skip it"
    )
    assert "continue-on-error" not in text, (
        "a failed charge must fail the workflow, never pass silently"
    )
