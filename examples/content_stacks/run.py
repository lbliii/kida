"""Content stacks example — {% push %} and {% stack %}.

Child templates push CSS and JS snippets into named stacks.
The base template emits them with {% stack %} at the right spots.

Run:
    python run.py
"""

from kida import DictLoader, Environment

templates = {
    "page.html": """\
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{ title }}</title>
    {% push "styles" %}
    <link rel="stylesheet" href="/css/widgets.css">
    <style>.hero { color: navy; }</style>
    {% end %}
    {% push "scripts" %}
    <script src="/js/widgets.js"></script>
    {% end %}
    {% stack "styles" %}
</head>
<body>
    <section class="hero">
        <h1>{{ heading }}</h1>
        <p>{{ message }}</p>
    </section>
    {% push "scripts" %}
    <script>console.log("page ready");</script>
    {% end %}
    {% stack "scripts" %}
</body>
</html>
""",
}


def main() -> None:
    env = Environment(loader=DictLoader(templates))
    template = env.get_template("page.html")
    # Push adds content to a named collection; stack emits it.
    # Pushes before the stack tag are collected and rendered at the stack point.

    output = template.render(
        title="Content Stacks Demo",
        heading="Push & Stack",
        message="CSS and JS pushed from the child, emitted in the base.",
    )
    print(output)


if __name__ == "__main__":
    main()
