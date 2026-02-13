# t-string Interpolation (Python 3.14+)

`k(t"Hello {name}!")` — zero-parser-overhead interpolation with auto-escaping.

## Requirements

Python 3.14+ (PEP 750 t-strings)

## Run

```bash
cd examples/t_string && python app.py
```

## Test

```bash
pytest examples/t_string/ -v
```

## What It Shows

- `k(t"...")` — process t-strings with HTML escaping
- No template compilation; ideal for high-frequency simple interpolation
- Auto-escaping: `k(t"<p>{user_input}</p>")` escapes `user_input`

## Usage

```python
from kida import k

name = "World"
k(t"Hello {name}!")  # "Hello World!"

user_input = "<script>"
k(t"<p>{user_input}</p>")  # "<p>&lt;script&gt;</p>"
```
