"""Focused readability contracts for built-in report templates."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from kida import FileSystemLoader
from kida.markdown import markdown_env
from kida.terminal import terminal_env

from .report_contracts import REPORT_CONTRACTS, ROOT_DIR, TEMPLATES_DIR, ReportContract


@dataclass(frozen=True, slots=True)
class ReadabilityContract:
    name: str
    first_visible_line: str
    required_fragments: tuple[str, ...]


READABILITY_CONTRACTS = [
    ReadabilityContract(
        "pytest", "## :x: Test Results", ("### Failed Tests", "<details>", "**Message:**")
    ),
    ReadabilityContract(
        "coverage", "## Coverage Report", (":warning: **73.5%**", "| File | Coverage |")
    ),
    ReadabilityContract("ruff", "## :x: Ruff Report", ("### E501 (2)", "`src/app.py:42`")),
    ReadabilityContract("ty", "## :x: Type Check Results", ("### Errors", "<details>")),
    ReadabilityContract("jest", "## :x: Test Results", ("### Failed Tests", "### Pending Tests")),
    ReadabilityContract(
        "gotest", "## :x: Go Test Results", ("### Failed Tests", "### Skipped Tests")
    ),
    ReadabilityContract("sarif", "## :x: semgrep Report", ("| Level | Count |", "### Errors (1)")),
    ReadabilityContract(
        "code-review",
        "## Claude Code Review",
        (":warning: **3** findings", "- [ ] :warning:", "<strong>Files reviewed</strong>"),
    ),
    ReadabilityContract(
        "pr-summary",
        "## Add Agent Message Protocol (AMP) schemas and agentic templates",
        ("### What changed", "### Risk areas", "### Test coverage"),
    ),
    ReadabilityContract(
        "deploy-preview",
        "## :white_check_mark: Deploy Preview",
        ("### Bundle size", "### Performance", "[:page_facing_up: Build logs]"),
    ),
    ReadabilityContract(
        "dependency-review",
        "## Dependency Review",
        ("> [!CAUTION]", "- [ ] :x:", "### License concerns"),
    ),
    ReadabilityContract(
        "security-scan",
        "## Semgrep Results",
        (":x: **3** findings", "- [ ] :x:", "### By category"),
    ),
    ReadabilityContract(
        "copilot-instructions",
        "# Copilot Instructions",
        (
            "### Severity levels",
            "Return a single JSON code block",
            "conforming to the Agent Message Protocol",
        ),
    ),
    ReadabilityContract(
        "release-notes",
        "## 0.4.0 (2026-04-07)",
        ("### Highlights", "### New Features", "### New Contributors"),
    ),
    ReadabilityContract(
        "release-notes-compact",
        "## 0.4.0 (2026-04-07)",
        ("+420 / -85 across 15 files", "[0.3.3...0.4.0]"),
    ),
    ReadabilityContract(
        "release-notes-detailed",
        "# 0.4.0 — 2026-04-07",
        ("| Stat | Value |", "## Highlights", "## Bug Fixes"),
    ),
    ReadabilityContract(
        "release-notes-terminal",
        "What's New",
        ("[PASS] New template engine", "Contributors: @lbliii"),
    ),
]


def _contract_by_name(name: str) -> ReportContract:
    for contract in REPORT_CONTRACTS:
        if contract.name == name:
            return contract
    raise AssertionError(f"missing report contract for {name}")


def _render_report(contract: ReportContract) -> str:
    context = json.loads(contract.fixture_path.read_text(encoding="utf-8"))
    if contract.render_mode == "terminal":
        env = terminal_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    else:
        env = markdown_env(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    return env.get_template(contract.template_path.name).render(**context)


@pytest.mark.parametrize("readability", READABILITY_CONTRACTS, ids=lambda contract: contract.name)
def test_report_readability_contract(readability: ReadabilityContract):
    """Reports lead with status and keep action-oriented sections visible."""
    output = _render_report(_contract_by_name(readability.name))
    first_visible_line = next(line for line in output.splitlines() if line.strip())

    assert first_visible_line == readability.first_visible_line
    for fragment in readability.required_fragments:
        assert fragment in output


def test_github_action_pr_comment_marker_contract():
    """PR comment deduplication keeps using the stable kida-report marker."""
    action = (ROOT_DIR / "action.yml").read_text(encoding="utf-8")

    assert 'MARKER="<!-- kida-report: ${HEADER} -->"' in action
    assert 'HEADER="${TEMPLATE%-report}"' in action
