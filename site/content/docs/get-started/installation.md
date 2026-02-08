---
title: Installation
description: Install Kida using pip, uv, or from source
draft: false
weight: 10
lang: en
type: doc
tags:
- installation
keywords:
- install
- pip
- uv
- python 3.14
icon: download
---

# Installation

## Requirements

- **Python 3.14+** (required)
- No runtime dependencies (pure Python)

## Using pip

```bash
pip install kida-templates
```

## Using uv

```bash
uv add kida-templates
```

## From Source

```bash
git clone https://github.com/lbliii/kida.git
cd kida
pip install -e .
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/lbliii/kida.git
cd kida
uv sync
```

## Verify Installation

```python
import kida
print(kida.__version__)  # 0.1.2
```

Or from the command line:

```bash
python -c "import kida; print(kida.__version__)"
```

## Python 3.14t (Free-Threading)

Kida is optimized for Python 3.14t with free-threading enabled (PEP 703). To use free-threading:

1. Install the free-threaded Python 3.14 build (look for `python3.14t` or the "free-threaded" installer option)
2. Install Kida normally
3. Render templates concurrently with true parallelism

```python
from concurrent.futures import ThreadPoolExecutor
from kida import Environment

env = Environment()
template = env.from_string("Hello, {{ name }}!")

# On 3.14t, this runs with true parallelism (no GIL)
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(
        lambda n: template.render(name=n),
        ["Alice", "Bob", "Charlie", "Diana"]
    ))
```

See [[docs/about/thread-safety|Thread Safety]] for details on Kida's free-threading support.
