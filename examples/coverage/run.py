"""Template coverage collection example."""

from kida import DictLoader, Environment
from kida.coverage import CoverageCollector


def main():
    loader = DictLoader(
        {
            "page.html": """\
<h1>{{ title }}</h1>
{% if show_nav %}
<nav>
  <a href="/">Home</a>
  <a href="/about">About</a>
</nav>
{% endif %}
<main>
  {% if items %}
  <ul>
    {% for item in items %}
    <li>{{ item }}</li>
    {% endfor %}
  </ul>
  {% else %}
  <p>No items found.</p>
  {% endif %}
</main>
{% if footer %}
<footer>{{ footer }}</footer>
{% endif %}
""",
        }
    )

    env = Environment(loader=loader)

    cov = CoverageCollector()

    # Render inside the collector context manager.
    # Only some branches are taken, so coverage will be partial.
    with cov:
        tmpl = env.get_template("page.html")

        # First render: nav shown, items present, no footer
        print("--- Render 1 ---")
        print(tmpl.render(title="Hello", show_nav=True, items=["a", "b"], footer=None))

        # Second render: no nav, no items, footer shown
        print("--- Render 2 ---")
        print(tmpl.render(title="World", show_nav=False, items=[], footer="bye"))

    # Print the text summary
    print("--- Coverage Summary ---")
    print(cov.summary())

    # Write LCOV output
    lcov_path = "coverage.lcov"
    cov.write_lcov(lcov_path)
    print(f"\nLCOV data written to {lcov_path}")


if __name__ == "__main__":
    main()
