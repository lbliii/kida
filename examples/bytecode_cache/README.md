# Bytecode Cache — Cold Start Optimization

`BytecodeCache` compiles templates to Python bytecode on first load. Second load skips parser and compiler.

## Run

```bash
cd examples/bytecode_cache && python app.py
```

## Test

```bash
pytest examples/bytecode_cache/ -v
```

## What It Shows

- `BytecodeCache(cache_dir)` — persist compiled templates to disk
- Faster cold-start for large template sets
- Cache keyed by template name + source hash
