# FastAPI Components

Add typed Kida components to an existing FastAPI app on Python 3.14+:

```bash
uv add fastapi uvicorn kida-templates
uv run python app.py
```

Open <http://127.0.0.1:8000>. The GET route uses Kida's
`TemplateResponse()` adapter; the POST route renders only the `preview` block
and returns an `HTMLResponse`.

Run the non-network smoke path with:

```bash
uv run python app.py --smoke
```
