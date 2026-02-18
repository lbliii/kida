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

:::{checklist} Prerequisites
:show-progress:
- [ ] Python 3.14+ installed
- [x] No runtime dependencies (pure Python)
:::{/checklist}

## Install

:::{tab-set}
:::{tab-item} uv

```bash
uv add kida-templates
```

:::{/tab-item}

:::{tab-item} pip

```bash
pip install kida-templates
```

:::{/tab-item}

:::{tab-item} From Source

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

:::{/tab-item}
:::{/tab-set}

## Verify Installation

```python
import kida
print(kida.__version__)  # 0.2.2
```

Or from the command line:

```bash
python -c "import kida; print(kida.__version__)"
```

## Python 3.14t (Free-Threading)

Kida is optimized for Python 3.14t with free-threading enabled (PEP 703). To use free-threading:

:::{steps}
:::{step} Install free-threaded Python 3.14

Look for `python3.14t` or the "free-threaded" installer option.

:::{/step}
:::{step} Install Kida normally

Use pip or uv as shown above.

:::{/step}
:::{step} Render templates concurrently

Use true parallelism with `ThreadPoolExecutor` or similar.

:::{/step}
:::{/steps}

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

## Next Steps

:::{related}
:limit: 3
:section_title: Next Steps
:::
