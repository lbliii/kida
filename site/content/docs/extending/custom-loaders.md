---
title: Custom Loaders
description: Build custom template loaders
draft: false
weight: 40
lang: en
type: doc
tags:
- extending
- loaders
keywords:
- custom loaders
- extending
- database
icon: folder
---

# Custom Loaders

Build custom loaders to load templates from databases, APIs, or other sources.

## Quick Option: FunctionLoader

For simple cases, wrap a callable with the built-in `FunctionLoader` instead of writing a full class:

```python
from kida import Environment, FunctionLoader

# Simple dict lookup
templates = {"page.html": "<h1>{{ title }}</h1>"}
env = Environment(loader=FunctionLoader(lambda name: templates.get(name)))

# CMS integration in 3 lines
def load_from_cms(name):
    source = cms_client.get(f"templates/{name}")
    return (source, f"cms://{name}") if source else None

env = Environment(loader=FunctionLoader(load_from_cms))
```

Return `str` for source only, `tuple[str, str | None]` for source + filename, or `None` if not found.

## Full Custom Loader

For complex loaders with state, implement the Loader protocol.

### Loader Protocol

Implement two methods:

```python
class Loader:
    def get_source(self, name: str) -> tuple[str, str | None]:
        """Return (source, filename) for template."""
        ...

    def list_templates(self) -> list[str]:
        """Return list of all template names."""
        ...
```

## Database Loader

Load templates from a database:

```python
from kida import Environment, TemplateNotFoundError

class DatabaseLoader:
    def __init__(self, connection):
        self.conn = connection

    def get_source(self, name: str) -> tuple[str, str | None]:
        row = self.conn.execute(
            "SELECT source FROM templates WHERE name = ?",
            (name,)
        ).fetchone()

        if not row:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        # Return (source, filename for error messages)
        return row[0], f"db://{name}"

    def list_templates(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM templates"
        ).fetchall()
        return sorted(row[0] for row in rows)

# Usage
env = Environment(loader=DatabaseLoader(db_connection))
template = env.get_template("page.html")
```

## Redis Loader

Load templates from Redis:

```python
import redis
from kida import TemplateNotFoundError

class RedisLoader:
    def __init__(self, host="localhost", port=6379, prefix="templates:"):
        self.client = redis.Redis(host=host, port=port)
        self.prefix = prefix

    def get_source(self, name: str) -> tuple[str, str | None]:
        key = f"{self.prefix}{name}"
        source = self.client.get(key)

        if source is None:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        return source.decode("utf-8"), f"redis://{key}"

    def list_templates(self) -> list[str]:
        pattern = f"{self.prefix}*"
        keys = self.client.keys(pattern)
        return sorted(k.decode().removeprefix(self.prefix) for k in keys)

# Usage
env = Environment(loader=RedisLoader())
```

## HTTP Loader

Load templates from a remote server:

```python
import httpx
from kida import TemplateNotFoundError

class HTTPLoader:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client()

    def get_source(self, name: str) -> tuple[str, str | None]:
        url = f"{self.base_url}/{name}"

        try:
            response = self.client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        return response.text, url

    def list_templates(self) -> list[str]:
        # Could fetch index from server
        return []

# Usage
env = Environment(loader=HTTPLoader("https://templates.example.com"))
```

## Combining with Built-in Loaders

Kida ships with `ChoiceLoader` and `PrefixLoader` that work with any loader (including custom ones):

```python
from kida import ChoiceLoader, PrefixLoader, FileSystemLoader

# Try database first, then filesystem
env = Environment(
    loader=ChoiceLoader([
        DatabaseLoader(db),
        FileSystemLoader("templates/"),
    ])
)

# Namespace by prefix
env = Environment(
    loader=PrefixLoader({
        "db": DatabaseLoader(db),
        "files": FileSystemLoader("templates/"),
    })
)

# Loads from database
env.get_template("db/page.html")

# Loads from filesystem
env.get_template("files/base.html")
```

See [[docs/usage/loading-templates|Loading Templates]] for more on built-in loaders.

## Caching Layer

Add caching to any loader:

```python
import threading

class CachedLoader:
    def __init__(self, loader, maxsize=128):
        self.loader = loader
        self._cache: dict[str, tuple[str, str | None]] = {}
        self._lock = threading.Lock()
        self._maxsize = maxsize

    def get_source(self, name: str) -> tuple[str, str | None]:
        if name in self._cache:
            return self._cache[name]
        with self._lock:
            if name in self._cache:
                return self._cache[name]
            result = self.loader.get_source(name)
            if len(self._cache) >= self._maxsize:
                self._cache.pop(next(iter(self._cache)))
            self._cache[name] = result
            return result

    def list_templates(self) -> list[str]:
        return self.loader.list_templates()

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

# Usage
env = Environment(
    loader=CachedLoader(DatabaseLoader(db), maxsize=256)
)
```

> **Thread safety**: This uses a lock-based double-check pattern instead of `functools.lru_cache`, which is not thread-safe under free-threaded Python (3.13t+). See [[docs/about/thread-safety|Thread Safety]] for more on concurrent access patterns.

## Thread Safety

Loaders should be thread-safe:

```python
import threading

class ThreadSafeLoader:
    def __init__(self, loader):
        self.loader = loader
        self._lock = threading.Lock()

    def get_source(self, name: str) -> tuple[str, str | None]:
        with self._lock:
            return self.loader.get_source(name)

    def list_templates(self) -> list[str]:
        with self._lock:
            return self.loader.list_templates()
```

## Best Practices

### Raise TemplateNotFoundError

```python
from kida import TemplateNotFoundError

def get_source(self, name):
    if not self._exists(name):
        # ✅ Raise proper exception
        raise TemplateNotFoundError(f"Template '{name}' not found")

    # ❌ Don't return None
    # return None
```

### Include Source Location

```python
def get_source(self, name):
    source = self._load(name)
    # Include meaningful filename for error messages
    filename = f"db://{name}"  # or full path, URL, etc.
    return source, filename
```

### Handle Encoding

```python
def get_source(self, name):
    data = self._load_bytes(name)
    source = data.decode("utf-8")  # Handle encoding
    return source, name
```

## See Also

- [[docs/usage/loading-templates|Loading Templates]] — All built-in loaders (FileSystemLoader, DictLoader, ChoiceLoader, PrefixLoader, PackageLoader, FunctionLoader)
- [[docs/reference/api|API Reference]] — Loader protocol and API
- [[docs/about/architecture|Architecture]] — Template compilation pipeline
