# Native Async Templates

`{% async for %}` consumes async iterables. `{{ await expr }}` resolves coroutines inline.

## Run

```bash
cd examples/async_rendering && python app.py
```

## Test

```bash
pytest examples/async_rendering/ -v
```

## What It Shows

- `{% async for item in async_iterable %}` — consume async iterables
- `{{ await coro }}` — resolve coroutines in expressions
- `render_stream_async()` — async generator for streaming
