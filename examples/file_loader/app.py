"""File-based templates -- the most common real-world pattern.

Loads templates from disk with FileSystemLoader, demonstrates template
inheritance (extends/block) and includes.

Run:
    python app.py
"""

from pathlib import Path

from kida import Environment, FileSystemLoader

templates_dir = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(templates_dir)))

# Render both pages
home_template = env.get_template("home.html")
about_template = env.get_template("about.html")

home_output = home_template.render(
    site_name="My Site",
    nav_items=[
        {"url": "/", "label": "Home"},
        {"url": "/about", "label": "About"},
    ],
    title="Welcome",
    message="This is a kida-powered site with template inheritance.",
)

about_output = about_template.render(
    site_name="My Site",
    nav_items=[
        {"url": "/", "label": "Home"},
        {"url": "/about", "label": "About"},
    ],
    title="About Us",
    description="Built with kida, the template engine for free-threaded Python.",
)


def main() -> None:
    print("=== Home Page ===")
    print(home_output)
    print()
    print("=== About Page ===")
    print(about_output)


if __name__ == "__main__":
    main()
