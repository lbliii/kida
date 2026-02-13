# Free-Threading Proof

8 threads render different templates simultaneously with zero GIL contention.

## Run

```bash
cd examples/concurrent && python app.py
```

## Test

```bash
pytest examples/concurrent/ -v
```

## What It Shows

- `ThreadPoolExecutor` with concurrent renders
- Each thread gets its own render context
- No cross-contamination between simultaneous renders
- Python 3.14t free-threading readiness
