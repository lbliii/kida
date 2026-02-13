# Fragment Caching

Built-in `{% cache key %}` directive caches expensive template fragments.

## Run

```bash
cd examples/caching && python app.py
```

## Test

```bash
pytest examples/caching/ -v
```

## What It Shows

- `{% cache "key" %}...{% end %}` — cache block output
- Second render hits the cache — no recomputation
- Optional `ttl=` for time-to-live
