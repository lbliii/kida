"""Demo of template stack traces (Feature 2.1: Rich Error Messages).

Shows how Kida displays the full call chain when errors occur in nested templates.
"""

from pathlib import Path
from kida import Environment, FileSystemLoader

# Create temp directory with templates
demo_dir = Path("demo_templates")
demo_dir.mkdir(exist_ok=True)

# Create a chain: page.html → layout.html → nav.html (error here)
(demo_dir / "page.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
</head>
{% include "layout.html" %}
</html>
""".strip())

(demo_dir / "layout.html").write_text("""
<body>
    <div class="container">
        {% include "nav.html" %}
        <main>{{ content }}</main>
    </div>
</body>
""".strip())

(demo_dir / "nav.html").write_text("""
<nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
    <!-- Typo: should be 'username' not 'usernme' -->
    <span>Welcome, {{ usernme }}</span>
</nav>
""".strip())

# Set up environment
env = Environment(loader=FileSystemLoader(str(demo_dir)))
template = env.get_template("page.html")

try:
    # Try to render with missing variable
    html = template.render(title="Demo", content="Hello World", username="Alice")
except Exception as e:
    print("=" * 70)
    print("TEMPLATE ERROR WITH STACK TRACE")
    print("=" * 70)
    print(str(e))
    print("=" * 70)
    print("\nNotice the 'Template stack:' section showing:")
    print("  • page.html:7 (line where 'include layout.html' is)")
    print("  • layout.html:3 (line where 'include nav.html' is)")
    print("\nThis makes it easy to trace errors through nested templates!")

# Cleanup
import shutil
shutil.rmtree(demo_dir)
