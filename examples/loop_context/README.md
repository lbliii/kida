# Loop Context — loop.first, loop.last, loop.index, loop.length

The `loop` variable in `{% for %}` blocks provides iteration metadata.

## Run

```bash
cd examples/loop_context && python app.py
```

## Test

```bash
pytest examples/loop_context/ -v
```

## What It Shows

- `loop.first` — True on first iteration
- `loop.last` — True on last iteration
- `loop.index` — 1-based index (1, 2, 3, ...)
- `loop.length` — total number of items

## Template Usage

```kida
{% for item in items %}
<tr class="{% if loop.first %}first{% end %} {% if loop.last %}last{% end %}">
    <td>{{ loop.index }}/{{ loop.length }}</td>
    <td>{{ item }}</td>
</tr>
{% end %}
```
