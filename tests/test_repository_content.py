"""Content checks for this repository's only artifacts.

The repository ships no application code: its deliverables are the README
and the GitHub Issue templates.  The `CI` workflow runs this suite so every
delivery pull request and every commit on `main` carries a real test result
instead of an empty check-run gate (Orbi's pre-release gate reads the check
runs of the frozen base commit).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "user-outcome.md"

# GitHub shows a markdown issue template by the `name`/`about` fields of
# its YAML front matter; the body sections are the ones the template
# itself promises to the author.
ISSUE_TEMPLATE_FRONT_MATTER_KEYS = ("name", "about")
ISSUE_TEMPLATE_SECTIONS = (
    "## User outcome",
    "## Preconditions",
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
