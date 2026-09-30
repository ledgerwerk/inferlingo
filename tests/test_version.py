import re
import subprocess
import sys
from pathlib import Path

import inferlingo


def test_version_is_available_in_source_checkout():
    assert isinstance(inferlingo.__version__, str)
    assert inferlingo.__version__


def test_package_cli_and_release_docs_agree():
    root = Path(__file__).resolve().parents[1]
    development = (root / "docs/development.md").read_text(encoding="utf-8")
    changelog = (root / "docs/changelog.md").read_text(encoding="utf-8")

    planned_match = re.search(r"planned next release is `v(\d+\.\d+\.\d+)`", development)
    assert planned_match is not None
    planned_version = planned_match.group(1)

    package_match = re.fullmatch(r"(\d+\.\d+\.\d+)(?:\.dev\d+)?", inferlingo.__version__)
    assert package_match is not None
    assert package_match.group(1) == planned_version

    cli = subprocess.run(
        [sys.executable, "-m", "inferlingo", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert cli.stdout.strip() == inferlingo.__version__

    headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\] - (.+)$", changelog, re.MULTILINE)
    assert headings
    changelog_version, changelog_state = headings[0]
    if changelog_version == planned_version:
        assert changelog_state == "Unreleased"
    else:
        assert tuple(map(int, changelog_version.split("."))) < tuple(map(int, planned_version.split(".")))
        assert changelog_state != "Unreleased"
