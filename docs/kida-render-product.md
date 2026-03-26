# kida render — CI/CD Reporting as a Product

## One-liner

Turn structured CI output into beautiful, readable reports — on PRs, in logs, everywhere.

---

## The Problem

CI pipelines produce walls of unformatted text. Developers scroll through hundreds of lines of raw pytest output, terraform plans, security scan results, and deploy logs trying to find what matters. The signal-to-noise ratio is terrible.

Current solutions:

| Approach | Problem |
|---|---|
| Raw logs | Unreadable. Finding a failed test means Ctrl+F through noise. |
| Custom scripts | Every team writes their own formatter. Fragile, per-tool, no reuse. |
| Dashboards (Datadog, Grafana) | Overkill. Requires accounts, API keys, setup. You just want to know if the build passed. |
| GitHub's native summaries | Limited markdown. No real formatting, no templating, no design system. |

The core insight: **CI output is structured data (JSON, XML, YAML) that gets dumped as raw text.** A template engine can turn that structured data into readable output with zero custom code.

---

## The Product

### Layer 1: `kida render` CLI (open source, exists today)

A command that renders any template with any JSON data:

```bash
kida render report.txt --data results.json
```

This already works. It's part of kida's terminal rendering mode. Supports color depth detection, responsive layout, ANSI-aware formatting, and built-in components (panels, tables, progress bars, badges).

**Value**: Developers can format any CI output locally or in scripts. Zero dependencies beyond kida.

### Layer 2: GitHub Action (free, drives adoption) ✅

A GitHub Action that renders reports and posts them as PR comments or step summaries:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest --junitxml=results.xml

- name: Post report
  uses: lbliii/kida@v1
  with:
    template: pytest           # built-in template name
    data: results.xml
    data-format: junit-xml
    post-to: step-summary      # or: pr-comment, or both

# PR comment (updates in place, no duplicates)
- name: Post report to PR
  uses: lbliii/kida@v1
  with:
    template: pytest
    data: results.xml
    data-format: junit-xml
    post-to: pr-comment
```

Six built-in templates ship with the action: **pytest**, **coverage**, **ruff**, **ty**, **jest**, and **gotest**. Users can also point to custom templates in their repo.

**Value**: One line in a workflow file gets you formatted test reports on every PR. No accounts, no API keys, no external services.

### Layer 3: Template Gallery (free tier + paid)

A hosted collection of pre-built, tested report templates for CI tools:

**Testing**: pytest, jest, go test, cargo test, phpunit, rspec, junit XML
**Coverage**: coverage.py, istanbul, lcov, go cover
**Security**: trivy, snyk, dependabot, semgrep, bandit
**Infrastructure**: terraform plan, pulumi preview, cloudformation changeset
**Deployment**: helm diff, kubectl rollout, docker build summary
**Performance**: benchmark results, lighthouse scores, bundle size diffs
**Languages**: eslint, ruff, clippy, golangci-lint

Each template is a `.txt` file that transforms the tool's JSON/XML output into a formatted report. Templates are versioned and tested against real tool output.

### Layer 4: Teams (paid tier)

For organizations that want consistency across repos:

- **Branded templates** — company logo, colors, custom layout
- **Org-wide template registry** — shared templates across all repos, managed centrally
- **Trend tracking** — "your test suite is 12% slower than last week" as a PR comment
- **Template versioning** — pin to stable versions, preview updates before rolling out
- **Custom data transforms** — pre-process tool output before rendering (normalize different test runners into a common schema)

---

## How It Works Technically

### The rendering pipeline

```
Tool output (JSON/XML)
    ↓
Data transform (normalize to template schema)
    ↓
kida render (template + data → formatted output)
    ↓
Output target (PR comment, check summary, log, artifact)
```

### GitHub Action internals

The action is a lightweight wrapper:

1. **Read** the data file (JSON, or XML/YAML converted to JSON)
2. **Select** the template (built-in name or path to custom `.txt` file)
3. **Render** via `kida render --data <file> --mode terminal` (for logs) or `--mode markdown` (for PR comments)
4. **Post** to the configured target via GitHub API

The action itself is small — kida does all the rendering work.

### Markdown mode (new capability needed)

For PR comments and check summaries, kida would need a markdown output mode alongside the existing terminal mode. This is a natural extension:

- Terminal mode: `autoescape="terminal"` → ANSI escape codes
- HTML mode: `autoescape=True` → HTML entities
- **Markdown mode**: `autoescape="markdown"` → GitHub-flavored markdown

The same template could target multiple output modes. A `panel()` component renders as a bordered box in terminal, a collapsible `<details>` in markdown, a `<div>` in HTML.

### Data transforms

Different test runners produce different JSON schemas. A transform layer normalizes them:

```
pytest JSON report → common test result schema → template
jest JSON output   → common test result schema → same template
go test JSON       → common test result schema → same template
```

Transforms are small Python functions or jq-style mappings. The template only needs to know one schema.

---

## Competitive Landscape

### Direct competitors

| Tool | What it does | Weakness |
|---|---|---|
| **dorny/test-reporter** | Posts test results as GitHub checks | Single-purpose (tests only). Fixed format. No customization. |
| **EnricoMi/publish-unit-test-result-action** | Posts JUnit XML results | JUnit only. Limited formatting. |
| **marocchino/sticky-pull-request-comment** | Posts markdown comments on PRs | No data processing. You write the markdown yourself. |
| **LouisBrunner/checks-action** | Creates GitHub check runs | Raw API wrapper. No formatting intelligence. |

### Indirect competitors

| Tool | What it does | Why kida is different |
|---|---|---|
| **Codecov / Coveralls** | Coverage reporting | Single-purpose SaaS with accounts/API keys. kida is local-first, template-driven, any data. |
| **Datadog CI Visibility** | CI analytics dashboard | Enterprise SaaS. kida is a free CLI that does 80% of the job. |
| **BuildPulse / Trunk** | Flaky test detection | Specialized analytics. kida is general-purpose formatting. |

### Key differentiator

Every competitor is single-purpose. They do one thing (test results, coverage, security) with one fixed format. **kida-report does any data with any template.** One action replaces five.

---

## Go-to-Market

### Phase 1: Seed adoption through open source (now)

kida's terminal mode already works. The `kida render` CLI is shipping. Terminal examples demonstrate the output quality. Developers who use kida for HTML templates discover the terminal mode and start using it in scripts.

**Actions**:
- Ship high-quality terminal examples (done)
- Blog post: "Beautiful CI output in one command"
- Add `kida render` examples to kida docs

### Phase 2: GitHub Action (month 1-2)

Release `lbliii/kida-report` on the GitHub Actions marketplace. Ship with 5 built-in templates:
- pytest
- jest
- go test
- coverage.py
- terraform plan

**Actions**:
- Build the action (thin wrapper around kida render)
- Implement markdown output mode in kida
- Write data transforms for the 5 initial tools
- Marketplace listing with screenshots

### Phase 3: Template gallery (month 3-4)

Launch a docs site / gallery with community-contributed templates. Make it easy to contribute: fork, add a template + test fixture, PR.

**Actions**:
- Template gallery site (could be GitHub Pages, rendered by kida itself)
- Contribution guide with template testing framework
- Expand to 15-20 tools

### Phase 4: Teams tier (month 6+)

Once the free action has adoption (target: 1000+ repos), launch the paid tier for organizations that want centralized template management, branding, and trend tracking.

**Actions**:
- Hosted template registry API
- Org-level configuration (`.github/kida-report.yml`)
- Trend tracking service (store historical data, compute diffs)
- Pricing: $29/month per org (unlimited repos)

---

## Revenue Model

| Tier | Price | Target |
|---|---|---|
| CLI + Action + built-in templates | Free | Individual developers, small teams |
| Custom templates + gallery access | Free | Community adoption, ecosystem building |
| Teams: branded templates, org registry, trend tracking | $29/org/month | Engineering teams (20-200 devs) |
| Enterprise: SSO, audit logs, SLA, on-prem | Custom | Large orgs |

**Revenue target**: 500 paying orgs at $29/month = $14,500/month = $174k/year. Achievable if the free action reaches 5,000+ repos (2-10% conversion is typical for dev tools).

**Cost structure**: Near-zero. The action runs in the user's CI. No hosting, no compute, no storage (except trend tracking in paid tier). Template gallery is static files. The only real cost is a small API for the teams registry.

---

## Technical Requirements

### Must build (for the action)

1. **Markdown output mode for kida** — templates that render to GitHub-flavored markdown instead of ANSI. This is the biggest engineering task. The component system (panel, table, badge) needs markdown equivalents.

2. **Data transform layer** — small functions that normalize tool-specific JSON into common schemas. Start with 5 tools, expand via community contributions.

3. **GitHub Action wrapper** — reads inputs, calls `kida render`, posts via GitHub API. Small and straightforward.

4. **Template testing framework** — given a fixture JSON file, render the template and snapshot-test the output. Ensures templates don't break when kida updates.

### Nice to have (for teams tier)

5. **Trend tracking service** — stores rendered report metadata (pass/fail counts, durations, coverage numbers) and computes week-over-week diffs. Posts trend summaries on PRs.

6. **Template registry API** — org-scoped template storage with versioning. Actions pull templates from the registry instead of the repo.

7. **b-stack integration** — patitias renders markdown content within reports (e.g., test docstrings). rosettes highlights code in failure snippets and diffs.

---

## Risks

| Risk | Mitigation |
|---|---|
| GitHub improves native check summaries, reducing need | Our "any data + any template" flexibility can't be replicated by a platform. GitHub will build opinionated, fixed-format features. |
| Low conversion from free to paid | The free tier drives kida adoption regardless. The SaaS funds open source development but isn't the only goal. |
| Template maintenance burden (tools change output formats) | Community contributions + snapshot testing. Each template is tested against real tool output fixtures. |
| Competitor builds the same thing | First-mover advantage + b-stack integration (kida + patitias + rosettes) is hard to replicate. The rendering engine is the moat. |
| Enterprise sales cycle is long | Start with self-serve $29/month. Enterprise tier comes later only if there's inbound demand. |

---

## Open Questions for Exploration

1. **Markdown mode architecture**: Should templates be mode-agnostic (same template renders to terminal and markdown) or should there be separate templates per mode? Mode-agnostic is more elegant but harder to implement well.

2. **Data transform design**: Should transforms be Python functions, jq expressions, or a custom DSL? Python is most flexible but requires the action to bundle a Python runtime. jq is lighter but less capable.

3. **PR comment vs check summary**: GitHub check run summaries have a 65,535 character limit and support markdown. PR comments have no practical limit. Which is the better default target? Could support both.

4. **Template discoverability**: How do users find templates for their tools? A CLI command like `kida templates search pytest`? A web gallery? Both?

5. **Versioning strategy**: When a tool changes its output format (e.g., pytest upgrades), how do templates handle backwards compatibility? Version pins? Auto-detection?

6. **Mono-action vs multi-action**: One action that handles all tools via a `template:` input, or separate actions per tool (`kida-pytest`, `kida-terraform`)? Mono is cleaner but the marketplace discoverability is better with separate listings.

7. **Community model**: How to incentivize template contributions? A "template authors" program? Revenue sharing on the paid tier for popular templates?

---

## Success Metrics

| Metric | Phase 2 target (3 months) | Phase 4 target (12 months) |
|---|---|---|
| GitHub Action installs | 500 repos | 5,000 repos |
| Built-in templates | 5 | 25 |
| Community templates | 0 | 15 |
| Paying orgs | 0 | 100 |
| Monthly revenue | $0 | $2,900 |

---

## Summary

`kida render` is a general-purpose template rendering CLI that already works. Wrapping it in a GitHub Action with pre-built templates for common CI tools creates a product that replaces 5+ single-purpose reporting actions with one. The free action drives kida ecosystem adoption. The paid teams tier generates revenue from organizations that want branded, consistent CI reporting. The total addressable effort is small (thin action wrapper + markdown mode + data transforms) and the infrastructure cost is near-zero.

The play: make CI output beautiful with one line in a workflow file. The moat: kida's rendering engine and the b-stack integration are hard to replicate.
