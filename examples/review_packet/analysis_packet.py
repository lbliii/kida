"""Example-only large-app analysis packet.

This combines current Kida analysis helpers into one dict for a framework or
CI report to render. It is deliberately local to the example; it is not a
published schema.
"""

from __future__ import annotations

from dataclasses import asdict

from kida import DictLoader, Environment
from kida.analysis import (
    audit_escaping,
    check_context_contract,
    extract_literal_attributes,
    lint_privacy,
)


def build_large_app_packet() -> dict[str, object]:
    env = Environment(
        loader=DictLoader(
            {
                "page.html": """
{% from "components.html" import card %}
<main id="thread" data-page="thread">
  {{ card(page.title, body_html | safe(reason="sanitized markdown")) }}
  <button hx-post="/reply">Reply</button>
  {{ user.email }}
</main>
""",
                "components.html": """
{% def card(title: str, body_html: str) %}
<article class="card">
  <h1>{{ title }}</h1>
  {{ body_html }}
  {% slot actions %}
</article>
{% end %}
""",
            }
        )
    )
    template = env.get_template("page.html")
    components = []
    for component_template in ("components.html", "page.html"):
        component = env.get_template(component_template)
        components.extend(
            {
                "name": meta.name,
                "template": meta.template_name,
                "params": [param.name for param in meta.params],
                "slots": list(meta.slots),
                "has_default_slot": meta.has_default_slot,
                "depends_on": sorted(meta.depends_on),
            }
            for meta in component.def_metadata().values()
        )

    return {
        "template": template.name,
        "required_context": sorted(template.required_context()),
        "context_contract": [
            asdict(issue)
            for issue in check_context_contract(
                template,
                provided={"page.title", "body_html"},
                globals={"card"},
            )
        ],
        "components": components,
        "literal_attributes": [
            asdict(attr)
            for attr in extract_literal_attributes(template, names={"id", "data-page", "hx-post"})
        ],
        "escape_findings": [
            asdict(finding) for finding in audit_escaping(template, include_output_sites=False)
        ],
        "privacy_findings": [asdict(finding) for finding in lint_privacy(template)],
    }
