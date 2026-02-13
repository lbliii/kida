"""Jinja2 migration -- side-by-side comparison of equivalent templates.

Same page logic in Kida and Jinja2. Highlights syntax differences:
- {% end %} vs {% endif %}/{% endfor %}
- {% match %} vs {% if %}/{% elif %}/{% else %}
- ?? vs | default()
- ?. vs | default() for optional chaining

Run:
    python app.py
"""

from jinja2 import Environment as Jinja2Environment

from kida import Environment as KidaEnvironment

# Equivalent templates: status badge with optional user
KIDA_TEMPLATE = """\
<div class="status">
{% match status %}
{% case "active" %}
    <span class="badge active">Active</span>
{% case "pending" %}
    <span class="badge pending">Pending</span>
{% case _ %}
    <span class="badge unknown">Unknown</span>
{% end %}
{% if user?.name %}
    <span>User: {{ user.name }}</span>
{% end %}
<p>Bio: {{ user?.bio ?? "No bio" }}</p>
</div>
"""

JINJA2_TEMPLATE = """\
<div class="status">
{% if status == "active" %}
    <span class="badge active">Active</span>
{% elif status == "pending" %}
    <span class="badge pending">Pending</span>
{% else %}
    <span class="badge unknown">Unknown</span>
{% endif %}
{% if user is defined and user.name is defined %}
    <span>User: {{ user.name }}</span>
{% endif %}
<p>Bio: {{ user.bio | default("No bio") if user is defined and user.bio is defined else "No bio" }}</p>
</div>
"""

# Simplify Jinja2: Kida's ?. and ?? don't have direct equivalents; use simpler logic
JINJA2_TEMPLATE_SIMPLE = """\
<div class="status">
{% if status == "active" %}
    <span class="badge active">Active</span>
{% elif status == "pending" %}
    <span class="badge pending">Pending</span>
{% else %}
    <span class="badge unknown">Unknown</span>
{% endif %}
{% if user and user.name %}
    <span>User: {{ user.name }}</span>
{% endif %}
<p>Bio: {{ user.bio | default("No bio") if user else "No bio" }}</p>
</div>
"""

kida_env = KidaEnvironment()
jinja2_env = Jinja2Environment(autoescape=True)

kida_tmpl = kida_env.from_string(KIDA_TEMPLATE)
jinja2_tmpl = jinja2_env.from_string(JINJA2_TEMPLATE_SIMPLE)

# Context: active user with bio
context_full = {
    "status": "active",
    "user": {"name": "Alice", "bio": "Developer"},
}

# Context: pending, minimal user
context_minimal = {
    "status": "pending",
    "user": {"name": "Bob"},
}

# Context: unknown status, no user
context_empty = {
    "status": "archived",
    "user": None,
}

kida_output_full = kida_tmpl.render(**context_full)
jinja2_output_full = jinja2_tmpl.render(**context_full)

kida_output_minimal = kida_tmpl.render(**context_minimal)
jinja2_output_minimal = jinja2_tmpl.render(**context_minimal)

kida_output_empty = kida_tmpl.render(**context_empty)
jinja2_output_empty = jinja2_tmpl.render(**context_empty)


def _normalize(html: str) -> str:
    """Normalize whitespace for comparison."""
    return " ".join(html.split())


def main() -> None:
    print("=== Full context (active, user with bio) ===")
    print("Kida:", kida_output_full[:80] + "...")
    print("Jinja2:", jinja2_output_full[:80] + "...")
    print()
    print("=== Minimal (pending, user without bio) ===")
    print("Kida:", kida_output_minimal[:80] + "...")
    print("Jinja2:", jinja2_output_minimal[:80] + "...")
    print()
    print("=== Empty (no user) ===")
    print("Kida:", kida_output_empty[:80] + "...")
    print("Jinja2:", jinja2_output_empty[:80] + "...")


if __name__ == "__main__":
    main()
