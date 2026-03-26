{#- Markdown component templates for Kida.

    Import with:
        {% from "components.md" import section, metric, file_list, collapsible %}

    All components produce GitHub-flavored markdown output.
    Uses markdown filters (bold, h1-h4, code) to avoid autoescape issues.
-#}


{#- section — Heading with caller content.

    Parameters:
        title : Section heading text.
        level : Heading level (1-4, default 2).

    Usage:
        {% call section("Results") %}
        Content goes here.
        {% endcall %}
-#}
{% def section(title, level=2) %}
{% if level == 1 %}{{ title | h1 }}{% elif level == 2 %}{{ title | h2 }}{% elif level == 3 %}{{ title | h3 }}{% else %}{{ title | h4 }}{% endif %}

{{ caller() }}
{% end %}


{#- metric — Bold label with value and optional unit.

    Usage:
        {{ metric("Duration", "3.2", "s") }}
        {{ metric("Tests", 42) }}
-#}
{% def metric(label, value, unit="") %}
{{ label | bold }}: {{ value }}{{ " " ~ unit if unit else "" }}
{% end %}


{#- file_list — Bulleted code-formatted file list.

    Usage:
        {{ file_list(["src/main.py", "tests/test_main.py"]) }}
-#}
{% def file_list(files) %}
{% for f in files -%}
- {{ f | code }}
{% endfor %}
{% end %}


{#- collapsible — Details/summary wrapper via caller.

    Usage:
        {% call collapsible("Click to expand") %}
        Hidden content here.
        {% endcall %}
-#}
{% def collapsible(summary="Details") %}
<details>
<summary>{{ summary }}</summary>

{{ caller() }}

</details>
{% end %}
