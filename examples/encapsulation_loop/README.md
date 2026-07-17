# Encapsulation Advice Loop

This example is a reproducible replay for humans and coding agents using Kida's
ordinary public analysis APIs. It needs no Kida-specific agent, prompt template,
catalog, MCP server, browser, or source-history integration.

## Run the replay

```bash
uv run python examples/encapsulation_loop/app.py
uv run python examples/encapsulation_loop/app.py --measure --rounds 5
```

The first command prints deterministic JSON whose `calibration` field matches
`calibration.json`. The optional measurement adds local timing without
contaminating that snapshot.

## Use the same loop

1. Call `advise_encapsulation_roots()` for explicitly owned roots and inspect
   each diagnostic's code, span, confidence, metadata, and related locations.
2. Choose one of three actions: extract the proposed boundary, inline a proven
   pass-through wrapper, or preserve a documented product/adapter boundary.
3. Run `diagnose_roots(..., validate_calls=True)` to validate props and slots.
4. Render before and after with the same context, including named response
   blocks when present.
5. Re-run advice and record false positives, false negatives, context effects,
   and analysis cost.

Kida supplies evidence; the consumer owns the architectural choice. The replay
therefore commits both source states instead of auto-editing ambiguous markup.

## Cases

| Case | Evidence-led decision | Protected result |
|---|---|---|
| Growing route | Extract `message_row` from the iterated interactive region. | `K-MOD-102` clears; props and the possible actions slot remain inspectable. |
| Healthy layout | Keep the large layout intact. | No size/loop false positive. |
| Pass-through component | Inline `save_button` and call `button` directly. | `K-MOD-103` clears without render drift. |
| Response boundary | Preserve `messages_oob`, extract only its nested row. | Adapter context exposes the nested candidate without removing the response block. |
| Multiple roots | Preserve the public app wrapper alongside a framework root. | Visibility context suppresses only the exact documented boundary. |

Every case checks rendered output, component inventory, call validation, exact
diagnostic evidence, and expected advice. The committed report records zero
false positives, false negatives, behavior-parity failures, or validation
failures.
