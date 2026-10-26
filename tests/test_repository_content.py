"""Content checks for this repository's artifacts.

The repository ships no application server: its deliverables are the README,
the GitHub Issue templates and a small Stripe payment helper.  The `CI`
workflow runs this suite so every delivery pull request and every commit on
`main` carries a real test result instead of an empty check-run gate (Orbi's
pre-release gate reads the check runs of the frozen base commit).
"""

import argparse
import re
import subprocess
from pathlib import Path

import stripe_payments

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "user-outcome.md"
FEATURE_REQUEST_TEMPLATE = (
    REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature-request.md"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Issue #104: the CI `live payment verification` job runs the `verify`
# subcommand; the content check below asserts every flag after that command
# is defined by the `verify` subparser of `stripe_payments._parser()`.
STRIPE_VERIFY_COMMAND = "python -m stripe_payments verify"
STRIPE_FLAG_RE = re.compile(r"--[a-z][a-z-]*")

# GitHub shows a markdown issue template by the `name`/`about` fields of
# its YAML front matter; the body sections are the ones the template
# itself promises to the author.
ISSUE_TEMPLATE_FRONT_MATTER_KEYS = ("name", "about")

# Issue #39 appends this exact line as the README's final line.
# Issue #55 appends this exact line as the new README final line.
# Issue #97 appends this exact line as the new README final line.
# Issue #120 appends this exact line as the new README final line.
README_LAST_LINE = "Beta regression: Gemini native protocol hotfix v0.7.40."
ISSUE_TEMPLATE_SECTIONS = (
    "## User outcome",
    "## Preconditions",
    "## Steps to reproduce",
    "## Acceptance",
    "## Evidence",
)

# Issue #202 documents how to run every test locally in the README.
README_TESTS_HEADING = "## Run the tests locally"
README_TESTS_COMMAND = "python3 -m unittest discover -s tests -v"

# Issue #211 appends this exact line as the final line of the acceptance log.
E2E_LOG = REPO_ROOT / "docs" / "e2e-log.md"
E2E_LOG_LAST_LINE = "2026-10-27 周报第 4 期 fix-base 演示"
# The log kept exactly these 26 lines before Issue #211 appended its line.
E2E_LOG_PREVIOUS_LAST_LINE = "v0.8.17 晋升前新用户全流程验收记录"
E2E_LOG_LINE_COUNT = 27

# Issue #207 adds a Chinese 「运行测试」 section that runs every test with the
# same command as the CI `Run tests` step.
README_RUN_TESTS_HEADING = "## 运行测试"
README_RUN_TESTS_COMMAND = "python -m pytest"
README_RUN_TESTS_DEPENDENCIES = "python -m pip install pytest stripe"

# The `功能建议` template is offered by its Chinese `name` and promises its
# author the two sections the request asked for.
FEATURE_REQUEST_NAME = "功能建议"
FEATURE_REQUEST_SECTIONS = (
    "## 想解决的问题",
    "## 期望的效果",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


def _front_matter(text: str) -> str:
    """Return the YAML front matter block of a markdown file."""
    assert text.startswith("---\n"), "the file must start with a YAML front matter"
    end = text.index("\n---", len("---\n"))
    return text[len("---\n"):end]


def _front_matter_keys(text: str) -> set:
    """Return the YAML front matter keys of a markdown file."""
    return {
        line.split(":", 1)[0].strip()
        for line in _front_matter(text).splitlines()
        if line.strip()
    }


def _verify_subparser_option_strings() -> set:
    """Return every option string the `verify` subcommand parser defines."""
    parser = stripe_payments._parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    verify = subparsers.choices["verify"]
    return {
        option
        for action in verify._actions
        for option in action.option_strings
    }


def _ci_stripe_verify_flags() -> list:
    """Return every --flag CI passes to the Stripe verify command."""
    text = _read(WORKFLOW)
    assert STRIPE_VERIFY_COMMAND in text, (
        f"the CI workflow must invoke {STRIPE_VERIFY_COMMAND!r}"
    )
    after_command = text.index(STRIPE_VERIFY_COMMAND) + len(STRIPE_VERIFY_COMMAND)
    return STRIPE_FLAG_RE.findall(text[after_command:])


def _git_check_ignore(relative_path: str) -> str:
    """Return `git check-ignore -v` output for a path, empty when not ignored."""
    result = subprocess.run(
        ["git", "check-ignore", "-v", relative_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return result.stdout.strip()


def test_gitignore_ignores_the_default_export_directory():
    """Issue #114: a live export must not be committable from the repo root."""
    directory = stripe_payments.DEFAULT_OUTPUT_DIR
    output = _git_check_ignore(f"{directory}/customers.csv")
    assert output.startswith(".gitignore:"), (
        f"the .gitignore must ignore the default export directory {directory!r}"
    )


def test_readme_is_not_empty():
    assert _read(README).strip(), "README.md is empty"


def test_readme_documents_running_the_tests_locally():
    """Issue #202: the README shows the command that runs the local tests."""
    text = _read(README)
    assert README_TESTS_HEADING in text, (
        f"the README needs a {README_TESTS_HEADING!r} section"
    )
    assert README_TESTS_COMMAND in text, (
        f"the {README_TESTS_HEADING!r} section must show {README_TESTS_COMMAND!r}"
    )


def _readme_section(heading: str) -> str:
    """Return the body of a `## ` README section, up to the next `## `."""
    text = _read(README)
    assert f"\n{heading}\n" in text, f"the README needs a {heading!r} section"
    body = text.split(f"\n{heading}\n", 1)[1]
    return body.split("\n## ", 1)[0]


def test_readme_documents_how_to_run_the_tests():
    """Issue #207: a 「运行测试」 section runs every test with pytest."""
    body = _readme_section(README_RUN_TESTS_HEADING)
    assert README_RUN_TESTS_COMMAND in body, (
        f"the {README_RUN_TESTS_HEADING!r} section must show "
        f"{README_RUN_TESTS_COMMAND!r}"
    )
    assert "tests/" in body, (
        f"the {README_RUN_TESTS_HEADING!r} section must say it runs the "
        "tests under tests/"
    )
    # The documented command is the one CI runs, so the section cannot drift
    # away from the real test entry point.
    assert README_RUN_TESTS_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must use {README_RUN_TESTS_COMMAND!r}"
    )


def test_readme_documents_the_missing_pytest_repair():
    """Issue #207: a missing pytest is reported as not a passing test run."""
    body = _readme_section(README_RUN_TESTS_HEADING)
    assert "No module named pytest" in body, (
        f"the {README_RUN_TESTS_HEADING!r} section must name the failure "
        "message of a missing pytest"
    )
    assert README_RUN_TESTS_DEPENDENCIES in body, (
        f"the {README_RUN_TESTS_HEADING!r} section must show the repair "
        f"command {README_RUN_TESTS_DEPENDENCIES!r}"
    )


def test_readme_ends_with_regression_line():
    lines = [line for line in _read(README).splitlines() if line.strip()]
    assert lines[-1] == README_LAST_LINE, (
        f"the README must end with the {README_LAST_LINE!r} line, "
        f"got {lines[-1]!r}"
    )


def test_e2e_log_ends_with_the_issue_211_line():
    lines = _read(E2E_LOG).splitlines()
    assert lines[-1] == E2E_LOG_LAST_LINE, (
        f"the e2e log must end with the {E2E_LOG_LAST_LINE!r} line, "
        f"got {lines[-1]!r}"
    )
    assert len(lines) == E2E_LOG_LINE_COUNT, (
        f"the e2e log must keep its {E2E_LOG_LINE_COUNT - 1} existing lines and "
        f"append exactly one, got {len(lines)} lines"
    )
    assert lines[-2] == E2E_LOG_PREVIOUS_LAST_LINE, (
        "the line Issue #211 appended must not disturb the history before it, "
        f"expected {E2E_LOG_PREVIOUS_LAST_LINE!r} second to last"
    )


def test_issue_template_front_matter_has_required_keys():
    keys = _front_matter_keys(_read(ISSUE_TEMPLATE))
    for key in ISSUE_TEMPLATE_FRONT_MATTER_KEYS:
        assert key in keys, f"the issue template front matter needs {key!r}"


def test_feature_request_template_front_matter_has_required_keys():
    keys = _front_matter_keys(_read(FEATURE_REQUEST_TEMPLATE))
    for key in ISSUE_TEMPLATE_FRONT_MATTER_KEYS:
        assert key in keys, f"the 功能建议 template front matter needs {key!r}"


def test_feature_request_template_has_its_chinese_display_name():
    assert f"name: {FEATURE_REQUEST_NAME}" in _read(FEATURE_REQUEST_TEMPLATE), (
        "the template must be offered as 功能建议"
    )


def test_feature_request_template_documents_every_section():
    text = _read(FEATURE_REQUEST_TEMPLATE)
    for section in FEATURE_REQUEST_SECTIONS:
        assert section in text, f"the 功能建议 template is missing {section!r}"


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


def test_ci_stripe_verify_flags_are_defined_by_the_verify_subparser():
    flags = _ci_stripe_verify_flags()
    assert flags, (
        f"the CI workflow must pass flags to {STRIPE_VERIFY_COMMAND!r}"
    )
    option_strings = _verify_subparser_option_strings()
    missing = [flag for flag in flags if flag not in option_strings]
    assert not missing, (
        f"CI passes {missing} to {STRIPE_VERIFY_COMMAND!r}, but the verify "
        f"subparser only defines {sorted(option_strings)}"
    )


def test_live_payment_verification_cannot_run_on_push_or_pull_request():
    text = _read(WORKFLOW)
    assert "github.event_name == 'workflow_dispatch'" in text, (
        "the live job must be gated to workflow_dispatch"
    )
    assert "continue-on-error" not in text, (
        "a failed live charge must fail the workflow, never pass silently"
    )
