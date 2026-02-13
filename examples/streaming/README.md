# Chunked Rendering

`render_stream()` yields template output as chunks at statement boundaries.

## Run

```bash
cd examples/streaming && python app.py
```

## Test

```bash
pytest examples/streaming/ -v
```

## What It Shows

- `template.render_stream(**ctx)` — generator yielding chunks
- Ideal for chunked HTTP responses and Server-Sent Events
- Chunks align with statement boundaries
