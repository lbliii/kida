"""Demo of colored error messages (Feature 2.1 Phase 2: Terminal Colors).

Shows how Kida displays beautiful, colorized error messages that are easy to read.
Colors are automatically enabled when running in a TTY and respect NO_COLOR.
"""

import os
from pathlib import Path
from kida import Environment, FileSystemLoader

# Force colors for this demo (override TTY detection)
os.environ["FORCE_COLOR"] = "1"

# Re-import after setting env var to pick up the change
import importlib
from kida.environment import terminal
importlib.reload(terminal)

# Create temp directory with templates
demo_dir = Path("demo_colored_templates")
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

print("=" * 80)
print("COLORED ERROR MESSAGE DEMO")
print("=" * 80)
print()
print("Notice the colors:")
print("  • Error codes: Bright red + bold")
print("  • Locations: Cyan")
print("  • Error lines: Bright red highlighting")
print("  • Hints: Green")
print("  • Suggestions: Bright green + bold")
print("  • Stack traces: Dimmed text with cyan locations")
print()
print("=" * 80)
print()

try:
    # Try to render with missing variable
    html = template.render(title="Demo", content="Hello World", username="Alice")
except Exception as e:
    # Use format_compact() for the nicest output
    print(e.format_compact())

print()
print("=" * 80)
print("To disable colors, set NO_COLOR=1 environment variable")
print("=" * 80)

# Cleanup
import shutil
shutil.rmtree(demo_dir)
