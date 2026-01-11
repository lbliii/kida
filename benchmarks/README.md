# Kida Benchmarks

Benchmarks validate published performance claims and compare Kida to Jinja2.

## Setup

```bash
uv sync --group dev
```

## Running

- Render and scaling benchmarks:
  ```bash
  uv run pytest benchmarks/ --benchmark-only \
    --benchmark-json .benchmarks/render.json
  ```
- Cold-start suite:
  ```bash
  uv run python benchmarks/benchmark_cold_start.py
  ```
- Compare against a saved run:
  ```bash
  uv run pytest benchmarks/benchmark_render.py \
    --benchmark-compare
  ```

## Outputs

- Environment metadata is written to `.benchmarks/environment.json`.
- Use `--benchmark-json` to export structured results for ingestion.
- `.benchmarks/` is gitignored to keep local machine data out of history.
