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
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
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
# Issue #375: the repository ships a short code of conduct page under docs/.
CODE_OF_CONDUCT = REPO_ROOT / "docs" / "CODE_OF_CONDUCT.md"
CODE_OF_CONDUCT_HEADING = "# Code of Conduct"
# Issue #380: the support page tells readers where to get help.
SUPPORT_PAGE = REPO_ROOT / "docs" / "SUPPORT.md"
SUPPORT_HEADING = "# Support"
# Issue #382: the glossary explains the words the README uses.
GLOSSARY_PAGE = REPO_ROOT / "docs" / "GLOSSARY.md"
GLOSSARY_HEADING = "# Glossary"
GLOSSARY_TERM_PREFIX = "## "
# Issue #386: the contributor FAQ answers the first three questions a new
# contributor asks, and every answer names the real entry point.
CONTRIBUTOR_FAQ_PAGE = REPO_ROOT / "docs" / "CONTRIBUTOR-FAQ.md"
CONTRIBUTOR_FAQ_HEADING = "# Contributor FAQ"
CONTRIBUTOR_INSTALL_COMMAND = "python -m pip install pytest stripe"
CONTRIBUTOR_TEST_COMMAND = "python -m pytest"
# Relative markdown links (no scheme, no in-page anchor) must resolve to a
# file that really exists in the repository.
MARKDOWN_LINK_RE = re.compile(r"\]\((?!https?://|#)([^)#]+)")


def _utc(*parts):
    """Stripe's UTC epoch seconds for a wall-clock UTC date/time."""
    return int(datetime(*parts, tzinfo=timezone.utc).timestamp())


# The summary range sample covers records from 2026-09-05 to 2026-10-20 (UTC).
SUMMARY_RANGE_FIRST = _utc(2026, 9, 5, 0, 0, 0)
SUMMARY_RANGE_LAST = _utc(2026, 10, 20, 23, 59, 59)

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
# Issue #290: after the total line the summary prints the record count.
SUMMARY_COUNT_SAMPLE_LINE = "总笔数 4"
# Issue #292: after the count line the summary prints the average amount.
SUMMARY_AVERAGE_SAMPLE_LINE = "平均金额 310.89"
# Issue #294: after the average line the summary prints the largest amount.
SUMMARY_LARGEST_SAMPLE_LINE = "最大单笔金额 1,234.57"
# Issue #296: after the largest line the summary prints the smallest amount.
SUMMARY_SMALLEST_SAMPLE_LINE = "最小单笔金额 0.01"
# Issue #321: every full summary run opens with the UTC day range it totalled;
# the earliest and latest totalled record of the documented sample are below.
SUMMARY_RANGE_SAMPLE_LINE = "统计范围 2026-09-05..2026-10-20"
# Issue #224: the README documents the refunds-summary command and its line format.
STRIPE_REFUNDS_SUMMARY_COMMAND = "python -m stripe_payments refunds-summary"
REFUNDS_SUMMARY_SAMPLE_LINE = "2026-W44 usd 退款 2 笔 3.50"
# Issue #225: the refunds-summary usage sits next to the export and summary
# sections and shows the complete output the command prints.
README_EXPORT_HEADING = "### 导出付款数据（export）"
README_SUMMARY_HEADING = "### 汇总收入（summary）"
README_REFUNDS_SUMMARY_HEADING = "### 按周汇总退款（refunds-summary）"
# Issue #398: a short "Refund summary" section describes the summary behaviour
# and names the commit that behaviour follows.
README_REFUND_SUMMARY_HEADING = "## Refund summary"
README_REFUND_SUMMARY_COMMIT = "809bb78399a49e062e7564c024e83c70a6b75834"
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
# Issue #120 appends this exact line as the new README final line; Issue #282
# appends the license line after it, so it stays in the README, not at the end.
README_REGRESSION_LINE = "Beta regression: Gemini native protocol hotfix v0.7.40."
# Issue #282 appends this exact line as the README final line; Issue #297
# appends the contributing note after it, so it stays in the README.
README_LICENSE_LINE = "本项目以 MIT 许可证发布。"
# Issue #297 appends this exact line as the README final line; Issue #328
# appends the test command after it, so it stays in the README.
README_CONTRIBUTING_LINE = "想贡献请先开一个 Issue 说明你的想法，确认后再动手。"
# Issue #328 appends this exact line as the README final line; Issue #331
# appends the beta acceptance line after it, so it stays in the README.
README_PYTEST_NOTE_LINE = "运行测试请执行 python -m pytest。"
# Issue #331 appends this exact line as the README final line; Issue #333
# appends the v0.8.56 acceptance line after it, so it stays in the README.
README_V0854_ACCEPTANCE_LINE = "Beta 新用户全流程验收：v0.8.54（2026-11-14）。"
# Issue #333 appends this exact line as the README final line; Issue #335
# appends the `Last checked:` note after it, so it stays in the README.
README_V0856_ACCEPTANCE_LINE = "Beta 新用户全流程验收：v0.8.56（2026-11-15）。"
# Issue #335 appends this exact line as the README final line; Issue #337
# appends the engine check line after it, so it stays in the README.
README_LAST_CHECKED_LINE = "Last checked: 2026-11-16"
# Issue #337 appends this exact line as the README final line; Issue #339
# appends the cloud check line after it and Issue #341 the new engine check
# line, so it stays in the README.
README_ENGINE_CHECK_LINE = "Engine check: v0.7.44 (2026-11-16)"
# Issue #339 appends this exact line as the README final line; Issue #341
# appends the new engine check line after it, so it stays in the README.
README_CLOUD_CHECK_LINE = "Cloud check: v0.8.58 (2026-11-16)"
# Issue #341 appends this exact line as the README final line; Issue #343
# appends the trial check line after it, so it stays in the README.
README_ENGINE_CHECK_V0745_LINE = "Engine check: v0.7.45 (2026-11-16)"
# Issue #343 appends this exact line as the README final line; Issue #349
# appends the contributing note after it, so it stays in the README.
README_TRIAL_CHECK_LINE = "Trial check (2026-11-18)"
# Issue #26 appends this exact line as the README final line; Issue #455
# appends the changelog line after it, so it stays in the README.
README_TEST_COMMAND_LINE = "测试命令：`python -m pytest`"
# Issue #455 appends this exact line as the new README final line.
README_LAST_LINE = "- 2026-11-21: C4 label check."
# Issue #455 closes the README with a `## Changelog` section holding that line.
README_CHANGELOG_HEADING = "## Changelog"
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
# Issue #426: the 「Run the tests locally」 section leads with the command the
# reader can actually run, `python -m pytest`; the `unittest` command below
# stays in the section only as the one that does not run the tests.
README_LOCAL_TEST_COMMAND = "python -m pytest"

# Issue #207 adds a Chinese 「运行测试」 section that runs every test with the
# same command as the CI `Run tests` step.
README_RUN_TESTS_HEADING = "## 运行测试"
README_RUN_TESTS_COMMAND = "python -m pytest"
README_RUN_TESTS_DEPENDENCIES = "python -m pip install pytest stripe"
# Issue #396: one English 「Running the tests」 section answers "which single
# command runs the whole suite?" on one line, with the CI entry point.
README_RUNNING_TESTS_HEADING = "## Running the tests"
README_RUNNING_TESTS_COMMAND = "python -m pytest"
# Issue #277: one line in the README intro states how to run the tests, so a
# reader sees the command on the first screen; it links to the detailed
# 「运行测试」 section.
README_RUN_TESTS_LINE = (
    "运行测试：在仓库根目录执行 `python -m pytest`"
    "（与 CI 的 `Run tests` 步骤同一个命令，详见 [运行测试](#运行测试)）。"
)

# Issue #427: the paragraph directly below the README title says what this
# repository is, so a visitor knows it on the first screen.
README_FIRST_PARAGRAPH = "本仓库是 Orbi beta 的端到端测试仓库。"

# Issue #284 opens the README with a 「快速开始」 section so a first-time visitor
# sees the test command, where to run it and the line a passing run prints.
README_QUICK_START_HEADING = "## 快速开始"
README_QUICK_START_COMMAND = "python -m pytest -q"
README_QUICK_START_LOCATION = "仓库根目录"

# Issue #286: the README's 「常见问题」 section opens with the export question,
# answered with the directory the export command really writes to.
README_FAQ_HEADING = "## 常见问题"
README_FAQ_EXPORT_QUESTION = "Q：导出的文件在哪里"

# Issue #527 appends one more 「常见问题」 section at the very end of the README,
# written as the screenshot shows: the Python version and the default output
# directory, one `Q：`/`A：` pair per answer.
README_FAQ_PYTHON_QUESTION = "Q：运行要什么 Python 版本？"
README_FAQ_PYTHON_ANSWER = "A：3.10 及以上。"
README_FAQ_OUTPUT_QUESTION = "Q：输出写到哪里？"
README_FAQ_OUTPUT_ANSWER = "A：默认写到 out/ 目录。"

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


def test_readme_first_paragraph_states_this_is_the_beta_e2e_repository():
    """Issue #427: the paragraph below the title says what this repo is."""
    paragraphs = [
        block.strip() for block in _read(README).split("\n\n") if block.strip()
    ]
    assert paragraphs, "README.md has no paragraph"
    # The first block is the `# ` title; the paragraph below it is the intro.
    intro = paragraphs[1] if paragraphs[0].startswith("# ") else paragraphs[0]
    assert intro == README_FIRST_PARAGRAPH, (
        f"the README's first paragraph must be {README_FIRST_PARAGRAPH!r}, "
        f"got {intro!r}"
    )


def test_readme_documents_running_the_tests_locally():
    """Issue #202: the README shows the command that runs the local tests."""
    text = _read(README)
    assert README_TESTS_HEADING in text, (
        f"the README needs a {README_TESTS_HEADING!r} section"
    )
    assert README_TESTS_COMMAND in text, (
        f"the {README_TESTS_HEADING!r} section must show {README_TESTS_COMMAND!r}"
    )


def test_readme_run_the_tests_locally_section_names_the_pytest_command():
    """Issue #426: the local test command is `python -m pytest`."""
    body = _readme_section(README_TESTS_HEADING)
    # The first command a reader meets in this section is the one that really
    # runs the tests, on its own line.
    assert "```sh\n" in body, (
        f"the {README_TESTS_HEADING!r} section must show a shell command block"
    )
    first_command = body.split("```sh\n", 1)[1].split("\n```", 1)[0]
    assert first_command.strip() == README_LOCAL_TEST_COMMAND, (
        f"the first command of the {README_TESTS_HEADING!r} section must be "
        f"{README_LOCAL_TEST_COMMAND!r}, got {first_command.strip()!r}"
    )
    assert README_LOCAL_TEST_COMMAND in body.splitlines(), (
        f"the {README_TESTS_HEADING!r} section must spell "
        f"{README_LOCAL_TEST_COMMAND!r} out on its own line"
    )
    # The documented command is the CI entry point, so the section cannot
    # drift away from the tests CI really runs.
    assert README_LOCAL_TEST_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must use {README_LOCAL_TEST_COMMAND!r}"
    )
    # The `unittest` command stays documented as the one that does not run the
    # tests, so a reader who meets it elsewhere knows why it reports nothing.
    assert README_TESTS_COMMAND in body, (
        f"the {README_TESTS_HEADING!r} section must still name "
        f"{README_TESTS_COMMAND!r} as the command that does not run the tests"
    )
    assert "NO TESTS RAN" in body, (
        f"the {README_TESTS_HEADING!r} section must say the {README_TESTS_COMMAND!r} "
        "command does not run the tests"
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


def test_readme_has_a_one_line_running_the_tests_section():
    """Issue #396: one line names the single command that runs the suite."""
    text = _read(README)
    assert f"\n{README_RUNNING_TESTS_HEADING}\n" in text, (
        f"the README needs a {README_RUNNING_TESTS_HEADING!r} section"
    )
    body = text.split(f"\n{README_RUNNING_TESTS_HEADING}\n", 1)[1]
    body = body.split("\n## ", 1)[0]
    # The body directly below the heading is a single line: no code fence and
    # no second paragraph a reader would have to choose between.
    body_lines = [line.strip() for line in body.splitlines() if line.strip()]
    assert len(body_lines) == 1, (
        f"the {README_RUNNING_TESTS_HEADING!r} section body must be exactly "
        f"one non-empty line, got {body_lines!r}"
    )
    assert README_RUNNING_TESTS_COMMAND in body_lines[0], (
        f"the {README_RUNNING_TESTS_HEADING!r} line must name "
        f"{README_RUNNING_TESTS_COMMAND!r}"
    )
    assert "```" not in body, (
        f"the {README_RUNNING_TESTS_HEADING!r} section needs no fenced code "
        "block"
    )
    # The documented command is the entry point of the CI Run tests step, so
    # this section cannot drift away from the real test command.
    assert README_RUNNING_TESTS_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must use {README_RUNNING_TESTS_COMMAND!r}"
    )


def test_readme_has_a_quick_start_section():
    """Issue #284: a 「快速开始」 section runs every test with one command."""
    body = _readme_section(README_QUICK_START_HEADING)
    assert README_QUICK_START_COMMAND in body, (
        f"the {README_QUICK_START_HEADING!r} section must show "
        f"{README_QUICK_START_COMMAND!r}"
    )
    # The documented command is the one CI runs, so the section cannot drift
    # away from the real test entry point.
    assert README_QUICK_START_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must use {README_QUICK_START_COMMAND!r}"
    )
    # A first-time reader must know where to type the command and what a
    # passing run prints, so the section states both.
    assert README_QUICK_START_LOCATION in body, (
        f"the {README_QUICK_START_HEADING!r} section must say the command runs "
        f"in the {README_QUICK_START_LOCATION!r}"
    )
    assert re.search(r"\b\d+ passed", body), (
        f"the {README_QUICK_START_HEADING!r} section must show a sample "
        "passing pytest summary line, e.g. '180 passed'"
    )


def test_readme_states_the_test_command_up_front():
    """Issue #277: the README intro states how to run the tests in one line."""
    text = _read(README)
    assert README_RUN_TESTS_LINE in text, (
        f"the README needs the line {README_RUN_TESTS_LINE!r}"
    )
    intro = text.split("\n## ", 1)[0]
    assert README_RUN_TESTS_LINE in intro, (
        "the run-the-tests line must sit in the README intro, before the "
        "first `## ` section"
    )
    # The documented command is the one CI runs, so the line cannot drift away
    # from the real test entry point.
    assert README_RUN_TESTS_COMMAND in README_RUN_TESTS_LINE
    assert README_RUN_TESTS_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must use {README_RUN_TESTS_COMMAND!r}"
    )
    # The link resolves to the heading that carries the detailed instructions.
    anchor = README_RUN_TESTS_LINE.split("](#", 1)[1].split(")", 1)[0]
    assert anchor == README_RUN_TESTS_HEADING.removeprefix("## "), (
        f"the link must target the {README_RUN_TESTS_HEADING!r} heading"
    )
    assert f"\n{README_RUN_TESTS_HEADING}\n" in text, (
        f"the README needs a {README_RUN_TESTS_HEADING!r} section"
    )


def test_readme_ends_with_the_faq_answer_and_keeps_the_notes():
    """Issue #527: the README ends with the appended FAQ answer."""
    lines = [line for line in _read(README).splitlines() if line.strip()]
    assert lines[-1] == README_FAQ_OUTPUT_ANSWER, (
        f"the README must end with the {README_FAQ_OUTPUT_ANSWER!r} line, "
        f"got {lines[-1]!r}"
    )
    # Issue #455's changelog line stays in the README, right above the new
    # FAQ section, so appending the section does not drop it.
    assert README_LAST_LINE in lines, (
        f"the README must still carry the {README_LAST_LINE!r} line"
    )
    # Issue #26's test command note stays in the README, right above the
    # changelog section, so appending it does not drop the line.
    assert README_TEST_COMMAND_LINE in lines, (
        f"the README must still carry the {README_TEST_COMMAND_LINE!r} line"
    )
    # Issue #337's engine check line stays in the README, right above the new
    # one, so appending the cloud check and the new engine check lines does
    # not drop it.
    assert README_ENGINE_CHECK_LINE in lines, (
        f"the README must still carry the {README_ENGINE_CHECK_LINE!r} line"
    )
    # Issue #339's cloud check line stays in the README, right above the new
    # one, so appending the engine check line does not drop it.
    assert README_CLOUD_CHECK_LINE in lines, (
        f"the README must still carry the {README_CLOUD_CHECK_LINE!r} line"
    )
    # Issue #341's engine check line stays in the README, right above the new
    # one, so appending the trial check line does not drop it.
    assert README_ENGINE_CHECK_V0745_LINE in lines, (
        f"the README must still carry the {README_ENGINE_CHECK_V0745_LINE!r} line"
    )
    # Issue #343's trial check line stays in the README, right above the new
    # one, so appending the contributing note does not drop it.
    assert README_TRIAL_CHECK_LINE in lines, (
        f"the README must still carry the {README_TRIAL_CHECK_LINE!r} line"
    )
    # Issue #335's `Last checked:` note stays in the README, right above the
    # new one, so appending the engine check line does not drop it.
    assert README_LAST_CHECKED_LINE in lines, (
        f"the README must still carry the {README_LAST_CHECKED_LINE!r} line"
    )
    # Issue #333's v0.8.56 acceptance line stays in the README, right above the
    # new one, so appending the `Last checked:` line does not drop it; Issue
    # #331's v0.8.54 acceptance line stays there too.
    assert README_V0856_ACCEPTANCE_LINE in lines, (
        f"the README must still carry the {README_V0856_ACCEPTANCE_LINE!r} line"
    )
    assert README_V0854_ACCEPTANCE_LINE in lines, (
        f"the README must still carry the {README_V0854_ACCEPTANCE_LINE!r} line"
    )
    # Issue #328's test command note stays in the README, right above the
    # acceptance lines, and it still names the command the CI `Run tests` step
    # runs, so the reader reaches the real test entry point.
    assert README_PYTEST_NOTE_LINE in lines, (
        f"the README must still carry the {README_PYTEST_NOTE_LINE!r} line"
    )
    assert README_RUN_TESTS_COMMAND in README_PYTEST_NOTE_LINE, (
        f"the test command note must name {README_RUN_TESTS_COMMAND!r}"
    )
    # Issue #297's contributing note stays in the README, right above the test
    # command line, so appending the line does not drop it; Issue #282's
    # license line and Issue #120's regression marker stay there too.
    assert README_CONTRIBUTING_LINE in lines, (
        f"the README must still carry the {README_CONTRIBUTING_LINE!r} line"
    )
    assert README_LICENSE_LINE in lines, (
        f"the README must still carry the {README_LICENSE_LINE!r} line"
    )
    assert README_REGRESSION_LINE in lines, (
        f"the README must still carry the {README_REGRESSION_LINE!r} line"
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


# Issue #442: `export --days 30` exports only the records created in the
# rolling 30*24-hour window, with the same window and validation as
# `summary --days 30` and `refunds-summary --days 30`.  The export section
# shows the command, the counts line of the window, the shared `created[gte]`
# filter, the later `--since` edge and the failure path, and the changelog
# records the new option.
EXPORT_DAYS_SAMPLE_LINE = (
    "exported payments=2 refunds=1 customers=1 to "
    f"{stripe_payments.DEFAULT_OUTPUT_DIR}/"
)


def test_readme_documents_the_export_days_option():
    """Issue #442: the export section shows `--days N` and its window."""
    body = _readme_subsection(README_EXPORT_HEADING)
    assert "--days" in _subparser_option_strings("export"), (
        "the export subparser must define --days"
    )
    command = f"{STRIPE_EXPORT_COMMAND} --days 30 --format csv"
    assert command in body, (
        f"the {README_EXPORT_HEADING!r} section must show {command!r}"
    )
    assert EXPORT_DAYS_SAMPLE_LINE in body, (
        f"the {README_EXPORT_HEADING!r} section must show the exported counts "
        f"line of the --days window {EXPORT_DAYS_SAMPLE_LINE!r}"
    )
    unwrapped = body.replace("\n", "")
    # The window is pushed down as the list filter, so the reader knows only
    # that stretch of time is read.
    assert "created[gte]" in unwrapped, (
        f"the {README_EXPORT_HEADING!r} section must name the created[gte] "
        "list filter of the --days window"
    )
    # --since and --days intersect on the later lower edge, like summary.
    assert "`--days` 与 `--since` 一起用时下界取两者更晚的那个" in unwrapped, (
        f"the {README_EXPORT_HEADING!r} section must say --since with --days "
        "keeps the later lower edge"
    )
    # The failure path and its repair are documented next to the example.
    assert "error: --days must be positive, got 0" in unwrapped, (
        f"the {README_EXPORT_HEADING!r} section must show the --days 0 "
        "failure message"
    )
    unreleased = _read(CHANGELOG).split("## [Unreleased]", 1)[1].split(
        "\n## ", 1
    )[0].replace("\n", "")
    assert "`export` 子命令新增 `--days N`" in unreleased, (
        "CHANGELOG.md must record export --days under [Unreleased]"
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


# Issue #312: `export --since/--until` exports only that UTC day window, both
# edges included, and the command still ends with the exported counts line.
def test_readme_documents_the_export_day_window():
    """Issue #312: the export section shows --since/--until and its output."""
    body = _readme_subsection(README_EXPORT_HEADING)
    option_strings = _subparser_option_strings("export")
    assert "--since" in option_strings, (
        "the export subparser must define --since"
    )
    assert "--until" in option_strings, (
        "the export subparser must define --until"
    )
    assert (
        f"{STRIPE_EXPORT_COMMAND} --since 2026-09-01 --until 2026-09-30 "
        "--format csv"
    ) in body, (
        f"the {README_EXPORT_HEADING!r} section must show "
        f"{STRIPE_EXPORT_COMMAND!r} --since 2026-09-01 --until 2026-09-30 "
        "--format csv"
    )
    expected = (
        "exported payments=1 refunds=1 customers=2 to "
        f"{stripe_payments.DEFAULT_OUTPUT_DIR}/"
    )
    assert expected in body, (
        f"the {README_EXPORT_HEADING!r} section must show the exported counts "
        f"line {expected!r}"
    )
    assert "00:00:00Z" in body and "23:59:59Z" in body, (
        f"the {README_EXPORT_HEADING!r} section must say both day edges are "
        "included (00:00:00Z and 23:59:59Z)"
    )
    assert "只传" in body, (
        f"the {README_EXPORT_HEADING!r} section must say either date works alone"
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


# Issue #290: the summary closes with the number of records it added up.
def test_readme_documents_the_summary_count_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert stripe_payments.SUMMARY_COUNT_LABEL in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the count line "
        f"label {stripe_payments.SUMMARY_COUNT_LABEL!r}"
    )
    # The documented sample is rendered through the real line helper, so the
    # docs cannot drift from what `summary` prints.
    expected = stripe_payments._summary_count_line(4)
    assert expected == SUMMARY_COUNT_SAMPLE_LINE, (
        "the sample count line must be the real line format"
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary count "
        f"line {expected!r}"
    )


# Issue #292: the summary closes with the average amount per record.
def test_readme_documents_the_summary_average_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert stripe_payments.SUMMARY_AVERAGE_LABEL in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the average line "
        f"label {stripe_payments.SUMMARY_AVERAGE_LABEL!r}"
    )
    # The documented sample is rendered through the real line helper, so the
    # docs cannot drift from what `summary` prints.
    expected = stripe_payments._summary_average_line(124357, 4)
    assert expected == SUMMARY_AVERAGE_SAMPLE_LINE, (
        "the sample average line must be the real line format"
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary "
        f"average line {expected!r}"
    )


# Issue #294: the summary closes with the largest single amount.
def test_readme_documents_the_summary_largest_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert stripe_payments.SUMMARY_LARGEST_LABEL in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the largest line "
        f"label {stripe_payments.SUMMARY_LARGEST_LABEL!r}"
    )
    # The documented sample is rendered through the real line helper, so the
    # docs cannot drift from what `summary` prints.
    expected = stripe_payments._summary_largest_line(123457)
    assert expected == SUMMARY_LARGEST_SAMPLE_LINE, (
        "the sample largest line must be the real line format"
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary "
        f"largest line {expected!r}"
    )


# Issue #296: the summary closes with the smallest single amount.
def test_readme_documents_the_summary_smallest_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert stripe_payments.SUMMARY_SMALLEST_LABEL in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the smallest line "
        f"label {stripe_payments.SUMMARY_SMALLEST_LABEL!r}"
    )
    # The documented sample is rendered through the real line helper, so the
    # docs cannot drift from what `summary` prints.
    expected = stripe_payments._summary_smallest_line(1)
    assert expected == SUMMARY_SMALLEST_SAMPLE_LINE, (
        "the sample smallest line must be the real line format"
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary "
        f"smallest line {expected!r}"
    )


# Issue #321: every full summary run opens with the UTC date range it totalled.
def test_readme_documents_the_summary_range_line():
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert stripe_payments.SUMMARY_RANGE_LABEL in body, (
        f"the {README_SUMMARY_HEADING!r} section must name the range line "
        f"label {stripe_payments.SUMMARY_RANGE_LABEL!r}"
    )
    # The documented sample is rendered through the real line helper, so the
    # docs cannot drift from what `summary` prints.
    expected = stripe_payments._summary_range_line(
        SUMMARY_RANGE_FIRST, SUMMARY_RANGE_LAST
    )
    assert expected == SUMMARY_RANGE_SAMPLE_LINE, (
        "the sample range line must be the real line format"
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the summary "
        f"range line {expected!r}"
    )
    # An account with no record prints the same label with the empty text.
    empty = (
        f"{stripe_payments.SUMMARY_RANGE_LABEL} "
        f"{stripe_payments.SUMMARY_NO_RECORDS}"
    )
    assert stripe_payments._summary_range_line(None, None) == empty
    assert empty in body, (
        f"the {README_SUMMARY_HEADING!r} section must show {empty!r} for an "
        f"account with no record"
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


# Issue #303: `summary --since/--until` reads only that UTC day window.  The
# expected lines are rendered through the real helpers below, so the documented
# sample cannot drift from what the command prints.
SUMMARY_WINDOW_SAMPLE_DATA = (
    ("eur", 1000, 25),
    ("gbp", 250, 0),
    ("usd", 123457, 100),
)


def test_readme_documents_the_summary_day_window():
    """Issue #303: the section shows --since/--until and its sample output."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    option_strings = _subparser_option_strings("summary")
    assert "--since" in option_strings, (
        "the summary subparser must define --since"
    )
    assert "--until" in option_strings, (
        "the summary subparser must define --until"
    )
    assert (
        f"{STRIPE_SUMMARY_COMMAND} --since 2026-09-01 --until 2026-09-30"
        in body
    ), (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --since 2026-09-01 --until 2026-09-30"
    )
    payments = sum(
        stripe_payments._summary_hundredths(amount, currency)
        for currency, amount, _ in SUMMARY_WINDOW_SAMPLE_DATA
    )
    refunds = sum(
        stripe_payments._summary_hundredths(amount, currency)
        for currency, _, amount in SUMMARY_WINDOW_SAMPLE_DATA
    )
    expected = "\n".join(
        [
            stripe_payments._summary_line(currency, amount, refund)
            for currency, amount, refund in SUMMARY_WINDOW_SAMPLE_DATA
        ]
        + [
            stripe_payments._summary_total_line(payments, refunds),
            stripe_payments._summary_count_line(5),
            stripe_payments._summary_average_line(payments - refunds, 5),
            stripe_payments._summary_largest_line(123457),
            stripe_payments._summary_smallest_line(25),
        ]
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --since ... --until ...` output, expected:\n{expected}"
    )


# Issue #285: `summary --by-customer` groups the totals by paying customer.
# The sample data is the README's by-customer block, rendered through the real
# line helpers below, so the docs cannot drift from the output.
SUMMARY_BY_CUSTOMER_SAMPLE_DATA = (
    ("cus_alpha", "usd", 123457, 100),
    ("cus_beta", "eur", 1000, 0),
    ("（未归属客户）", "usd", 500, 50),
)


def test_readme_documents_the_summary_by_customer_option():
    """Issue #285: the summary section shows the --by-customer usage."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert "--by-customer" in _subparser_option_strings("summary"), (
        "the summary subparser must define --by-customer"
    )
    assert f"{STRIPE_SUMMARY_COMMAND} --by-customer" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --by-customer"
    )
    assert SUMMARY_BY_CUSTOMER_SAMPLE_DATA[2][0] == (
        stripe_payments.SUMMARY_UNATTRIBUTED_CUSTOMER
    ), "the sample's last group must be the real unattributed group label"
    expected = "\n".join(
        stripe_payments._summary_line(
            currency, payments, refunds, customer=customer
        )
        for customer, currency, payments, refunds in SUMMARY_BY_CUSTOMER_SAMPLE_DATA
    ) + "\n" + stripe_payments._summary_total_line(
        sum(
            stripe_payments._summary_hundredths(payments, currency)
            for _, currency, payments, _ in SUMMARY_BY_CUSTOMER_SAMPLE_DATA
        ),
        sum(
            stripe_payments._summary_hundredths(refunds, currency)
            for _, currency, _, refunds in SUMMARY_BY_CUSTOMER_SAMPLE_DATA
        ),
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --by-customer` output, got:\n{body}"
    )


def test_readme_documents_the_by_customer_csv_customer_column():
    """Issue #285: `--by-customer --csv` adds the `客户` column to the CSV."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert f"{STRIPE_SUMMARY_COMMAND} --by-customer --csv" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --by-customer --csv"
    )
    header = ",".join(
        stripe_payments.EXPORT_HEADERS[column]
        for column in stripe_payments.SUMMARY_COLUMNS_BY_CUSTOMER
    )
    assert header in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the by-customer "
        f"CSV header row {header!r}"
    )


# Issue #260: `summary --quiet` prints only the net total per currency.
# The sample data is the README's quiet output block, rendered through the real
# `_summary_net_line()` below, so the docs cannot drift from the output.
QUIET_SAMPLE_DATA = (("eur", 1000, 0), ("usd", 123457, 100))


def test_readme_documents_the_summary_quiet_option():
    """Issue #260: the summary section shows the --quiet usage and its output."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert "--quiet" in _subparser_option_strings("summary"), (
        "the summary subparser must define --quiet"
    )
    assert f"{STRIPE_SUMMARY_COMMAND} --quiet" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --quiet"
    )
    expected = "\n".join(
        stripe_payments._summary_net_line(currency, payments, refunds)
        for currency, payments, refunds in QUIET_SAMPLE_DATA
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --quiet` output, got:\n{body}"
    )


# Issue #262: `summary --top 2` prints only the two largest net currencies.
# The sample data is the README's `--top` block, rendered through the real line
# helpers below, so the docs cannot drift from the output.
TOP_SAMPLE_DATA = (("usd", 123457, 100), ("eur", 50000, 0))


def test_readme_documents_the_summary_top_option():
    """Issue #262: the summary section shows the --top usage and its output."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert "--top" in _subparser_option_strings("summary"), (
        "the summary subparser must define --top"
    )
    assert f"{STRIPE_SUMMARY_COMMAND} --top 2" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --top 2"
    )
    expected = "\n".join(
        stripe_payments._summary_line(currency, payments, refunds)
        for currency, payments, refunds in TOP_SAMPLE_DATA
    ) + "\n" + stripe_payments._summary_total_line(
        sum(payments for _, payments, _ in TOP_SAMPLE_DATA),
        sum(refunds for _, _, refunds in TOP_SAMPLE_DATA),
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --top 2` output, got:\n{body}"
    )


# Issue #271: `summary --days 30` reads only the last 30 days.
# The sample data is the README's `--days` block, rendered through the real
# line helpers below, so the docs cannot drift from the output.
DAYS_SAMPLE_DATA = (("eur", 1000, 0), ("usd", 123457, 100))


def test_readme_documents_the_summary_days_option():
    """Issue #271: the summary section shows the --days usage and its output."""
    body = _readme_subsection(README_SUMMARY_HEADING)
    assert "--days" in _subparser_option_strings("summary"), (
        "the summary subparser must define --days"
    )
    assert f"{STRIPE_SUMMARY_COMMAND} --days 30" in body, (
        f"the {README_SUMMARY_HEADING!r} section must show "
        f"{STRIPE_SUMMARY_COMMAND!r} --days 30"
    )
    expected = "\n".join(
        stripe_payments._summary_line(currency, payments, refunds)
        for currency, payments, refunds in DAYS_SAMPLE_DATA
    ) + "\n" + stripe_payments._summary_total_line(
        sum(payments for _, payments, _ in DAYS_SAMPLE_DATA),
        sum(refunds for _, _, refunds in DAYS_SAMPLE_DATA),
    )
    assert expected in body, (
        f"the {README_SUMMARY_HEADING!r} section must show the complete "
        f"`summary --days 30` output, got:\n{body}"
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
    """Issue #225/#319: the complete output, week rows then the total row."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    lines = [
        stripe_payments._refund_week_line(week, currency, count, amount)
        for week, currency, count, amount in REFUNDS_SUMMARY_SAMPLE_DATA
    ]
    # Issue #319: the last line totals exactly the week rows above it.
    lines.append(
        stripe_payments._refund_total_line(
            sum(count for _, _, count, _ in REFUNDS_SUMMARY_SAMPLE_DATA),
            sum(
                stripe_payments._summary_hundredths(amount, currency)
                for _, currency, _, amount in REFUNDS_SUMMARY_SAMPLE_DATA
            ),
        )
    )
    expected = "\n".join(lines)
    # The whole block is documented verbatim, so the reader sees every line in
    # the documented (week, currency) sort order instead of a single sample.
    assert expected in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        f"complete output of {STRIPE_REFUNDS_SUMMARY_COMMAND!r}, got:\n{body}"
    )


def test_readme_documents_the_refunds_summary_csv_export():
    """Issue #304: the section shows --csv/--output-dir, header and notice."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    for flag in ("--csv", "--output-dir"):
        assert flag in body, (
            f"the {README_REFUNDS_SUMMARY_HEADING!r} section must document "
            f"the {flag} option of {STRIPE_REFUNDS_SUMMARY_COMMAND!r}"
        )
    # The documented CSV header and closing notice are the real ones, so the
    # README cannot drift from what the command writes and prints.
    assert ",".join(
        stripe_payments.REFUNDS_SUMMARY_HEADERS[column]
        for column in stripe_payments.REFUNDS_SUMMARY_COLUMNS
    ) in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the CSV "
        "header row"
    )
    assert "exported refunds-summary rows=" in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        "printed file notice of --csv"
    )


# Issue #313: `refunds-summary --since/--until` counts only the refunds created
# inside that UTC day window.  The expected lines are rendered through the real
# helpers below, so the documented sample cannot drift from the output.
REFUNDS_SUMMARY_WINDOW_SAMPLE_DATA = (("2026-W40", "eur", 1, 100),)


def test_readme_documents_the_refunds_summary_day_window():
    """Issue #313: the section shows --since/--until and its sample output."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    option_strings = _subparser_option_strings("refunds-summary")
    assert "--since" in option_strings, (
        "the refunds-summary subparser must define --since"
    )
    assert "--until" in option_strings, (
        "the refunds-summary subparser must define --until"
    )
    command = (
        f"{STRIPE_REFUNDS_SUMMARY_COMMAND} --since 2026-09-01 "
        "--until 2026-09-30"
    )
    assert command in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show "
        f"{command!r}"
    )
    lines = [
        stripe_payments._refund_week_line(week, currency, count, amount)
        for week, currency, count, amount in REFUNDS_SUMMARY_WINDOW_SAMPLE_DATA
    ]
    lines.append(
        stripe_payments._refund_total_line(
            sum(
                count
                for _, _, count, _ in REFUNDS_SUMMARY_WINDOW_SAMPLE_DATA
            ),
            sum(
                stripe_payments._summary_hundredths(amount, currency)
                for _, currency, _, amount in REFUNDS_SUMMARY_WINDOW_SAMPLE_DATA
            ),
        )
    )
    expected = "\n".join(lines)
    assert expected in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        f"complete window output, expected:\n{expected}"
    )
    # The window is pushed down as the Refunds list filters, so the reader
    # knows only that stretch of time is read.
    for flag in ("created[gte]", "created[lte]"):
        assert flag in body, (
            f"the {README_REFUNDS_SUMMARY_HEADING!r} section must name the "
            f"{flag} list filter of the day window"
        )
    # Both whole days are included and either date works alone.
    assert "两端都是整天" in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must say the window "
        "includes both whole days"
    )
    assert "只传一个" in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must say either date "
        "works alone"
    )


def test_readme_documents_the_refunds_summary_window_csv_rows():
    """Issue #313: with --csv the file carries only the window rows."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    assert "exported refunds-summary rows=1 to " in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        "--csv notice of the window example, so the reader sees the row count"
    )
    header = ",".join(
        stripe_payments.REFUNDS_SUMMARY_HEADERS[column]
        for column in stripe_payments.REFUNDS_SUMMARY_COLUMNS
    )
    rows = ["2026-W40,eur,1,1.00"]
    assert "\n".join([header, *rows]) in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the window "
        f"CSV as {[header, *rows]!r}"
    )


# Issue #371: `refunds-summary --days 30` counts only the refunds created in
# the rolling 30*24-hour window, so the section shows the command, its sample
# output, the later --since edge, the shared filter order and the failure path.
# The sample is the README refunds-summary data with the ISO week 40 usd row and
# both ISO week 44 rows inside the window.
REFUNDS_SUMMARY_DAYS_SAMPLE_DATA = (
    ("2026-W40", "usd", 1, 50),
    ("2026-W44", "eur", 1, 100),
    ("2026-W44", "usd", 2, 350),
)


def _refunds_summary_window_output(sample_data):
    """The week lines plus the `合计` line of the given refund week data."""
    lines = [
        stripe_payments._refund_week_line(week, currency, count, amount)
        for week, currency, count, amount in sample_data
    ]
    lines.append(
        stripe_payments._refund_total_line(
            sum(count for _, _, count, _ in sample_data),
            sum(
                stripe_payments._summary_hundredths(amount, currency)
                for _, currency, _, amount in sample_data
            ),
        )
    )
    return "\n".join(lines)


def test_readme_documents_the_refunds_summary_days_option():
    """Issue #371: the section shows `--days N` and its sample output."""
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    assert "--days" in _subparser_option_strings("refunds-summary"), (
        "the refunds-summary subparser must define --days"
    )
    command = f"{STRIPE_REFUNDS_SUMMARY_COMMAND} --days 30"
    assert command in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show "
        f"{command!r}"
    )
    expected = _refunds_summary_window_output(
        REFUNDS_SUMMARY_DAYS_SAMPLE_DATA
    )
    assert expected in body, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        f"complete `refunds-summary --days 30` output, expected:\n{expected}"
    )
    unwrapped = body.replace("\n", "")
    # The window is pushed down as the Refunds list filter, so the reader
    # knows only that stretch of time is read.
    assert "created[gte]" in unwrapped, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must name the "
        "created[gte] list filter of the --days window"
    )
    # --since and --days intersect on the later lower edge.
    assert "--days` 与 `--since` 一起用时下界取两者更晚的那个" in unwrapped, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must say --since with "
        "--days keeps the later lower edge"
    )
    # The failure path and its repair are documented next to the example.
    assert "error: --days must be positive, got 0" in unwrapped, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must show the "
        "--days 0 failure message"
    )
    unreleased = _read(CHANGELOG).split("## [Unreleased]", 1)[1].split(
        "\n## ", 1
    )[0].replace("\n", "")
    assert "`refunds-summary` 子命令新增 `--days N`" in unreleased, (
        "CHANGELOG.md must record refunds-summary --days under [Unreleased]"
    )


# Issue #352: `refunds-summary` counts only succeeded refunds, the same scope
# as `summary`, so both README sections describe one refund scope and the
# changelog records the change under [Unreleased].
def test_readme_documents_the_refunds_summary_succeeded_scope():
    body = _readme_subsection(README_REFUNDS_SUMMARY_HEADING)
    # The paragraph wraps, so the sentence is checked on one line.
    unwrapped = body.replace("\n", "")
    assert "只统计 Stripe 状态为 `succeeded` 的退款" in unwrapped, (
        f"the {README_REFUNDS_SUMMARY_HEADING!r} section must state the "
        "succeeded-only refund scope shared with `summary`"
    )
    # The statuses the command drops are named, so the reader knows what
    # stays out of the week rows, the total and the CSV.
    for status in ("`pending`", "`failed`", "`canceled`"):
        assert status in unwrapped, (
            f"the {README_REFUNDS_SUMMARY_HEADING!r} section must name the "
            f"{status} refunds it leaves out"
        )
    # The old claim is gone: the README must not describe the drift the code
    # no longer has.
    assert "统计范围不变" not in _read(README)
    unreleased = _read(CHANGELOG).split("## [Unreleased]", 1)[1].split(
        "\n## ", 1
    )[0]
    assert "只统计 Stripe 状态为 `succeeded` 的退款" in unreleased.replace(
        "\n", ""
    ), (
        "CHANGELOG.md must record the succeeded-only refunds-summary scope "
        "under [Unreleased]"
    )


# Issue #398: the README opens the refund docs with one short "Refund summary"
# section that describes the behaviour and names the commit it follows, so a
# reader does not have to compare two commits themselves.
def test_readme_has_a_refund_summary_section_naming_the_commit():
    body = _readme_section(README_REFUND_SUMMARY_HEADING)
    assert README_REFUND_SUMMARY_COMMIT in body, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must name the commit "
        f"the refund summary behaviour follows "
        f"({README_REFUND_SUMMARY_COMMIT})"
    )
    # The described behaviour is the one the command implements: succeeded
    # refunds grouped by UTC ISO week and currency, backed by the detailed
    # refunds-summary section the short section links to.
    unwrapped = body.replace("\n", "")
    assert "只统计 Stripe 状态为 `succeeded` 的退款" in unwrapped, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must state the "
        "succeeded-only refund scope"
    )
    assert "ISO 8601 周" in unwrapped, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must state the UTC ISO "
        "week grouping"
    )
    assert "币种" in unwrapped, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must state the "
        "per-currency rows"
    )
    assert "(#按周汇总退款refunds-summary)" in unwrapped, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must link to "
        f"{README_REFUNDS_SUMMARY_HEADING!r}"
    )
    assert "`refunds-summary`" in body, (
        f"the {README_REFUND_SUMMARY_HEADING!r} section must name the "
        "`refunds-summary` command"
    )


# Issue #257: the `test (20)` / `test (22)` base-branch checks only exist
# because the CI `test` job runs the repository entry point once per supported
# Node.js major version.  A missing matrix or a missing run step would leave
# `main` with no real test check at all.
CI_TEST_MATRIX = "node-version: [20, 22]"
CI_TEST_COMMAND = "python -m pytest -q"


def test_ci_test_job_runs_the_repository_pytest_command():
    """Issue #257: `test (20)` / `test (22)` must stay real pytest runs."""
    text = _read(WORKFLOW)
    assert CI_TEST_MATRIX in text, (
        "the CI test job must run once per Node.js major version, expected "
        f"{CI_TEST_MATRIX!r}"
    )
    assert CI_TEST_COMMAND in text, (
        "the CI test job must run the repository entry point, expected a step "
        f"with {CI_TEST_COMMAND!r}"
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


def test_readme_faq_section_answers_where_the_exported_files_go():
    """Issue #286: the first FAQ answer says where the exported files land."""
    body = _readme_section(README_FAQ_HEADING)
    entries = re.split(r"\n### ", body)[1:]
    assert entries, (
        f"the {README_FAQ_HEADING!r} section needs question/answer entries"
    )
    first = entries[0]
    assert first.startswith(README_FAQ_EXPORT_QUESTION), (
        f"the first {README_FAQ_HEADING!r} entry must be "
        f"{README_FAQ_EXPORT_QUESTION!r}, got {first.splitlines()[0]!r}"
    )
    # The answer states the directory the export command really writes to, so
    # the FAQ cannot drift away from the code's default.
    directory = stripe_payments.DEFAULT_OUTPUT_DIR
    assert f"`{directory}/`" in first, (
        f"the first {README_FAQ_HEADING!r} answer must name the default "
        f"export directory {directory + '/'!r}"
    )
    assert "--output-dir" in first, (
        f"the first {README_FAQ_HEADING!r} answer must say how to change the "
        "directory with --output-dir"
    )
    for category in ("payments", "refunds", "customers"):
        assert f"{category}-<日期>" in first, (
            f"the first {README_FAQ_HEADING!r} answer must name the exported "
            f"{category}-<日期> files"
        )


def test_docs_has_a_code_of_conduct_page():
    """Issue #375: docs/CODE_OF_CONDUCT.md opens with the required heading."""
    lines = _read(CODE_OF_CONDUCT).splitlines()
    assert lines[0] == CODE_OF_CONDUCT_HEADING, (
        f"docs/CODE_OF_CONDUCT.md must open with {CODE_OF_CONDUCT_HEADING!r}, "
        f"got {lines[0]!r}"
    )
    # A heading alone is not a code of conduct: the page needs a body that
    # tells the reader what behaviour is expected.
    assert any(line.strip() for line in lines[1:]), (
        "docs/CODE_OF_CONDUCT.md must have a body below the heading"
    )


def test_docs_has_a_support_page():
    """Issue #380: docs/SUPPORT.md opens with the required heading."""
    lines = _read(SUPPORT_PAGE).splitlines()
    assert lines[0] == SUPPORT_HEADING, (
        f"docs/SUPPORT.md must open with {SUPPORT_HEADING!r}, "
        f"got {lines[0]!r}"
    )
    # A heading alone does not help anyone: the page must say where to ask,
    # and security reports must not be sent to the public issue tracker.
    body = "\n".join(lines[1:])
    assert any(line.strip() for line in lines[1:]), (
        "docs/SUPPORT.md must have a body below the heading"
    )
    assert "SECURITY.md" in body, (
        "docs/SUPPORT.md must point security reports at SECURITY.md"
    )


def test_docs_has_a_glossary_page():
    """Issue #382: docs/GLOSSARY.md defines at least three README words."""
    lines = _read(GLOSSARY_PAGE).splitlines()
    assert lines[0] == GLOSSARY_HEADING, (
        f"docs/GLOSSARY.md must open with {GLOSSARY_HEADING!r}, "
        f"got {lines[0]!r}"
    )
    # Each term is a level-two heading, so the page really has one entry per
    # word instead of a heading plus prose only.
    terms = [
        line[len(GLOSSARY_TERM_PREFIX):].strip()
        for line in lines
        if line.startswith(GLOSSARY_TERM_PREFIX)
    ]
    assert len(terms) >= 3, (
        f"docs/GLOSSARY.md must define at least 3 terms, got {len(terms)}: "
        f"{terms}"
    )
    # The page explains words the README actually uses, so every entry must
    # be findable in the README instead of inventing its own vocabulary.
    readme = _read(README)
    for term in terms:
        assert term and term in readme, (
            f"docs/GLOSSARY.md term {term!r} must appear in README.md"
        )


def test_docs_has_a_contributor_faq_page():
    """Issue #386: docs/CONTRIBUTOR-FAQ.md answers three contributor questions."""
    lines = _read(CONTRIBUTOR_FAQ_PAGE).splitlines()
    assert lines[0] == CONTRIBUTOR_FAQ_HEADING, (
        f"docs/CONTRIBUTOR-FAQ.md must open with {CONTRIBUTOR_FAQ_HEADING!r}, "
        f"got {lines[0]!r}"
    )
    assert any(line.strip() for line in lines[1:]), (
        "docs/CONTRIBUTOR-FAQ.md must have a body below the heading"
    )
    # Each question is a level-two heading, and the page answers exactly three
    # of them, so a heading alone cannot pass for an answer.
    questions = [
        line[len(GLOSSARY_TERM_PREFIX):].strip()
        for line in lines
        if line.startswith(GLOSSARY_TERM_PREFIX)
    ]
    assert len(questions) == 3, (
        f"docs/CONTRIBUTOR-FAQ.md must ask 3 questions, got {len(questions)}: "
        f"{questions}"
    )
    for question in questions:
        assert question.endswith("？"), (
            f"docs/CONTRIBUTOR-FAQ.md entry {question!r} must be a question"
        )


def test_contributor_faq_answers_through_the_real_contribution_channel():
    """Issue #386: the FAQ repeats the repository's no-PR contribution rule."""
    body = _read(CONTRIBUTOR_FAQ_PAGE).replace("\n", "")
    contributing = _read(REPO_ROOT / "CONTRIBUTING.md").replace("\n", "")
    # CONTRIBUTING.md is the canonical rule, so the FAQ cannot promise a pull
    # request channel the repository does not accept.
    assert "不接受 pull request" in contributing, (
        "CONTRIBUTING.md must stay the canonical no-PR contribution rule"
    )
    assert "不接受 pull request" in body, (
        "docs/CONTRIBUTOR-FAQ.md must say the repository takes no pull request"
    )
    assert "通过 Issue 提出" in body, (
        "docs/CONTRIBUTOR-FAQ.md must point contributors at the Issue tracker"
    )
    assert "通过 Issue 提出" in contributing, (
        "CONTRIBUTING.md must stay the canonical Issue channel the FAQ repeats"
    )
    # Both templates are named by the path a contributor really opens, and the
    # files exist.
    for template in (ISSUE_TEMPLATE, FEATURE_REQUEST_TEMPLATE):
        assert template.is_file(), f"{template.relative_to(REPO_ROOT)} is missing"
        assert template.relative_to(REPO_ROOT).as_posix() in body, (
            "docs/CONTRIBUTOR-FAQ.md must name "
            f"{template.relative_to(REPO_ROOT).as_posix()!r}"
        )


def test_contributor_faq_shows_the_real_test_commands_and_repair():
    """Issue #386: the FAQ shows the commands CONTRIBUTING.md and CI run."""
    body = _read(CONTRIBUTOR_FAQ_PAGE)
    contributing = _read(REPO_ROOT / "CONTRIBUTING.md")
    assert CONTRIBUTOR_INSTALL_COMMAND in body, (
        f"docs/CONTRIBUTOR-FAQ.md must show {CONTRIBUTOR_INSTALL_COMMAND!r}"
    )
    assert CONTRIBUTOR_TEST_COMMAND in body, (
        f"docs/CONTRIBUTOR-FAQ.md must show {CONTRIBUTOR_TEST_COMMAND!r}"
    )
    # The documented commands are the contributor commands, so the FAQ cannot
    # drift away from the real test entry point.
    for command in (CONTRIBUTOR_INSTALL_COMMAND, CONTRIBUTOR_TEST_COMMAND):
        assert command in contributing, (
            f"CONTRIBUTING.md must document {command!r}"
        )
    assert CONTRIBUTOR_TEST_COMMAND in _read(WORKFLOW), (
        f"the CI Run tests step must run {CONTRIBUTOR_TEST_COMMAND!r}"
    )
    # The failure path and its repair are documented, so a first run that fails
    # on a missing dependency has an answer instead of a silent dead end.
    assert "No module named pytest" in body, (
        "docs/CONTRIBUTOR-FAQ.md must name the missing-pytest failure message"
    )


def test_contributor_faq_relative_links_resolve():
    """Issue #386: every link on the FAQ page leads to a file that exists."""
    text = _read(CONTRIBUTOR_FAQ_PAGE)
    targets = MARKDOWN_LINK_RE.findall(text)
    assert targets, "docs/CONTRIBUTOR-FAQ.md must link the pages it refers to"
    for target in targets:
        resolved = (CONTRIBUTOR_FAQ_PAGE.parent / target.strip()).resolve()
        assert resolved.is_file(), (
            f"docs/CONTRIBUTOR-FAQ.md links {target!r}, but that file is missing"
        )


# Issue #403: the two pull-request rules are a numbered list under `## Rules`.
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
CONTRIBUTING_RULES_HEADING = "## Rules"
CONTRIBUTING_RULES = (
    "Commit messages are written in English.",
    "Pull requests need a passing test run: run `python -m pytest` before you "
    "open a pull request and make sure the summary reports no `failed`.",
)


def test_contributing_presents_the_pull_request_rules_as_a_numbered_list():
    """Issue #403: the rules are a numbered list under a `## Rules` heading."""
    text = _read(CONTRIBUTING)
    block = "\n".join(
        [
            CONTRIBUTING_RULES_HEADING,
            "",
            f"1. {CONTRIBUTING_RULES[0]}",
            f"2. {CONTRIBUTING_RULES[1]}",
        ]
    )
    assert block in text, (
        "CONTRIBUTING.md must show the two pull-request rules as a 1./2. "
        f"numbered list under {CONTRIBUTING_RULES_HEADING!r}"
    )
    standalone = text.splitlines()
    for rule in CONTRIBUTING_RULES:
        assert rule not in standalone, (
            f"the rule {rule!r} must not stay a standalone paragraph"
        )


# Issue #414: CONTRIBUTING.md links the two Issue templates a contributor
# really opens, so the guide leads straight to the form to fill in.
CONTRIBUTING_ISSUE_TEMPLATES = (
    ".github/ISSUE_TEMPLATE/user-outcome.md",
    ".github/ISSUE_TEMPLATE/feature-request.md",
)


def test_contributing_links_the_issue_templates():
    """Issue #414: CONTRIBUTING.md links the two Issue templates."""
    text = _read(CONTRIBUTING)
    targets = [target.strip() for target in MARKDOWN_LINK_RE.findall(text)]
    for template in CONTRIBUTING_ISSUE_TEMPLATES:
        assert (REPO_ROOT / template).is_file(), f"{template} is missing"
        assert template in targets, (
            "CONTRIBUTING.md must link "
            f"{template!r}, the path a contributor really opens"
        )
    # Every relative link on the page leads to a file that exists, so the
    # new line cannot point at a template that was renamed or removed.
    for target in targets:
        resolved = (CONTRIBUTING.parent / target).resolve()
        assert resolved.is_file(), (
            f"CONTRIBUTING.md links {target!r}, but that file is missing"
        )


# Issue #411: the changelog opens with an empty "未发布" section that the next
# delivery can fill in, above the Keep a Changelog `[Unreleased]` section.
CHANGELOG_UNRELEASED_HEADING = "## 未发布"
CHANGELOG_UNRELEASED_PLACEHOLDER = "暂无"


def test_changelog_starts_with_an_empty_unreleased_section():
    """Issue #411: the first `## ` section is `## 未发布` holding `暂无`."""
    text = _read(CHANGELOG)
    sections = text.split("\n## ")
    assert len(sections) > 1, "CHANGELOG.md must have at least one `## ` section"
    first = sections[1]
    assert first.splitlines()[0] == CHANGELOG_UNRELEASED_HEADING[3:], (
        "CHANGELOG.md must start with a '## 未发布' section, got "
        f"{first.splitlines()[0]!r}"
    )
    body = first.split("\n## ", 1)[0]
    assert body.split("\n", 1)[1].strip() == CHANGELOG_UNRELEASED_PLACEHOLDER, (
        "the '## 未发布' section must hold exactly one line "
        f"{CHANGELOG_UNRELEASED_PLACEHOLDER!r}"
    )
    # The existing Keep a Changelog section keeps every recorded entry.
    assert "\n## [Unreleased]\n" in text, (
        "CHANGELOG.md must keep its existing '## [Unreleased]' section"
    )


# Issue #361: one short `## Usage` section shows how to run the repository's
# main script with a single example command, and that command really runs from
# the repository root.
README_USAGE_HEADING = "## Usage"
README_USAGE_SCRIPT = "stripe_payments"


def _readme_usage_commands() -> list:
    """Return the commands of the `## Usage` section's one fenced example."""
    body = _readme_section(README_USAGE_HEADING)
    assert body.count("```") == 2, (
        f"the {README_USAGE_HEADING!r} section must hold one fenced example "
        f"command, got {body.count('```') // 2} fenced blocks"
    )
    blocks = re.findall(r"```sh\n(.*?)```", body, re.DOTALL)
    assert len(blocks) == 1, (
        f"the {README_USAGE_HEADING!r} section must hold exactly one fenced "
        f"example command, got {len(blocks)}"
    )
    commands = [line.strip() for line in blocks[0].splitlines() if line.strip()]
    assert len(commands) == 1, (
        f"the {README_USAGE_HEADING!r} section must show exactly one example "
        f"command, got {commands!r}"
    )
    return commands


def test_readme_has_a_usage_section_with_one_example_command():
    """Issue #361: the Usage section runs the main script with one command."""
    command = _readme_usage_commands()[0]
    assert command.startswith(f"python -m {README_USAGE_SCRIPT} "), (
        f"the {README_USAGE_HEADING!r} example must run the main script as "
        f"`python -m {README_USAGE_SCRIPT} ...`, got {command!r}"
    )
    # Every flag of the example is defined by the real top-level parser, so
    # the documented command cannot drift away from the CLI.
    option_strings = {
        option
        for action in stripe_payments._parser()._actions
        for option in action.option_strings
    }
    flags = STRIPE_FLAG_RE.findall(command)
    assert flags, (
        f"the {README_USAGE_HEADING!r} example must pass a flag of the CLI, "
        "so it runs without a live Stripe key"
    )
    for flag in flags:
        assert flag in option_strings, (
            f"the {README_USAGE_HEADING!r} example passes {flag!r}, which the "
            f"top-level parser does not define ({sorted(option_strings)!r})"
        )


def test_readme_has_a_changelog_section_holding_the_c4_line():
    """Issue #455: the README keeps a `## Changelog` section."""
    body = _readme_section(README_CHANGELOG_HEADING)
    lines = [line for line in body.splitlines() if line.strip()]
    assert lines == [README_LAST_LINE], (
        f"the {README_CHANGELOG_HEADING!r} section must hold exactly the "
        f"{README_LAST_LINE!r} line, got {lines!r}"
    )
    # Issue #527 appends the FAQ section after the changelog, so the changelog
    # stays its own `## ` section right before the new one.
    text = _read(README)
    assert f"{README_CHANGELOG_HEADING}\n\n{README_LAST_LINE}\n\n" in text, (
        f"the {README_CHANGELOG_HEADING!r} section must keep the "
        f"{README_LAST_LINE!r} line"
    )


def test_readme_ends_with_the_issue_527_faq_section():
    """Issue #527: the README closes with a 「常见问题」 section from the mockup."""
    expected = "\n".join(
        (
            README_FAQ_HEADING,
            "",
            README_FAQ_PYTHON_QUESTION,
            "",
            README_FAQ_PYTHON_ANSWER,
            "",
            README_FAQ_OUTPUT_QUESTION,
            "",
            README_FAQ_OUTPUT_ANSWER,
        )
    )
    text = _read(README).rstrip("\n")
    assert text.endswith(f"\n{expected}"), (
        f"the README must end with the appended {README_FAQ_HEADING!r} section, "
        f"got {text[-len(expected):]!r}"
    )
    # The section is one `## ` block with exactly the two `Q：` questions and
    # their `A：` answers, so the reader sees the mockup's content unchanged.
    lines = [line for line in expected.splitlines() if line.strip()]
    tail = text.rsplit(f"\n{README_FAQ_HEADING}\n", 1)[-1]
    assert [line for line in tail.splitlines() if line.strip()] == lines[1:], (
        "the appended FAQ section must hold exactly the two question/answer "
        f"pairs, got {[line for line in tail.splitlines() if line.strip()]!r}"
    )


def test_readme_usage_example_command_runs_from_the_repository_root():
    """Issue #361: the documented example command exits 0 as printed."""
    command = _readme_usage_commands()[0]
    argv = command.split()
    assert argv[0] == "python", (
        f"the {README_USAGE_HEADING!r} example must start with `python`, "
        f"got {argv[0]!r}"
    )
    result = subprocess.run(
        [sys.executable, *argv[1:]],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"the {README_USAGE_HEADING!r} example {command!r} failed with exit "
        f"{result.returncode}:\n{result.stderr}"
    )
    # The example runs the main script, so a reader sees its real output.
    assert f"{README_USAGE_SCRIPT} {stripe_payments.VERSION}" in result.stdout, (
        f"the {README_USAGE_HEADING!r} example must print the main script's "
        f"real output, got:\n{result.stdout}"
    )

# Issue #506: the root CHECKOUT.md records the checkout page's error banner
# (text, colour and the prototype class) and the orders that were refunded, so
# a reader learns both facts without opening the prototype or the order table.
CHECKOUT_PAGE = REPO_ROOT / "CHECKOUT.md"
CHECKOUT_BANNER_TEXT = "Payment failed: invalid card"
# The screenshot shows a dark red bar; the page describes the colour in words
# instead of a hex code.
CHECKOUT_BANNER_COLOURS = ("深红色", "暗红")
CHECKOUT_BANNER_CLASS = "`error-banner`"
CHECKOUT_REFUND_HEADING = "## 退款订单"
# The documented order table holds exactly one order whose `refund` column is
# greater than 0, so the refunded-order list names only that order id.
CHECKOUT_REFUNDED_ORDER_IDS = ["1002"]
CHECKOUT_ORDER_ID_RE = re.compile(r"`(\d{4})`")


def _checkout_paragraphs() -> list:
    """Return the non-empty paragraphs of CHECKOUT.md."""
    return [
        block.strip()
        for block in _read(CHECKOUT_PAGE).split("\n\n")
        if block.strip()
    ]


def test_checkout_page_states_the_error_banner_text_colour_and_class():
    """Issue #506: one paragraph carries all three error-banner facts."""
    paragraphs = _checkout_paragraphs()
    expected = (CHECKOUT_BANNER_TEXT, CHECKOUT_BANNER_CLASS, *CHECKOUT_BANNER_COLOURS)
    matches = [
        paragraph
        for paragraph in paragraphs
        if all(fact in paragraph for fact in expected)
    ]
    assert matches, (
        "CHECKOUT.md needs one paragraph naming the banner text "
        f"{CHECKOUT_BANNER_TEXT!r}, the colour 深红色（暗红） and the prototype "
        f"class {CHECKOUT_BANNER_CLASS!r}; got paragraphs: {paragraphs!r}"
    )


def test_checkout_page_lists_only_the_refunded_order():
    """Issue #506: the refunded-order list holds only the refunded order."""
    text = _read(CHECKOUT_PAGE)
    assert f"\n{CHECKOUT_REFUND_HEADING}\n" in text, (
        f"CHECKOUT.md needs a {CHECKOUT_REFUND_HEADING!r} section"
    )
    body = text.split(f"\n{CHECKOUT_REFUND_HEADING}\n", 1)[1]
    bullets = [
        line for line in body.splitlines() if line.lstrip().startswith("- ")
    ]
    assert bullets, (
        f"the {CHECKOUT_REFUND_HEADING!r} section must list the refunded orders"
    )
    order_ids = CHECKOUT_ORDER_ID_RE.findall("\n".join(bullets))
    assert order_ids == CHECKOUT_REFUNDED_ORDER_IDS, (
        "the refunded-order list must name exactly the orders whose `refund` "
        f"column is greater than 0 ({CHECKOUT_REFUNDED_ORDER_IDS}), "
        f"got {order_ids!r}"
    )


# Issue #509: the root BANNER.md records the checkout error banner's colour, so
# a reader picks the right colour without opening the screenshot.
BANNER_PAGE = REPO_ROOT / "BANNER.md"
BANNER_COLOUR_NAME = "深红色"
BANNER_COLOUR_HEX = "#B01C1B"
# The screenshot carries no design token, so the page marks the colour value as
# an approximation a design file can replace.
BANNER_APPROXIMATE_NOTE = "近似值"


def test_banner_page_states_the_error_banner_colour():
    """Issue #509: BANNER.md names the dark red colour and its hex value."""
    paragraphs = [
        block.strip()
        for block in _read(BANNER_PAGE).split("\n\n")
        if block.strip()
    ]
    expected = (BANNER_COLOUR_NAME, BANNER_COLOUR_HEX)
    matches = [
        paragraph
        for paragraph in paragraphs
        if all(fact in paragraph for fact in expected)
    ]
    assert matches, (
        "BANNER.md needs one paragraph naming the checkout error banner colour "
        f"{BANNER_COLOUR_NAME!r} and its hex value {BANNER_COLOUR_HEX!r}; "
        f"got paragraphs: {paragraphs!r}"
    )
    assert BANNER_APPROXIMATE_NOTE in _read(BANNER_PAGE), (
        f"BANNER.md must mark the hex value {BANNER_COLOUR_HEX!r} as an "
        f"{BANNER_APPROXIMATE_NOTE!r}"
    )


# Issue #510: the root REFUNDS.md lists the order numbers that were refunded,
# so a reader sees the refunded orders without opening the order table.  The
# order table holds exactly one order whose `refund` column is greater than 0
# (`1002`); the order whose refund is 0 must not be listed.
REFUNDS_PAGE = REPO_ROOT / "REFUNDS.md"
REFUNDS_HEADING = "# 退款订单"
REFUNDED_ORDER_ID = "1002"
UNREFUNDED_ORDER_ID = "1001"


def test_refunds_page_lists_the_refunded_orders_only():
    """Issue #510: REFUNDS.md exists and lists only orders with refund > 0."""
    text = _read(REFUNDS_PAGE)
    assert REFUNDS_HEADING in text, (
        f"REFUNDS.md needs the {REFUNDS_HEADING!r} heading, got:\n{text}"
    )
    assert REFUNDED_ORDER_ID in text, (
        "REFUNDS.md must list the refunded order "
        f"{REFUNDED_ORDER_ID} (its refund column is greater than 0)"
    )
    assert UNREFUNDED_ORDER_ID not in text, (
        "REFUNDS.md must not list the order "
        f"{UNREFUNDED_ORDER_ID}: its refund column is 0"
    )


# Issue #515: the root GATE861.txt holds the retry value of the attached
# settings.log, and nothing else: no key, no comment and no second setting.
GATE861_PAGE = REPO_ROOT / "GATE861.txt"
GATE861_RETRY_VALUE = "7"


def test_gate861_file_holds_only_the_retry_value():
    """Issue #515: GATE861.txt is one line with the retry value `7`."""
    assert _read(GATE861_PAGE) == f"{GATE861_RETRY_VALUE}\n", (
        f"GATE861.txt must hold only the retry value {GATE861_RETRY_VALUE!r} "
        f"followed by one newline, got {_read(GATE861_PAGE)!r}"
    )


# Issue #517: the root GATE870.txt holds the single word `ok` and nothing
# else, so a reader who opens it sees one line without extra text, a second
# line or a blank line.
GATE870_PAGE = REPO_ROOT / "GATE870.txt"
GATE870_CONTENT = "ok"


def test_gate870_file_holds_only_ok():
    """Issue #517: GATE870.txt is exactly one line `ok` plus a newline."""
    content = _read(GATE870_PAGE)
    assert content == f"{GATE870_CONTENT}\n", (
        f"GATE870.txt must hold only {GATE870_CONTENT!r} followed by one "
        f"newline, got {content!r}"
    )


# Issue #516: the root GATE862.txt holds the button colour of the attached
# spec.html on line 1 and one Chinese sentence describing the main colour of
# the attached blue.png on line 2.  It carries no HTML: no tag and no script.
GATE862_PAGE = REPO_ROOT / "GATE862.txt"
GATE862_BUTTON_COLOUR = "#1F7A3A"
GATE862_BLUE_DESCRIPTION = "附图 blue.png 的主色是一种中等饱和度的蓝色。"


# Issue #522: the receipt page follows the 「金额列」 rules of the attached
# spec.html — the 金额 header, every row's amount (the 合计 row included) is
# right aligned, amounts use tabular figures so the decimal points of $29.00,
# $6.00 and -$29.00 stack, and a negative (refund) amount is red #DC2626.
RECEIPT_PAGE = REPO_ROOT / "docs" / "receipt.html"
RECEIPT_AMOUNT_HEADING = "金额"
RECEIPT_REFUND_TEXT = "-$29.00"
RECEIPT_AMOUNT_ALIGN = "right"
RECEIPT_TABULAR_NUMERALS = "tabular-nums"
RECEIPT_REFUND_RED = "#dc2626"
# The selector shapes that can match a table cell here: `tag`, `.class`,
# `tag.class` (any number of classes) and `*`, space separated for a
# descendant selector.  Any other shape — a pseudo-class such as
# `.btn:hover`, an ID, an attribute selector — does not style a cell in the
# page's static rendering, so it is skipped instead of asserted over.
STYLE_BLOCK_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL)
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CELL_SELECTOR_RE = re.compile(r"^(\*|[a-z][a-z0-9]*)?((?:\.[A-Za-z0-9_-]+)*)$")


class _TableCells(HTMLParser):
    """Collect the page's table cells with the ancestors each one sits in."""

    # Only the elements that can wrap a table cell need an open scope.
    SCOPE_TAGS = ("table", "thead", "tbody", "tfoot", "tr", "td", "th")

    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None
        self._text = []
        self._open = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell = dict(attrs)
            self._text = []
        if tag in self.SCOPE_TAGS:
            self._open.append((tag, dict(attrs)))

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None:
            ancestors = tuple(reversed(self._open[:-1]))
            self._row.append(
                (tag, self._cell, "".join(self._text).strip(), ancestors)
            )
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        while self._open and self._open[-1][0] != tag:
            self._open.pop()
        if self._open:
            self._open.pop()

    def handle_data(self, data):
        if self._cell is not None:
            self._text.append(data)


def _table_rows(html_text):
    """Return the page's table rows, one list of cells per row."""
    parser = _TableCells()
    parser.feed(html_text)
    parser.close()
    return parser.rows


def _style_rules(html_text):
    """Return the page's `(selector, declarations)` rules in source order."""
    css = "".join(STYLE_BLOCK_RE.findall(html_text))
    css = CSS_COMMENT_RE.sub("", css)
    rules = []
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = {}
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            name, value = declaration.split(":", 1)
            declarations[name.strip().lower()] = value.strip()
        for selector in selectors.split(","):
            rules.append((selector.strip(), declarations))
    return rules


def _compound_matches(compound, tag, attributes):
    """Match one compound selector: True, False, or None when unsupported."""
    match = CELL_SELECTOR_RE.match(compound)
    if match is None:
        return None
    compound_tag, classes = match.groups()
    compound_tag = None if compound_tag == "*" else compound_tag
    wanted = {name for name in classes.split(".") if name}
    cell_classes = set(attributes.get("class", "").split())
    return compound_tag in (None, tag) and wanted <= cell_classes


def _selector_matches(selector, tag, attributes, ancestors):
    """Match a selector against a cell and its ancestors, innermost first.

    A child combinator is read as a descendant one: this table nests its cells
    directly, so both forms point at the same cells.
    """
    compounds = selector.replace(">", " ").split()
    inner = _compound_matches(compounds[-1], tag, attributes)
    if inner is not True:
        return inner
    ancestors = list(ancestors)
    for compound in reversed(compounds[:-1]):
        matched_at = None
        for index, (ancestor_tag, ancestor_attributes) in enumerate(ancestors):
            matched = _compound_matches(compound, ancestor_tag, ancestor_attributes)
            if matched is None:
                return None
            if matched:
                matched_at = index
                break
        if matched_at is None:
            return False
        ancestors = ancestors[matched_at + 1:]
    return True


def _declared(html_text, tag, attributes, ancestors=()):
    """Return the declarations the page's stylesheet applies to a cell.

    The stylesheet of this page is flat and its rules for a cell do not
    overlap, so a later matching rule wins.  Selectors this helper does not
    understand are skipped, never counted as a match.
    """
    applied = {}
    for selector, declarations in _style_rules(html_text):
        if _selector_matches(selector, tag, attributes, ancestors) is True:
            applied.update(declarations)
    return applied


def _receipt_amount_cells():
    """Return the 金额 cells of docs/receipt.html: the header, rows, total."""
    rows = _table_rows(_read(RECEIPT_PAGE))
    assert rows, "docs/receipt.html must hold the receipt table"
    header, body = rows[0], rows[1:]
    assert header[-1][2] == RECEIPT_AMOUNT_HEADING, (
        f"the last column header must be {RECEIPT_AMOUNT_HEADING!r}, "
        f"got {header[-1][2]!r}"
    )
    assert body, "the receipt table must hold the amount rows"
    return [header[-1]] + [row[-1] for row in body]


def test_receipt_amount_cells_are_right_aligned_with_tabular_numerals():
    """Issue #522: every 金额 cell ends on one right edge, in tabular figures."""
    html_text = _read(RECEIPT_PAGE)
    for tag, attributes, text, ancestors in _receipt_amount_cells():
        declared = _declared(html_text, tag, attributes, ancestors)
        assert declared.get("text-align") == RECEIPT_AMOUNT_ALIGN, (
            f"the amount cell {text!r} must be right aligned, "
            f"got text-align {declared.get('text-align')!r}"
        )
        assert declared.get("font-variant-numeric") == RECEIPT_TABULAR_NUMERALS, (
            f"the amount cell {text!r} must use tabular figures so its decimal "
            f"point stacks with the others, got font-variant-numeric "
            f"{declared.get('font-variant-numeric')!r}"
        )
    # The Issue restyles the 金额 column only: 项目 and 数量 keep the page's
    # left alignment, so the amount rules must not spill onto them.
    for row in _table_rows(html_text):
        for tag, attributes, text, ancestors in row[:-1]:
            declared = _declared(html_text, tag, attributes, ancestors)
            assert declared.get("text-align") == "left", (
                f"the non-amount cell {text!r} must keep the page's left "
                f"alignment, got text-align {declared.get('text-align')!r}"
            )


def test_receipt_refund_amount_is_red_and_the_other_amounts_are_not():
    """Issue #522: -$29.00 is red #DC2626, every other amount keeps its colour."""
    html_text = _read(RECEIPT_PAGE)
    cells = _receipt_amount_cells()
    refunds = [cell for cell in cells if cell[2] == RECEIPT_REFUND_TEXT]
    assert len(refunds) == 1, (
        f"docs/receipt.html must hold one refund amount "
        f"{RECEIPT_REFUND_TEXT!r}, got {len(refunds)}"
    )
    for tag, attributes, text, ancestors in cells:
        colour = (
            _declared(html_text, tag, attributes, ancestors)
            .get("color", "")
            .lower()
        )
        if text == RECEIPT_REFUND_TEXT:
            assert colour == RECEIPT_REFUND_RED, (
                f"the refund amount {text!r} must be {RECEIPT_REFUND_RED}, "
                f"got {colour or 'no declared colour'!r}"
            )
        else:
            assert colour != RECEIPT_REFUND_RED, (
                f"the positive amount {text!r} must keep the default colour, "
                f"got the refund red {colour!r}"
            )


def test_gate862_file_holds_the_button_colour_and_blue_png_description():
    """Issue #516: GATE862.txt is the button colour plus one blue.png line."""
    text = _read(GATE862_PAGE)
    lines = text.splitlines()
    assert len(lines) == 2, (
        f"GATE862.txt must hold exactly two lines, got {lines!r}"
    )
    assert lines[0] == GATE862_BUTTON_COLOUR, (
        f"GATE862.txt line 1 must be the spec.html button colour "
        f"{GATE862_BUTTON_COLOUR!r}, got {lines[0]!r}"
    )
    assert lines[1] == GATE862_BLUE_DESCRIPTION, (
        f"GATE862.txt line 2 must describe blue.png as "
        f"{GATE862_BLUE_DESCRIPTION!r}, got {lines[1]!r}"
    )
    # The file is plain text: no HTML markup and no script of spec.html leaks in.
    assert "<" not in text and ">" not in text, (
        f"GATE862.txt must not carry HTML markup, got {text!r}"
    )
    assert "script" not in text.lower(), (
        f"GATE862.txt must not carry the spec.html script, got {text!r}"
    )


# Issue #521: the receipt page's 「下载 PDF」 button is a clickable primary button
# — #2563EB with white text, #1D4ED8 on hover — instead of the #9CA3AF grey the
# receipt page (and its spec) reserves for a button that cannot be clicked.
RECEIPT_PAGE = REPO_ROOT / "docs" / "receipt.html"
RECEIPT_BUTTON_LABEL = "下载 PDF"
RECEIPT_PRIMARY_BACKGROUND = "#2563eb"
RECEIPT_PRIMARY_HOVER_BACKGROUND = "#1d4ed8"
RECEIPT_DISABLED_BACKGROUND = "#9ca3af"
RECEIPT_WHITE_TEXT = ("#fff", "#ffffff")


def _receipt_rule(selector: str) -> dict:
    """Return the declarations of one CSS rule of the receipt page's style."""
    text = _read(RECEIPT_PAGE)
    match = re.search(
        r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", text
    )
    assert match, (
        f"docs/receipt.html must declare a {selector!r} rule, got:\n"
        f"{text}"
    )
    declarations = {}
    for declaration in match.group(1).split(";"):
        if ":" in declaration:
            prop, value = declaration.split(":", 1)
            declarations[prop.strip().lower()] = value.strip().lower()
    return declarations


def _receipt_background(declarations: dict, selector: str) -> str:
    """The background colour a rule declares, whether as shorthand or longhand."""
    value = declarations.get(
        "background-color", declarations.get("background", "")
    )
    assert value, (
        f"the docs/receipt.html {selector!r} rule must declare a background "
        f"colour, got {declarations!r}"
    )
    return value


def test_receipt_download_button_uses_the_primary_button_colour():
    """Issue #521: the button is #2563EB with white text, never the grey."""
    rule = _receipt_rule(".btn")
    background = _receipt_background(rule, ".btn")
    assert background == RECEIPT_PRIMARY_BACKGROUND, (
        f"the 「{RECEIPT_BUTTON_LABEL}」 button must use the primary "
        f"background {RECEIPT_PRIMARY_BACKGROUND} (#2563EB), got {background!r}"
    )
    assert RECEIPT_DISABLED_BACKGROUND not in background, (
        "the 「" + RECEIPT_BUTTON_LABEL + "」 button is clickable, so it must "
        f"not use the unavailable-button grey {RECEIPT_DISABLED_BACKGROUND}"
    )
    text_colour = rule.get("color", "")
    assert text_colour in RECEIPT_WHITE_TEXT, (
        f"the 「{RECEIPT_BUTTON_LABEL}」 button must keep white text "
        f"({RECEIPT_WHITE_TEXT[0]}), got {text_colour!r}"
    )
    # The styled class really is the button the receipt page renders, and the
    # button keeps its existing `href="#"` behaviour.
    page = _read(RECEIPT_PAGE)
    assert f'class="btn" href="#">{RECEIPT_BUTTON_LABEL}</a>' in page, (
        f"docs/receipt.html must keep rendering the class=\"btn\" anchor "
        f"labelled {RECEIPT_BUTTON_LABEL!r} with href=\"#\""
    )


def test_receipt_download_button_darkens_on_hover():
    """Issue #521: hovering the button changes its background to #1D4ED8."""
    hover = _receipt_rule(".btn:hover")
    background = _receipt_background(hover, ".btn:hover")
    assert background == RECEIPT_PRIMARY_HOVER_BACKGROUND, (
        f"the 「{RECEIPT_BUTTON_LABEL}」 button must turn "
        f"{RECEIPT_PRIMARY_HOVER_BACKGROUND} (#1D4ED8) on hover, got "
        f"{background!r}"
    )


# Issue #525: the repository root carries a VERSION file whose entire content is
# the single line `0.1.0`, so a person or script reading it gets the version
# string instead of "no such file".
VERSION_FILE = REPO_ROOT / "VERSION"
VERSION_FILE_CONTENT = "0.1.0\n"


def test_version_file_holds_the_repository_version():
    """Issue #525: VERSION exists at the root and is exactly one line, 0.1.0."""
    assert VERSION_FILE.is_file(), (
        "VERSION must exist at the repository root (repository-relative VERSION)"
    )
    text = VERSION_FILE.read_text(encoding="utf-8")
    assert text == VERSION_FILE_CONTENT, (
        "VERSION must contain exactly the single line '0.1.0' "
        f"(one trailing newline), got {text!r}"
    )


# Issue #534: the repository root carries BASE0877C.txt whose entire content is
# the single line `ok`, so a reader who opens it sees one line without extra
# text, a second line or a blank line.
BASE0877C_FILE = REPO_ROOT / "BASE0877C.txt"
BASE0877C_CONTENT = "ok"


def test_base0877c_file_holds_only_ok():
    """Issue #534: BASE0877C.txt exists at the root and is exactly one line, ok."""
    assert BASE0877C_FILE.is_file(), (
        "BASE0877C.txt must exist at the repository root"
    )
    text = BASE0877C_FILE.read_text(encoding="utf-8")
    assert text == f"{BASE0877C_CONTENT}\n", (
        f"BASE0877C.txt must hold only {BASE0877C_CONTENT!r} followed by one "
        f"newline, got {text!r}"
    )
