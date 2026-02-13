# LLM Token Streaming

`{% async for %}` consuming a simulated LLM token stream. O(n) work instead of O(n²) re-render-per-token.

## Run

```bash
cd examples/llm_streaming && python app.py
```

## Test

```bash
pytest examples/llm_streaming/ -v
```

## What It Shows

- Async iterator as token stream
- Template renders progressively as tokens arrive
- `render_stream_async()` yields HTML chunks
- In production: wire to OpenAI, Anthropic, etc.
