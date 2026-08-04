# )彡 Kida

[![PyPI version](https://img.shields.io/pypi/v/kida-templates.svg)](https://pypi.org/project/kida-templates/)
[![Build Status](https://github.com/lbliii/kida/actions/workflows/tests.yml/badge.svg)](https://github.com/lbliii/kida/actions/workflows/tests.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://pypi.org/project/kida-templates/)
[![Python 3.14t no-GIL tested](https://img.shields.io/badge/Python%203.14t-no--GIL%20tested-2ea44f.svg)](https://lbliii.github.io/kida/docs/about/thread-safety/#tested-support-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

![Kida, a cross-eyed snow-lynx Bengal cat, actively assembling jungle components that become web, terminal, Markdown, and CI output](site/assets/images/kida-jungle-components-hero.webp)

**Server-side components for Python—typed, composable, and checked before render.**

Kida gives Python applications a real component model: typed props, named and
scoped slots, static call-site validation, and error boundaries. The same pure-
Python engine renders HTML, Markdown, terminal output, and CI reports—with no
npm, no build step, and no runtime dependencies.

[Read the docs](https://lbliii.github.io/kida/) ·
[Build a component](https://lbliii.github.io/kida/docs/usage/components/) ·
[Compare with Jinja2 macros](https://lbliii.github.io/kida/docs/tutorials/component-comparison/)

## Why Kida

Templates become application architecture long before most template engines
notice. Arguments stay implicit, composition collapses into one caller block,
and broken component calls surface only when a request renders the wrong path.

Kida makes those contracts explicit:

- **Typed props** document and validate a component's inputs.
- **Named and scoped slots** compose structure without prop drilling.
- **Static validation** catches bad names, missing props, and literal type
  mismatches before render.
- **Structured metadata** lets frameworks discover components without parsing
  private AST internals.
- **One rendering model** serves web pages, fragments, docs, terminals, and CI.

## Quick Start

Kida requires Python 3.14 or later.

```bash
pip install kida-templates
```

Define a component and call it in the same template:

```kida
{% def card(title: str, variant: str = "default") %}
<article class="card card--{{ variant }}">
  <header>
    <h2>{{ title }}</h2>
    {% slot actions %}
  </header>
  <div class="card__body">{% slot %}</div>
</article>
{% enddef %}

{% call card("Settings", variant="elevated") %}
  {% slot actions %}<button>Save</button>{% end %}
  <p>Configure your preferences.</p>
{% endcall %}
```

Render it from ordinary Python:

```python
from kida import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))
html = env.get_template("page.html").render()
```

Kida's canonical block ending is `{% end %}`. Matching explicit closers such as
`{% endif %}`, `{% endfor %}`, and `{% endblock %}` are also accepted, so an
otherwise compatible Jinja template does not need closer-only edits.

## Catch Broken Calls Before Render

Suppose a call misspells `label` and passes a string where `count` expects an
integer:

```kida
{% def badge(count: int, label: str) %}
<span class="badge">{{ count }} {{ label }}</span>
{% enddef %}

{{ badge(count="five", lable="Messages") }}
```

Run the checker:

```bash
kida check templates/ --strict --validate-calls
```

```text
templates/dashboard.html:5: K-CMP-001: Call to 'badge' — unknown params: lable; missing required: label
templates/dashboard.html:5: K-CMP-002: type: badge() param 'count' expects int, got str ('five')
```

The mistake stays in the editor or CI—not in a user's request.

## A Component Model, Not a Macro Convention

| Capability | Kida |
|---|---|
| Typed props | `{% def card(title: str, count: int = 0) %}` |
| Named slots | `{% slot actions %}` and `{% slot %}` |
| Scoped slots | `{% slot row let:item=item %}` |
| Conditional content | `has_slot("footer")` |
| Context propagation | `{% provide theme = "dark" %}` and `consume("theme")` |
| Error boundaries | `{% try %}...{% fallback error %}...{% endtry %}` |
| Co-located assets | `{% push "styles" %}` and `{% stack "styles" %}` |
| Partial rendering | `render_block()` and parameterized regions |
| Streaming | `render_stream()` and `render_stream_async()` |
| Discovery | `kida components templates/` or the introspection API |

Use Kida in Flask, Django, FastAPI, Starlette, Chirp, Bengal, scripts, and CI.
Render full pages or HTMX fragments; reuse the same semantics for Markdown
reports and ANSI-aware terminal interfaces.

The [app-owned component authoring contract](site/content/docs/usage/components.md#app-owned-authoring-contract)
defines extraction heuristics, composition seams, and framework/application
ownership boundaries.

## One System, Many Surfaces

| Surface | What Kida provides |
|---|---|
| Web applications | Components, layouts, streaming, and block rendering |
| Static sites | Reusable content components and scoped state |
| Terminal tools | ANSI-aware tables, badges, panels, and dashboards |
| CI reports | GitHub step summaries and PR comments from test and analysis data |
| Frameworks | Component metadata, dependency analysis, and multi-root inspection |

The GitHub Action includes templates for pytest, coverage, ruff, ty, Jest, Go
test, SARIF, release notes, and agent reports. See the
[CI reporting guide](https://lbliii.github.io/kida/docs/usage/github-action/).

## Pure Python, Including Free-Threading

Kida has zero runtime dependencies. Templates compile to immutable Python code,
render state lives in `ContextVar`, and environment mutation uses copy-on-write
patterns. The documented sharing contract is tested under `PYTHON_GIL=0` on
free-threaded Python 3.14t.

That claim is intentionally bounded: it covers Kida's
[public thread-safety contract](https://lbliii.github.io/kida/docs/about/thread-safety/#whats-safe),
not unsynchronized application state or custom callables.

## Explore

- [Get started](https://lbliii.github.io/kida/docs/get-started/)
- [Build components](https://lbliii.github.io/kida/docs/usage/components/)
- [Integrate a framework](https://lbliii.github.io/kida/docs/tutorials/)
- [Browse the syntax reference](https://lbliii.github.io/kida/docs/syntax/)
- [Use the CLI](https://lbliii.github.io/kida/docs/reference/cli/)
- [Read the security model](https://lbliii.github.io/kida/docs/advanced/security/)

```bash
kida render template.txt --data context.json
kida check templates/ --validate-calls --a11y --typed
kida components templates/ --json
kida fmt templates/
kida extract templates/ -o messages.pot
```

## Status

Kida is pre-1.0 and used standalone, through mainstream Python frameworks, and
across a broader pure-Python rendering stack. The API can still move, but the
core commitments are stable: typed composition, static validation, render-
surface parity, zero runtime dependencies, and free-threaded safety.

For migrations, start with the
[0.12.0 release notes](https://lbliii.github.io/kida/releases/0.12.0/) and follow
the linked upgrade guides.

## Python Components Ecosystem

Kida is the component layer in a personal, pure-Python stack built for Python
3.14t. Each project stands on its own; together they cover the path from content
and components to applications, servers, sites, terminals, and developer tools.

| | Project | Role |
|--:|---|---|
| **⌁⌁** | [Chirp](https://github.com/lbliii/chirp) | Web framework |
| **=^..^=** | [Pounce](https://github.com/lbliii/pounce) | ASGI server |
| **)彡** | **Kida** | Server-side component system ← You are here |
| **∿∿** | [Purr](https://github.com/lbliii/purr) | Content runtime |
| **ᓚᘏᗢ** | [Bengal](https://github.com/lbliii/bengal) | Static-site integration |
| **ฅᨐฅ** | [Patitas](https://github.com/lbliii/patitas) | Markdown parser |
| **⌾⌾⌾** | [Rosettes](https://github.com/lbliii/rosettes) | Syntax highlighter |
| **ᓃ‿ᓃ** | [Milo](https://github.com/lbliii/milo-cli) | Terminal UI framework |

## License

MIT License — see [LICENSE](LICENSE).
