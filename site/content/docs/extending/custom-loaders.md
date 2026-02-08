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

## Loader Protocol

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

See [[docs/usage/loading-templates|Loading Templates]] for more on `ChoiceLoader` and `PrefixLoader`.

## Caching Layer

Add caching to any loader:

```python
from functools import lru_cache

class CachedLoader:
    def __init__(self, loader, maxsize=128):
        self.loader = loader
        self._get_source = lru_cache(maxsize=maxsize)(
            self._get_source_uncached
        )

    def _get_source_uncached(self, name: str):
        return self.loader.get_source(name)

    def get_source(self, name: str) -> tuple[str, str | None]:
        return self._get_source(name)

    def list_templates(self) -> list[str]:
        return self.loader.list_templates()

    def clear_cache(self):
        self._get_source.cache_clear()

# Usage
env = Environment(
    loader=CachedLoader(DatabaseLoader(db), maxsize=256)
)
```

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

- [[docs/usage/loading-templates|Loading Templates]] — FileSystemLoader, DictLoader
- [[docs/reference/api|API Reference]] — Loader protocol
- [[docs/about/architecture|Architecture]] — Template compilation pipeline
