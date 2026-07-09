# Render Capture and Manifests

The preferred build-tool workflow for capturing rendered blocks and selected
context, accumulating page captures in a manifest, comparing builds, inspecting
site-scoped freeze-cache candidates, and deriving a search manifest.

## Run

```bash
cd examples/render_capture_manifest
python app.py
```

## Test

```bash
pytest examples/render_capture_manifest/ -v
```

The example uses only names exported from the root `kida` package. Capture is
compiled in explicitly with `Environment(enable_capture=True)` and activated for
one render at a time with `captured_render()`.
