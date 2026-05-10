"""Report template contract metadata used by template tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = ROOT_DIR / "templates"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


@dataclass(frozen=True, slots=True)
class ReportContract:
    """Built-in report template fixture/snapshot contract."""

    name: str
    fixture: str | None = None
    data_format: str = "json"
    render_mode: str = "markdown"
    surfaces: tuple[str, ...] = ("github-pr-comment", "github-step-summary")
    amp_schema: str | None = None

    @property
    def fixture_name(self) -> str:
        return self.fixture or self.name

    @property
    def template_path(self) -> Path:
        return TEMPLATES_DIR / f"{self.name}-report.md"

    @property
    def fixture_path(self) -> Path:
        return FIXTURES_DIR / f"{self.fixture_name}.json"

    @property
    def snapshot_path(self) -> Path:
        return SNAPSHOTS_DIR / f"{self.name}-report.md"


REPORT_CONTRACTS = [
    ReportContract("pytest", data_format="junit-xml"),
    ReportContract("coverage", data_format="json|lcov"),
    ReportContract("ruff"),
    ReportContract("ty", data_format="junit-xml"),
    ReportContract("jest"),
    ReportContract("gotest", data_format="junit-xml"),
    ReportContract("sarif"),
    ReportContract("code-review", amp_schema="code-review"),
    ReportContract("pr-summary", amp_schema="pr-summary"),
    ReportContract("deploy-preview", amp_schema="deploy-preview"),
    ReportContract("dependency-review", amp_schema="dependency-review"),
    ReportContract("security-scan", amp_schema="security-scan"),
    ReportContract("copilot-instructions"),
    ReportContract(
        "release-notes",
        fixture="release-notes",
        data_format="github-prs",
        surfaces=("github-release", "github-step-summary"),
        amp_schema="release-notes",
    ),
    ReportContract(
        "release-notes-compact",
        fixture="release-notes",
        data_format="github-prs",
        surfaces=("github-pr-comment",),
        amp_schema="release-notes",
    ),
    ReportContract(
        "release-notes-detailed",
        fixture="release-notes",
        data_format="github-prs",
        surfaces=("github-release", "github-step-summary"),
        amp_schema="release-notes",
    ),
    ReportContract(
        "release-notes-terminal",
        fixture="release-notes",
        data_format="github-prs",
        render_mode="terminal",
        surfaces=("terminal",),
        amp_schema="release-notes",
    ),
]
