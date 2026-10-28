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
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# Issue #104: the CI `live payment verification` job runs the `verify`
# subcommand; the content check below asserts every flag after that command
# is defined by the `verify` subparser of `stripe_payments._parser()`.
STRIPE_VERIFY_COMMAND = "python -m stripe_payments verify"
STRIPE_EXPORT_COMMAND = "python -m stripe_payments export"
# Issue #221: the README documents the summary command and its line format.
STRIPE_SUMMARY_COMMAND = "python -m stripe_payments summary"
SUMMARY_SAMPLE_LINE = "USD 付款 1,234.57 退款 1.00 净额 1,233.57"
# Issue #243: the summary ends with one all-currency total line.
SUMMARY_TOTAL_SAMPLE_LINE = "合计 付款 1,244.57 退款 1.00 净额 1,243.57"
# Issue #224: the README documents the refunds-summary command and its line format.
STRIPE_REFUNDS_SUMMARY_COMMAND = "python -m stripe_payments refunds-summary"
REFUNDS_SUMMARY_SAMPLE_LINE = "2026-W44 usd 退款 2 笔 3.50"
# Issue #225: the refunds-summary usage sits next to the export and summary
# sections and shows the complete output the command prints.
README_EXPORT_HEADING = "### 导出付款数据（export）"
README_SUMMARY_HEADING = "### 汇总收入（summary）"
README_REFUNDS_SUMMARY_HEADING = "### 按周汇总退款（refunds-summary）"
# Issue #254: the top-level `--version` flag and the line it prints.
STRIPE_VERSION_COMMAND = "python -m stripe_payments --version"
README_VERSION_HEADING = "### 查看版本（--version）"
# The sample data the README section describes: ISO 第 40 周一笔 usd 0.50，第 44 周
# 一笔 eur 1.00 加两笔 usd 1.00、2.50。The expected lines are rendered through the
# real `_refund_week_line()` below, so the docs cannot drift from the output.
REFUNDS_SUMMARY_SAMPLE_DATA = (
    ("2026-W40", "usd", 1, 50),
    ("2026-W44", "eur", 1, 100),
    ("2026-W44", "usd", 2, 350),
)
# Issue #218: the export command takes exactly these `--format` choices.
EXPORT_FORMATS = ("csv", "json", "both")
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


def _subparser_option_strings(command: str) -> set:
    """Return every option string a `stripe_payments` subcommand defines."""
    parser = stripe_payments._parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    subparser = subparsers.choices[command]
    return {
        option
        for action in subparser._actions
        for option in action.option_strings
    }


def _verify_subparser_option_strings() -> set:
    """Return every option string the `verify` subcommand parser defines."""
    return _subparser_option_strings("verify")


def _readme_export_command_lines() -> list:
    """Return the README lines that run the export command."""
    return [
        line
        for line in _read(README).splitlines()
        if STRIPE_EXPORT_COMMAND in line
    ]


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


def test_readme_documents_the_export_format_choices():
    """Issue #218: the README shows how to export only CSV, only JSON or both."""
    lines = _readme_export_command_lines()
    assert lines, f"the README must document {STRIPE_EXPORT_COMMAND!r}"
    # Every flag the README passes to the export command must be a real flag of
    # the export subparser, so the documented command cannot drift.
    flags = {flag for line in lines for flag in STRIPE_FLAG_RE.findall(line)}
    missing_flags = flags - _subparser_option_strings("export")
    assert not missing_flags, (
        f"the README passes {sorted(missing_flags)} to "
        f"{STRIPE_EXPORT_COMMAND!r}, but the export subparser does not define "
        "them"
    )
    assert "--format" in flags, (
        f"the README must show {STRIPE_EXPORT_COMMAND!r} with --format"
    )
    text = "\n".join(lines)
    for format_name in EXPORT_FORMATS:
        assert f"--format {format_name}" in text, (
            f"the README must show {STRIPE_EXPORT_COMMAND!r} "
            f"--format {format_name}"
        )


# Issue #230: the exported file names carry the UTC export date.
EXPORT_SAMPLE_FILE_NAME = "payments-2026-10-28.csv"


def test_readme_documents_the_dated_export_file_names():
    """Issue #230: the README shows the date suffix on the exported files."""
    body = _readme_subsection(README_EXPORT_HEADING)
    assert EXPORT_SAMPLE_FILE_NAME in body, (
        f"the {README_EXPORT_HEADING!r} section must show the dated export "
        f"file name {EXPORT_SAMPLE_FILE_NAME!r}"
    )


def test_readme_documents_the_summary_command_output():
    """Issue #221: one currency per line, thousands separators, upper-case."""
    text = _read(README)
    assert STRIPE_SUMMARY_COMMAND in text, (
        f"the README must document {STRIPE_SUMMARY_COMMAND!r}"
    )
    # The documented sample is the real line format, so the docs cannot drift
    # from what `summary` prints.
    assert SUMMARY_SAMPLE_LINE in text, (
        f"the README must show the summary line {SUMMARY_SAMPLE_LINE!r}"
    )


# Issue #243: the summary section shows the total line and says it adds up the
# printed currency values.
def test_readme_documents_the_summary_total_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert SUMMARY_TOTAL_SAMPLE_LINE in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary total "
        f"line {SUMMARY_TOTAL_SAMPLE_LINE!r}"
    )
    label = stripe_payments.SUMMARY_TOTAL_LABEL
    assert label in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the total line "
        f"label {label!r}"
    )


# Issue #234: `summary --currency usd` prints only the usd line.
def test_readme_documents_the_summary_currency_filter():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert STRIPE_SUMMARY_COMMAND in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r}"
    )
    # Every flag the documented summary command passes must be a real flag of
    # the summary subparser, so the docs cannot drift from the command.
    flags = {
        flag
        for line in body.splitlines()
        if STRIPE_SUMMARY_COMMAND in line
        for flag in STRIPE_FLAG_RE.findall(line)
    }
    missing_flags = flags - _subparser_option_strings("summary")
    assert not missing_flags, (
        f"the README passes {sorted(missing_flags)} to "
        f"{STRIPE_SUMMARY_COMMAND!r}, but the summary subparser does not "
        "define them"
    )
    assert "--currency usd" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --currency usd"
    )


def test_readme_documents_the_chinese_csv_header():
    """Issue #235: the README shows the Chinese header row the export writes."""
    body = _readme_subsection(README_EXPORT_HEADING)
    header = ",".join(
        stripe_payments.EXPORT_HEADERS[column]
        for column in stripe_payments.EXPORT_COLUMNS["payments"]
    )
    assert header in body, (
        f"the {README_EXPORT_HEADING!r} section must show the exported CSV "
        f"header row {header!r}"
    )


# Issue #240: `summary --csv` writes the printed rows into a dated CSV file.
SUMMARY_CSV_SAMPLE_FILE_NAME = "summary-2026-10-28.csv"


def test_readme_documents_the_summary_csv_export():
    """Issue #240: the summary section shows the --csv usage and its file."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert f"{STRIPE_SUMMARY_COMMAND} --csv" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --csv"
    )
    # The documented header row is the one the CSV writer emits, so the docs
    # cannot drift away from the exported columns.
    header = ",".join(
        stripe_payments.EXPORT_HEADERS[column]
        for column in stripe_payments.SUMMARY_COLUMNS
    )
    assert header in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary CSV "
        f"header row {header!r}"
    )
    assert SUMMARY_CSV_SAMPLE_FILE_NAME in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the dated summary "
        f"CSV file name {SUMMARY_CSV_SAMPLE_FILE_NAME!r}"
    )


# Issue #248: `summary --by-month` groups the totals by month and currency.
SUMMARY_BY_MONTH_SAMPLE_LINE = (
    "2026-10 USD 付款 1,234.57 退款 1.00 净额 1,233.57"
)
# The sample data the README by-month block describes, rendered through the
# real `_summary_line()` below, so the docs cannot drift from the output.
SUMMARY_BY_MONTH_SAMPLE_DATA = (
    ("2026-09", "eur", 0, 200),
    ("2026-09", "jpy", 500, 0),
    ("2026-09", "usd", 1000, 50),
    ("2026-10", "eur", 1000, 0),
    ("2026-10", "usd", 123457, 100),
)


def test_readme_documents_the_summary_by_month_option():
    """Issue #248: the summary section shows the --by-month usage."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert "--by-month" in _subparser_option_strings("summary"), (
        "the summary subparser must define --by-month"
    )
    assert f"{STRIPE_SUMMARY_COMMAND} --by-month" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --by-month"
    )
    assert SUMMARY_BY_MONTH_SAMPLE_LINE in body, (
        f"the {README_SUMMARY_HEADING!r} section must show a by-month line "
        f"like {SUMMARY_BY_MONTH_SAMPLE_LINE!r}"
    )


def test_readme_shows_the_complete_by_month_summary_output():
    """Issue #248: the section shows the whole grouped output, in order."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    expected = "\n".join(
        stripe_payments._summary_line(
            currency, payments, refunds, month=month
        )
        for month, currency, payments, refunds in SUMMARY_BY_MONTH_SAMPLE_DATA
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --by-month` output, got:\n{body}"
    )


def test_readme_documents_the_by_month_csv_month_column():
    """Issue #248: `--by-month --csv` adds the `月份` column to the CSV."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert f"{STRIPE_SUMMARY_COMMAND} --by-month --csv" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --by-month --csv"
    )
    header = ",".join(
        stripe_payments.EXPORT_HEADERS[column]
        for column in stripe_payments.SUMMARY_COLUMNS_BY_MONTH
    )
    assert header in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the by-month CSV "
        f"header row {header!r}"
    )


def test_readme_documents_the_refunds_summary_command_output():
    """Issue #224/#249: one ISO week/currency per line, count and amount."""
    text = _read(README)
    assert STRIPE_REFUNDS_SUMMARY_COMMAND in text, (
        f"the README must document {STRIPE_REFUNDS_SUMMARY_COMMAND!r}"
    )
    # The documented sample is the real line format, so the docs cannot drift
    # from what `refunds-summary` prints.
    assert REFUNDS_SUMMARY_SAMPLE_LINE in text, (
        f"the README must show the refunds-summary line "
        f"{REFUNDS_SUMMARY_SAMPLE_LINE!r}"
    )


def _readme_subsection(heading: str) -> str:
    """Return the body of a `### ` README subsection, up to the next heading."""
    text = _read(README)
    assert f"\n{heading}\n" in text, f"the README needs a {heading!r} section"
    body = text.split(f"\n{heading}\n", 1)[1]
    for marker in ("\n## ", "\n### "):
        body = body.split(marker, 1)[0]
    return body


def test_readme_documents_the_refunds_summary_usage_next_to_export_and_summary():
    """Issue #225: the usage sits with the export and summary sections."""
    text = _read(README)
    headings = (
        README_EXPORT_HEADING,
        README_SUMMARY_HEADING,
        README_REFUNDS_SUMMARY_HEADING,
    )
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions), (
        f"the README must document {', '.join(headings)} in that order"
    )
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    assert STRIPE_REFUNDS_SUMMARY_COMMAND in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show how to run "
        f"{STRIPE_REFUNDS_SUMMARY_COMMAND!r}"
    )
    # `refunds-summary` takes no options, so the documented command cannot pass
    # a flag the subparser does not define.
    flags = set(STRIPE_FLAG_RE.findall(body))
    missing_flags = flags - _subparser_option_strings("refunds-summary")
    assert not missing_flags, (
        f"the README passes {sorted(missing_flags)} to "
        f"{STRIPE_REFUNDS_SUMMARY_COMMAND!r}, but the refunds-summary "
        "subparser does not define them"
    )


def test_readme_shows_the_complete_refunds_summary_output():
    """Issue #225: the section shows the complete output, in the real order."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    expected = "\n".join(
        stripe_payments._refund_week_line(week, currency, count, amount)
        for week, currency, count, amount in REFUNDS_SUMMARY_SAMPLE_DATA
    )
    # The whole block is documented verbatim, so the reader sees every line in
    # the documented (week, currency) sort order instead of a single sample.
    assert expected in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        f"complete output of {STRIPE_REFUNDS_SUMMARY_COMMAND!r}, got:\n{body}"
    )


def test_live_payment_verification_cannot_run_on_push_or_pull_request():
    text = _read(WORKFLOW)
    assert "github.event_name == 'workflow_dispatch'" in text, (
        "the live job must be gated to workflow_dispatch"
    )
    assert "continue-on-error" not in text, (
        "a failed live charge must fail the workflow, never pass silently"
    )


def test_readme_documents_the_version_command():
    """Issue #254: the README shows `--version` and the line it prints."""
    option_strings = {
        option
        for action in stripe_payments._parser()._actions
        for option in action.option_strings
    }
    assert "--version" in option_strings, (
        "the top-level parser must define --version"
    )
    body = _readme_subsection(README_VERSION_HEADING)
    assert STRIPE_VERSION_COMMAND in body, (
        f"the {README_VERSION_HEADING!r} section must show "
        f"{STRIPE_VERSION_COMMAND!r}"
    )
    # The documented output is the line the command really prints.
    version_line = f"stripe_payments {stripe_payments.VERSION}"
    assert version_line in body, (
        f"the {README_VERSION_HEADING!r} section must show the version line "
        f"{version_line!r}"
    )
    # The printed version is the latest released version of the changelog,
    # so the number a run prints and the release notes cannot drift apart.
    assert f"## [v{stripe_payments.VERSION}]" in _read(CHANGELOG), (
        f"CHANGELOG.md needs a [v{stripe_payments.VERSION}] release entry "
        "matching the printed version"
    )
