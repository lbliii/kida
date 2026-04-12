# RFC: `tojson` HTML-Attribute-Safe Mode

**Status**: Implemented  
**Created**: 2026-04-11  
**Related**: `src/kida/environment/filters/_type_conversion.py`, Chirp Alpine.js integration  
**Priority**: P2 (developer experience — prevents a common HTML-breaking footgun)  
**Affects**: kida-templates, bengal-chirp (Alpine.js users), chirp-ui

---

## Executive Summary

Kida's `tojson` filter wraps output in `Markup()` to prevent double-escaping. This is correct for `<script>` tags but produces broken HTML when used in element attributes, because the JSON double quotes conflict with the attribute delimiters.

Every server-rendered framework that integrates Alpine.js, Vue, or similar attribute-driven JS frameworks hits this. This RFC proposes adding an `attr=True` parameter to `tojson` that HTML-entity-encodes the output for safe embedding in double-quoted attributes.

| Change | Scope | Effort |
|--------|-------|--------|
| Add `attr` param to `_filter_tojson` | `_type_conversion.py` (~5 lines) | Trivial |
| Tests: attr mode, round-trip, edge cases | `tests/test_kida_filters.py` (~8 tests) | Low |
| Docs: filter reference + escaping guide | `site/content/docs/` | Low |

**Fully backward compatible** — `attr` defaults to `False`; existing usage is unchanged.

---

## Problem

### Current Implementation

`_filter_tojson` (`src/kida/environment/filters/_type_conversion.py:117-119`):

```python
def _filter_tojson(value: Any, indent: int | None = None) -> Markup:
    """Convert value to JSON string (marked safe to prevent escaping)."""
    return Markup(json.dumps(value, indent=indent, default=str))
```

The `Markup()` wrapper tells Kida's autoescaper "this string is already safe — do not escape it." This prevents `{"key": "value"}` from becoming `{&quot;key&quot;: &quot;value&quot;}` inside `<script>` tags, which is the correct behavior there.

### The Attribute Footgun

When `tojson` output is placed in an HTML attribute, the raw double quotes terminate the attribute prematurely:

```kida
<div x-data="game({{ config | tojson }})">
```

Renders as:

```html
<div x-data="game({"rows": 6, "cols": 8})">
```

The browser sees `x-data="game({"` as the attribute value, `rows` as a new attribute, and the rest as garbage. No error is raised — the HTML is silently malformed.

### How Other Frameworks Handle This

| Framework | Approach |
|-----------|----------|
| Flask/Jinja2 | `tojson` HTML-escapes `<`, `>`, `&`, `'` but NOT `"` — relies on `<script>` context |
| Django | `json_script` filter emits a `<script type="application/json">` tag (avoids the problem entirely) |
| Rails | `json_escape` / `j` helper that escapes for JS string context |
| Alpine.js docs | Recommend single-quoted attributes: `x-data='{{ json }}'` |

None of these solve the double-quoted HTML attribute case cleanly. Kida can.

### Real-World Impact

This was hit during the b-site matching game build. The template author (an AI agent) wrote:

```kida
<div x-data="matchGame({{ game_config | tojson }})">
```

The fix required restructuring to a `<script type="application/json">` tag + `alpine:init` listener — a 15-line boilerplate change for what should be a one-line template expression.

---

## Design

### `tojson(attr=True)`

Add an `attr` parameter that HTML-entity-encodes the JSON output:

```python
def _filter_tojson(
    value: Any,
    indent: int | None = None,
    attr: bool = False,
) -> Markup:
    """Convert value to JSON string (marked safe to prevent escaping).

    Args:
        value: Value to serialize as JSON.
        indent: JSON indentation level (None for compact).
        attr: If True, HTML-entity-encode the output for safe embedding
            in double-quoted HTML attributes. The output can be parsed
            back to JSON with standard browser APIs after the browser
            decodes the HTML entities.
    """
    raw = json.dumps(value, indent=indent, default=str)
    if attr:
        raw = (
            raw.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
    return Markup(raw)
```

### Usage

```kida
{# In a <script> tag — existing behavior, unchanged #}
<script type="application/json">{{ data | tojson }}</script>

{# In an HTML attribute — new attr mode #}
<div x-data="{{ config | tojson(attr=true) }}">

{# Single-quoted attribute — works today without attr mode #}
<div x-data='{{ config | tojson }}'>

{# Pretty-printed in <script> tag #}
<script>var config = {{ data | tojson(indent=2) }};</script>
```

### How `attr=True` Works in the Browser

The browser's HTML parser decodes `&quot;` → `"`, `&amp;` → `&`, `&lt;` → `<`, `&gt;` → `>` before passing the attribute value to JavaScript. Alpine.js (and any framework that reads `x-data` via `getAttribute()`) receives valid JSON:

```html
<!-- Server sends: -->
<div x-data="{&quot;rows&quot;: 6, &quot;cols&quot;: 8}">

<!-- Browser decodes attribute to: -->
<!-- getAttribute("x-data") === '{"rows": 6, "cols": 8}' -->

<!-- Alpine parses this as JSON — works correctly -->
```

### Why Not a Separate Filter?

A `tojson_attr` filter was considered but rejected:

1. **Discoverability** — users already know `tojson`; a flag is easier to find than a separate filter name.
2. **Consistency** — `tojson(indent=2)` already demonstrates the "one filter, options" pattern.
3. **Fewer imports** — no new name to register in custom environments.

### Why Not Always Entity-Encode?

Making entity-encoding the default would break existing `<script>` tag usage, where raw JSON is correct and entity-encoded JSON is wrong (JavaScript doesn't decode HTML entities). The `attr` flag makes the context explicit.

---

## Edge Cases

### Nested Quotes in Values

```python
{"message": 'He said "hello"'}
```

`json.dumps` produces `{"message": "He said \"hello\""}`. With `attr=True`:

```html
{&quot;message&quot;: &quot;He said \&quot;hello\&quot;&quot;}
```

The browser decodes to `{"message": "He said \"hello\""}` — valid JSON. The backslash escaping from `json.dumps` is preserved.

### Non-ASCII Characters

`json.dumps` defaults to `ensure_ascii=True`, so non-ASCII characters are emitted as `\uXXXX` escapes. If `ensure_ascii=False` is set explicitly, non-ASCII characters pass through unchanged. In either case, HTML entity encoding does not alter non-ASCII characters. No issue.

### None / Null Values

`json.dumps(None)` → `"null"`. No quotes to escape. Works in both modes.

### Large Objects

Entity encoding adds ~5 characters per `"` in the output. For large config objects, this increases attribute size. This is a documentation concern, not a blocker — large configs should use `<script type="application/json">` regardless.

---

## Testing Strategy

1. **Basic attr encoding**: `{"key": "value"}` → `{&quot;key&quot;: &quot;value&quot;}` with `attr=True`.
2. **Round-trip**: Verify that `html.unescape(tojson(data, attr=True))` produces valid JSON equal to the input.
3. **Nested quotes**: Values containing `"` are correctly double-escaped.
4. **Special HTML chars**: `<`, `>`, `&` in values are entity-encoded.
5. **Default mode unchanged**: `tojson(data)` without `attr` produces raw JSON (no entities).
6. **None handling**: `tojson(None, attr=True)` → `"null"`.
7. **Indent + attr**: `tojson(data, indent=2, attr=True)` produces indented, entity-encoded output.
8. **Markup type**: Output is `Markup` in both modes.
9. **No double-escape regression**: Existing `test_tojson_no_double_escape` still passes.

---

## Documentation Updates

### `site/content/docs/reference/filters.md`

Update the `tojson` section:

```markdown
### tojson

Convert a value to a JSON string.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `indent` | `int \| None` | `None` | JSON indentation level |
| `attr` | `bool` | `False` | HTML-entity-encode for safe use in attributes |

**In `<script>` tags** (default):
\```kida
<script type="application/json">{{ data | tojson }}</script>
\```

**In HTML attributes** (use `attr=true`):
\```kida
<div x-data="{{ config | tojson(attr=true) }}">
\```
```

### `site/content/docs/usage/escaping.md`

Add a section on JSON-in-attributes vs JSON-in-scripts, explaining why the two contexts need different encoding.

### Downstream: Chirp Alpine guide, chirp-ui CLAUDE.md

Update to recommend `tojson(attr=true)` for Alpine `x-data` attributes as an alternative to the `<script type="application/json">` pattern.

---

## Implementation Plan

1. Add `attr` parameter to `_filter_tojson` in `src/kida/environment/filters/_type_conversion.py`.
2. Add tests to `tests/test_kida_filters.py`.
3. Update filter reference docs.
4. Update escaping guide.
5. Notify downstream (Chirp, chirp-ui) to update their Alpine/tojson guidance.

Estimated effort: 1-2 hours including tests and docs.
