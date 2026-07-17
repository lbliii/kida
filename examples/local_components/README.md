# App-Owned Local Components

This framework-neutral example keeps typed Kida components, product patterns,
and ordinary CSS in one application. It uses no component package, token
runtime, frontend build, router, or JavaScript state.

## Run

From the repository root:

```bash
uv run python examples/local_components/app.py
uv run kida check \
  --root app=examples/local_components/templates \
  --validate-calls --a11y
uv run kida components \
  --root app=examples/local_components/templates \
  --json
```

The final command returns machine-readable component signatures, named slots,
logical template IDs, source ownership, and file locations.

## Boundaries

```text
templates/
  components/controls.html   # reusable controls with accessibility policy
  patterns/search-panel.html # product-specific composition and server state
  pages/search.html          # route composition and scoped result markup
static/
  tokens.css                 # app-owned semantic custom properties
  components.css             # app-owned component and pattern styles
```

`text_field` owns the label/input relationship and help association.
`submit_button` owns the submit and disabled-state policy. `search_panel` earns
a product-pattern boundary because it owns the search form, live result status,
empty state, iteration, and scoped `result` slot.

The result card stays inline in `pages/search.html`: it is route-specific
composition, introduces no independent policy, and is already replaceable
through the pattern's scoped slot. Extracting it would add a name without adding
an interface.

The query and result count are rendered on the server. The `role="status"` and
`aria-live="polite"` region announces the returned state without requiring a
client-side state model. The application—not Kida—owns the CSS variables,
layers, filenames, theme values, and asset delivery.

Framework adapters may supply additional explicitly namespaced roots and define
layout or response roles, but Kida core does not infer those conventions. The
pinned [Chirp downstream pilot](https://github.com/lbliii/kida/issues/280#issuecomment-5006187657)
proves that boundary without making this example framework-specific.
