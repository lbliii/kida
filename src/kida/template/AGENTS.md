<!-- generated from .stewards/manifest.toml — edit the manifest, not this file -->

# Steward: template

Preserve compiled template execution across full, block, inherited, streaming, async, cached, and introspection paths.

Ordinary work: use this map directly with the root map and run only affected checks.
Do not open `.stewards/PROTOCOL.md` or `.stewards/manifest.toml` unless the task is an explicit review/audit or steward-network maintenance.

## Protects

| Invariant | Sev | Backing | Proof / anchor |
| --- | --- | --- | --- |
| Full, block, inherited, streaming, async, and composition paths share setup and intended output semantics. | P0 | machine-backed | `uv run pytest tests/test_render_mode_plans.py tests/test_render_surface_parity.py tests/test_render_block.py tests/test_render_with_blocks.py tests/test_render_stream.py tests/test_kida_async_rendering.py -q` (`runtime-suite`) |
| Render context, buffers, cached blocks, and async helpers retain local or synchronized state ownership. | P0 | machine-backed | `PYTHON_GIL=0 uv run pytest tests/test_render_surface_parity.py tests/test_sandbox_fuzz.py tests/test_bytecode_cache_concurrency.py tests/test_lru_cache_concurrency.py tests/test_kida_stress_test.py tests/test_randomized_thread_stress.py -q --tb=short` (`safety-suite`) |

## Guardrails

- Render surfaces share setup, validation, escaping, and source-attributed failure behavior unless a difference is explicit and tested.
- Cached blocks preserve key/invalidation semantics and introduce no hidden mutable cross-template state.

## Edges

- executes → **compiler** (compiled functions)
- specialized-by → **terminal** (terminal surface)
- specialized-by → **markdown** (markdown surface)

## Owns

- **code:** `src/kida/template/`, `src/kida/render_context.py`, `src/kida/render_accumulator.py`, `src/kida/composition.py`
- **tests:** `tests/test_render_surface_parity.py`, `tests/test_render_block.py`, `tests/test_render_stream.py`
- **docs:** `site/content/docs/usage/rendering-contexts.md`, `site/content/docs/usage/streaming.md`
