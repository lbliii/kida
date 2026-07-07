# Flask Components

Add typed Kida components to an existing Flask app on Python 3.14+:

```bash
uv add flask kida-templates
uv run python app.py
```

Open <http://127.0.0.1:5000>. The GET route renders a typed component with a
default slot; the POST route renders only the `preview` block for an
HTML-over-the-wire update.

Run the non-network smoke path with:

```bash
uv run python app.py --smoke
```
