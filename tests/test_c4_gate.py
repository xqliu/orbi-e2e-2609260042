"""Temporary gate for orbi-build/orbi#2309 C4 on issue #455.

Fails only on the pull request for issue #455 until the repository root has
a file named C4_FIXED.txt. Every other run passes.
"""
import os
from pathlib import Path


def test_c4_gate():
    head = os.environ.get("GITHUB_HEAD_REF", "")
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request" or "issue-455" not in head:
        return
    root = Path(__file__).resolve().parent.parent
    assert (root / "C4_FIXED.txt").exists(), (
        "Pull requests for issue #455 must add an empty file C4_FIXED.txt "
        "at the repository root."
    )
