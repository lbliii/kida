# FastAPI Integration

`render_stream_async()` with FastAPI's `StreamingResponse` for true streaming HTML delivery.

## Run

```bash
pip install fastapi uvicorn
cd examples/fastapi_async && uvicorn app:app --reload
```

## Test

```bash
pytest examples/fastapi_async/ -v
```

## What It Shows

- `StreamingResponse` with async template rendering
- Templates with `{% async for %}` consume async data
- Full and streaming endpoints produce same content
