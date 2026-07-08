"""Collect typed release-note data for Kida's composite GitHub Action.

The module uses only the standard library. External commands are routed through
``CommandRunner`` so unit tests can exercise the complete collector offline.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class CollectorError(RuntimeError):
    """A diagnosable release-note collection failure."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Captured result from one external command."""

    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    """Injectable external-command boundary."""

    def __call__(self, args: Sequence[str]) -> CommandResult: ...


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    """Inputs needed to collect one release comparison."""

    repository: str
    head_ref: str
    base_ref: str = ""
    repository_root: Path = Path()


class IssueSummary(TypedDict):
    number: int
    title: str


class PullRequestOutput(TypedDict):
    number: int
    title: str
    author: str
    labels: list[str]
    body: str
    body_excerpt: str
    release_note: str
    linked_issues: list[IssueSummary]
    dependency_updates: list[dict[str, str]]


class DirectCommit(TypedDict):
    sha: str
    message: str
    author: str


class DiffStats(TypedDict):
    files_changed: int
    insertions: int
    deletions: int
    new_files: list[str]


class ReleaseData(TypedDict):
    version: str
    previous_version: str
    release_date: str
    repository: str
    pull_requests: list[PullRequestOutput]
    contributors: list[str]
    new_contributors: list[str]
    compare_url: str
    diff_stats: DiffStats
    direct_commits: list[DirectCommit]
    benchmarks: dict[str, object]


@dataclass(frozen=True, slots=True)
class PullRequestRecord:
    """Normalized GitHub PR data used during collection."""

    number: int
    title: str
    author: str
    labels: tuple[str, ...]
    merged_at: datetime
    body: str
    closing_issues: tuple[IssueSummary, ...]
    merge_oid: str


_GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $base: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 100
      after: $after
      states: MERGED
      baseRefName: $base
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        mergedAt
        body
        author { login }
        labels(first: 100) { nodes { name } }
        closingIssuesReferences(first: 100) { nodes { number title } }
        mergeCommit { oid }
      }
    }
  }
}
""".strip()

_RELEASE_NOTE_RE = re.compile(r"<!--\s*release-note:\s*(.+?)\s*-->")
_CLOSING_ISSUE_RE = re.compile(
    r"(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#(\d+)",
    re.IGNORECASE,
)
_DEPENDABOT_AUTHORS = frozenset({"dependabot[bot]", "renovate[bot]", "dependabot", "renovate"})
_BUMP_RE = re.compile(r"[Bb]ump\s+(\S+)\s+from\s+(\S+)\s+to\s+(\S+)")
_RENOVATE_RE = re.compile(r"[Uu]pdate\s+(\S+)\s+to\s+v?(\S+)")
_VERSION_TAG_RE = re.compile(r"^v\d")


def subprocess_runner(args: Sequence[str]) -> CommandResult:
    """Run one command without a shell and capture its output."""
    completed = subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _format_command(args: Sequence[str]) -> str:
    return " ".join(args[:3])


def _require_success(result: CommandResult, args: Sequence[str]) -> str:
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no command output"
        raise CollectorError(f"{_format_command(args)} failed: {detail}")
    return result.stdout


def _json_command(runner: CommandRunner, args: Sequence[str]) -> dict[str, Any]:
    raw = _require_success(runner(args), args)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CollectorError(f"{_format_command(args)} returned malformed JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise CollectorError(f"{_format_command(args)} returned a non-object JSON payload")
    return payload


def _parse_iso(value: object, *, context: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CollectorError(f"{context} is missing an ISO-8601 timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise CollectorError(f"{context} has invalid ISO-8601 timestamp {value!r}") from exc


def _default_branch(repository: str, runner: CommandRunner) -> str:
    args = ("gh", "repo", "view", repository, "--json", "defaultBranchRef")
    payload = _json_command(runner, args)
    branch = payload.get("defaultBranchRef")
    if not isinstance(branch, dict) or not isinstance(branch.get("name"), str):
        raise CollectorError("GitHub repository response is missing defaultBranchRef.name")
    name = branch["name"].strip()
    if not name:
        raise CollectorError("GitHub repository response contains an empty default branch")
    return name


def _git_text(runner: CommandRunner, *args: str) -> str:
    command = ("git", *args)
    return _require_success(runner(command), command).strip()


def _git_date(ref: str, runner: CommandRunner) -> datetime:
    value = _git_text(runner, "log", "-1", "--format=%aI", ref)
    return _parse_iso(value, context=f"git ref {ref!r}")


def _resolve_base_ref(
    config: CollectorConfig,
    runner: CommandRunner,
    warn: Callable[[str], None],
) -> str:
    if config.base_ref:
        return config.base_ref

    tags = _git_text(
        runner,
        "tag",
        f"--merged={config.head_ref}",
        "--sort=-version:refname",
    ).splitlines()
    candidates = [tag for tag in tags if _VERSION_TAG_RE.match(tag) and tag != config.head_ref]
    if candidates:
        return candidates[0]

    warn("Could not auto-detect a previous version tag; using the first commit.")
    root_commits = _git_text(runner, "rev-list", "--max-parents=0", config.head_ref).splitlines()
    if not root_commits:
        raise CollectorError(f"git history for {config.head_ref!r} has no root commit")
    return root_commits[-1]


def _validate_ref_range(
    base_ref: str, head_ref: str, runner: CommandRunner
) -> tuple[datetime, datetime]:
    base_date = _git_date(base_ref, runner)
    head_date = _git_date(head_ref, runner)
    command = ("git", "merge-base", "--is-ancestor", base_ref, head_ref)
    ancestry = runner(command)
    if ancestry.returncode == 1:
        raise CollectorError(f"base ref {base_ref!r} is not an ancestor of head ref {head_ref!r}")
    _require_success(ancestry, command)
    if base_date > head_date:
        raise CollectorError(f"base ref {base_ref!r} is newer than head ref {head_ref!r}")
    return base_date, head_date


def _expect_dict(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CollectorError(f"{context} must be a JSON object")
    return cast("dict[str, Any]", value)


def _expect_list(value: object, *, context: str) -> list[object]:
    if not isinstance(value, list):
        raise CollectorError(f"{context} must be a JSON array")
    return cast("list[object]", value)


def _normalize_author(value: object, *, context: str) -> str:
    if value is None:
        return ""
    author = _expect_dict(value, context=f"{context} author")
    login = author.get("login")
    if login is not None and not isinstance(login, str):
        raise CollectorError(f"{context} author.login must be a string or null")
    return login or ""


def _normalize_labels(value: object, *, context: str) -> tuple[str, ...]:
    labels = _expect_dict(value, context=f"{context} labels")
    nodes = _expect_list(labels.get("nodes"), context=f"{context} labels.nodes")
    names: list[str] = []
    for index, label_value in enumerate(nodes):
        label = _expect_dict(label_value, context=f"{context} label {index}")
        name = label.get("name")
        if not isinstance(name, str):
            raise CollectorError(f"{context} label {index} is missing name")
        names.append(name)
    return tuple(names)


def _normalize_issues(value: object, *, context: str) -> tuple[IssueSummary, ...]:
    issues = _expect_dict(value, context=f"{context} closingIssuesReferences")
    nodes = _expect_list(
        issues.get("nodes"),
        context=f"{context} closingIssuesReferences.nodes",
    )
    normalized: list[IssueSummary] = []
    for index, issue_value in enumerate(nodes):
        issue = _expect_dict(issue_value, context=f"{context} issue {index}")
        number = issue.get("number")
        title = issue.get("title")
        if not isinstance(number, int) or isinstance(number, bool):
            raise CollectorError(f"{context} issue {index} is missing number")
        if not isinstance(title, str):
            raise CollectorError(f"{context} issue {index} is missing title")
        normalized.append({"number": number, "title": title})
    return tuple(normalized)


def _normalize_merge_oid(value: object, *, context: str) -> str:
    if value is None:
        return ""
    merge_commit = _expect_dict(value, context=f"{context} mergeCommit")
    oid = merge_commit.get("oid")
    if oid is not None and not isinstance(oid, str):
        raise CollectorError(f"{context} mergeCommit.oid must be a string or null")
    return oid or ""


def _normalize_pr(value: object, *, page: int, index: int) -> PullRequestRecord:
    context = f"GitHub PR page {page} item {index}"
    node = _expect_dict(value, context=context)
    number = node.get("number")
    title = node.get("title")
    body = node.get("body")
    if not isinstance(number, int) or isinstance(number, bool):
        raise CollectorError(f"{context} is missing an integer number")
    if not isinstance(title, str):
        raise CollectorError(f"{context} is missing a title")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise CollectorError(f"{context} body must be a string or null")

    return PullRequestRecord(
        number=number,
        title=title,
        author=_normalize_author(node.get("author"), context=context),
        labels=_normalize_labels(node.get("labels"), context=context),
        merged_at=_parse_iso(node.get("mergedAt"), context=f"{context} mergedAt"),
        body=body,
        closing_issues=_normalize_issues(node.get("closingIssuesReferences"), context=context),
        merge_oid=_normalize_merge_oid(node.get("mergeCommit"), context=context),
    )


def _fetch_merged_prs(
    repository: str,
    base_branch: str,
    runner: CommandRunner,
) -> list[PullRequestRecord]:
    try:
        owner, name = repository.split("/", 1)
    except ValueError as exc:
        raise CollectorError("repository must use owner/name form") from exc
    if not owner or not name:
        raise CollectorError("repository must use owner/name form")

    records: list[PullRequestRecord] = []
    cursor = ""
    page = 1
    while True:
        args = [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={_GRAPHQL_QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"base={base_branch}",
        ]
        if cursor:
            args.extend(("-F", f"after={cursor}"))
        payload = _json_command(runner, args)
        data = _expect_dict(payload.get("data"), context=f"GitHub PR page {page} data")
        repository_data = _expect_dict(
            data.get("repository"), context=f"GitHub PR page {page} repository"
        )
        connection = _expect_dict(
            repository_data.get("pullRequests"),
            context=f"GitHub PR page {page} pullRequests",
        )
        nodes = _expect_list(
            connection.get("nodes"), context=f"GitHub PR page {page} pullRequests.nodes"
        )
        records.extend(
            _normalize_pr(node, page=page, index=index) for index, node in enumerate(nodes)
        )

        page_info = _expect_dict(
            connection.get("pageInfo"), context=f"GitHub PR page {page} pageInfo"
        )
        has_next = page_info.get("hasNextPage")
        end_cursor = page_info.get("endCursor")
        if not isinstance(has_next, bool):
            raise CollectorError(f"GitHub PR page {page} pageInfo.hasNextPage must be boolean")
        if not has_next:
            break
        if not isinstance(end_cursor, str) or not end_cursor:
            raise CollectorError(f"GitHub PR page {page} claims another page without an end cursor")
        cursor = end_cursor
        page += 1

    return records


def _body_excerpt(body: str) -> str:
    paragraph: list[str] = []
    for line in body.strip().splitlines():
        stripped = line.strip()
        if not paragraph and (not stripped or stripped.startswith("<!--")):
            continue
        if not stripped and paragraph:
            break
        paragraph.append(line)
    excerpt = "\n".join(paragraph[:5])
    return f"{excerpt[:300]}..." if len(excerpt) > 300 else excerpt


def _linked_issues(record: PullRequestRecord) -> list[IssueSummary]:
    issues: list[IssueSummary] = [
        {"number": issue["number"], "title": issue["title"]} for issue in record.closing_issues
    ]
    known_numbers = {issue["number"] for issue in issues}
    for match in _CLOSING_ISSUE_RE.finditer(record.body):
        number = int(match.group(1))
        if number not in known_numbers:
            issues.append({"number": number, "title": ""})
            known_numbers.add(number)
    return issues


def _dependency_updates(record: PullRequestRecord) -> list[dict[str, str]]:
    if record.author not in _DEPENDABOT_AUTHORS:
        return []
    bump = _BUMP_RE.search(record.title)
    if bump:
        return [{"name": bump.group(1), "from": bump.group(2), "to": bump.group(3)}]
    renovate = _RENOVATE_RE.search(record.title)
    if renovate:
        return [{"name": renovate.group(1), "from": "", "to": renovate.group(2)}]
    return []


def _pr_output(record: PullRequestRecord) -> PullRequestOutput:
    marker = _RELEASE_NOTE_RE.search(record.body)
    return {
        "number": record.number,
        "title": record.title,
        "author": record.author,
        "labels": list(record.labels),
        "body": record.body,
        "body_excerpt": _body_excerpt(record.body),
        "release_note": marker.group(1).strip() if marker else "",
        "linked_issues": _linked_issues(record),
        "dependency_updates": _dependency_updates(record),
    }


def _direct_commits(
    base_ref: str,
    head_ref: str,
    merge_oids: set[str],
    runner: CommandRunner,
) -> list[DirectCommit]:
    lines = _git_text(
        runner,
        "log",
        "--format=%H%x09%s%x09%an",
        f"{base_ref}..{head_ref}",
    ).splitlines()
    commits: list[DirectCommit] = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            raise CollectorError("git log returned a commit row without sha, subject, and author")
        sha, message, author = parts
        if sha in merge_oids or message.startswith("Merge pull request"):
            continue
        commits.append({"sha": sha, "message": message, "author": author})
    return commits[:50]


def _diff_stats(base_ref: str, head_ref: str, runner: CommandRunner) -> DiffStats:
    comparison = f"{base_ref}..{head_ref}"
    summary = _git_text(runner, "diff", "--shortstat", comparison)
    stats: DiffStats = {
        "files_changed": 0,
        "insertions": 0,
        "deletions": 0,
        "new_files": [],
    }
    files_match = re.search(r"(\d+)\s+files?\s+changed", summary)
    insertions_match = re.search(r"(\d+)\s+insertions?", summary)
    deletions_match = re.search(r"(\d+)\s+deletions?", summary)
    if files_match:
        stats["files_changed"] = int(files_match.group(1))
    if insertions_match:
        stats["insertions"] = int(insertions_match.group(1))
    if deletions_match:
        stats["deletions"] = int(deletions_match.group(1))

    new_files = _git_text(
        runner,
        "diff",
        "--diff-filter=A",
        "--name-only",
        comparison,
    )
    if new_files:
        stats["new_files"] = new_files.splitlines()
    return stats


def _benchmark_data(repository_root: Path) -> dict[str, object]:
    baselines = list(repository_root.glob("benchmarks/**/*_baseline.json"))
    return {"deltas": []} if baselines else {}


def _validate_issue(pr_index: int, issue_index: int, issue: IssueSummary) -> None:
    if set(issue) != {"number", "title"}:
        raise CollectorError(f"pull request {pr_index} linked issue {issue_index} has invalid keys")
    if not isinstance(issue["number"], int) or isinstance(issue["number"], bool):
        raise CollectorError(
            f"pull request {pr_index} linked issue {issue_index} number must be an integer"
        )
    if not isinstance(issue["title"], str):
        raise CollectorError(
            f"pull request {pr_index} linked issue {issue_index} title must be a string"
        )


def _validate_dependency_update(
    pr_index: int,
    update_index: int,
    update: dict[str, str],
) -> None:
    if set(update) != {"name", "from", "to"} or not all(
        isinstance(update.get(key), str) for key in ("name", "from", "to")
    ):
        raise CollectorError(f"pull request {pr_index} dependency update {update_index} is invalid")


def _validate_pull_request(index: int, pull_request: PullRequestOutput) -> None:
    required = {
        "number",
        "title",
        "author",
        "labels",
        "body",
        "body_excerpt",
        "release_note",
        "linked_issues",
        "dependency_updates",
    }
    if set(pull_request) != required:
        raise CollectorError(f"pull request {index} keys do not match the report contract")
    if not isinstance(pull_request["number"], int) or isinstance(pull_request["number"], bool):
        raise CollectorError(f"pull request {index} number must be an integer")
    for key in ("title", "author", "body", "body_excerpt", "release_note"):
        if not isinstance(pull_request[key], str):
            raise CollectorError(f"pull request {index} {key} must be a string")
    if not all(isinstance(label, str) for label in pull_request["labels"]):
        raise CollectorError(f"pull request {index} labels must contain strings")
    for issue_index, issue in enumerate(pull_request["linked_issues"]):
        _validate_issue(index, issue_index, issue)
    for update_index, update in enumerate(pull_request["dependency_updates"]):
        _validate_dependency_update(index, update_index, update)


def _validate_diff_stats(stats: DiffStats) -> None:
    if set(stats) != {"files_changed", "insertions", "deletions", "new_files"}:
        raise CollectorError("collector output diff_stats keys do not match the report contract")
    if not all(
        isinstance(stats[key], int) and not isinstance(stats[key], bool)
        for key in ("files_changed", "insertions", "deletions")
    ):
        raise CollectorError("collector output diff counters must be integers")
    if not all(isinstance(path, str) for path in stats["new_files"]):
        raise CollectorError("collector output new_files must contain strings")


def _validate_direct_commit(index: int, commit: DirectCommit) -> None:
    if set(commit) != {"sha", "message", "author"} or not all(
        isinstance(commit[key], str) for key in ("sha", "message", "author")
    ):
        raise CollectorError(f"direct commit {index} does not match the report contract")


def _validate_top_level_types(data: ReleaseData) -> None:
    for key in ("version", "previous_version", "release_date", "repository", "compare_url"):
        if not isinstance(data[key], str):
            raise CollectorError(f"collector output {key!r} must be a string")
    for key in ("pull_requests", "contributors", "new_contributors", "direct_commits"):
        if not isinstance(data[key], list):
            raise CollectorError(f"collector output {key!r} must be a list")
    if not isinstance(data["diff_stats"], dict) or not isinstance(data["benchmarks"], dict):
        raise CollectorError("collector output stats and benchmarks must be objects")
    if not all(isinstance(value, str) for value in data["contributors"]):
        raise CollectorError("collector output contributors must contain strings")
    if not all(isinstance(value, str) for value in data["new_contributors"]):
        raise CollectorError("collector output new_contributors must contain strings")


def validate_release_data(data: ReleaseData) -> None:
    """Validate the report/template boundary before writing JSON."""
    required = {
        "version",
        "previous_version",
        "release_date",
        "repository",
        "pull_requests",
        "contributors",
        "new_contributors",
        "compare_url",
        "diff_stats",
        "direct_commits",
        "benchmarks",
    }
    if set(data) != required:
        raise CollectorError("collector output keys do not match the release report contract")
    _validate_top_level_types(data)

    for index, pull_request in enumerate(data["pull_requests"]):
        _validate_pull_request(index, pull_request)
    _validate_diff_stats(data["diff_stats"])
    for index, commit in enumerate(data["direct_commits"]):
        _validate_direct_commit(index, commit)
    deltas = data["benchmarks"].get("deltas")
    if deltas is not None and not isinstance(deltas, list):
        raise CollectorError("collector output benchmarks.deltas must be a list")


def _warn(message: str) -> None:
    sys.stderr.write(f"::warning::{message}\n")


def collect_release_data(
    config: CollectorConfig,
    *,
    runner: CommandRunner = subprocess_runner,
    today: Callable[[], date] = date.today,
    warn: Callable[[str], None] | None = None,
) -> ReleaseData:
    """Collect release data from GitHub and git for one comparison."""
    if not config.repository or "/" not in config.repository:
        raise CollectorError("repository must use owner/name form")
    if not config.head_ref:
        raise CollectorError("head ref must not be empty")
    warning = warn or _warn

    base_ref = _resolve_base_ref(config, runner, warning)
    base_date, head_date = _validate_ref_range(base_ref, config.head_ref, runner)
    base_branch = _default_branch(config.repository, runner)
    all_prs = _fetch_merged_prs(config.repository, base_branch, runner)
    selected = [pr for pr in all_prs if base_date <= pr.merged_at <= head_date]

    outputs = [_pr_output(pr) for pr in selected]
    current_authors = {pr.author for pr in selected if pr.author}
    prior_authors = {pr.author for pr in all_prs if pr.author and pr.merged_at < base_date}
    contributors = sorted(current_authors)
    new_contributors = sorted(current_authors - prior_authors)
    merge_oids = {pr.merge_oid for pr in selected if pr.merge_oid}
    direct_commits = _direct_commits(base_ref, config.head_ref, merge_oids, runner)

    version = (
        config.head_ref.removeprefix("v") if config.head_ref.startswith("v") else config.head_ref
    )
    previous_version = base_ref.removeprefix("v") if base_ref.startswith("v") else base_ref
    data: ReleaseData = {
        "version": version,
        "previous_version": previous_version,
        "release_date": today().isoformat(),
        "repository": config.repository,
        "pull_requests": outputs,
        "contributors": contributors,
        "new_contributors": new_contributors,
        "compare_url": (
            f"https://github.com/{config.repository}/compare/{base_ref}...{config.head_ref}"
        ),
        "diff_stats": _diff_stats(base_ref, config.head_ref, runner),
        "direct_commits": direct_commits,
        "benchmarks": _benchmark_data(config.repository_root),
    }
    validate_release_data(data)
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="GitHub repository as owner/name")
    parser.add_argument("--base-ref", default="", help="Base tag, branch, or SHA")
    parser.add_argument("--head-ref", required=True, help="Head tag, branch, or SHA")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(),
        help="Repository root used for benchmark placeholder discovery",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Collect data and write the validated JSON contract."""
    args = _build_parser().parse_args(argv)
    config = CollectorConfig(
        repository=args.repository,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        repository_root=args.repository_root,
    )
    try:
        data = collect_release_data(config)
        args.output.write_text(f"{json.dumps(data, indent=2)}\n", encoding="utf-8")
    except (CollectorError, OSError) as exc:
        sys.stderr.write(f"::error::Release-note collection failed: {exc}\n")
        return 2

    sys.stdout.write(
        f"Collected {len(data['pull_requests'])} PRs, {len(data['direct_commits'])} direct commits"
        "\n"
    )
    sys.stdout.write(
        f"  {len(data['new_contributors'])} new contributor(s), "
        f"{data['diff_stats']['files_changed']} files changed"
        "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
