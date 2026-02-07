"""Template loaders for Kida environment.

Loaders provide template source to the Environment. They implement
`get_source(name)` returning `(source, filename)`.

Built-in Loaders:
- `FileSystemLoader`: Load from filesystem directories
- `DictLoader`: Load from in-memory dictionary (testing/embedded)
- `ChoiceLoader`: Try multiple loaders in order (theme fallback)
- `PrefixLoader`: Namespace templates by prefix (plugin architectures)

Custom Loaders:
Implement the Loader protocol:
    ```python
    class DatabaseLoader:
        def get_source(self, name: str) -> tuple[str, str | None]:
            row = db.query("SELECT source FROM templates WHERE name = ?", name)
            if not row:
                raise TemplateNotFoundError(f"Template '{name}' not found")
            return row.source, f"db://{name}"

        def list_templates(self) -> list[str]:
            return [r.name for r in db.query("SELECT name FROM templates")]
    ```

Thread-Safety:
Loaders should be thread-safe for concurrent `get_source()` calls.
All built-in loaders are safe (FileSystemLoader reads files atomically,
DictLoader uses immutable dict lookup, ChoiceLoader and PrefixLoader
delegate to their child loaders).

"""

from __future__ import annotations

from pathlib import Path

from kida.environment.exceptions import TemplateNotFoundError


class FileSystemLoader:
    """Load templates from filesystem directories.

    Searches one or more directories for templates by name. The first matching
    file is returned. Supports arbitrary directory structures and file nesting.

    Attributes:
        _paths: List of Path objects to search
        _encoding: File encoding (default: utf-8)

    Methods:
        get_source(name): Return (source, filename) for template
        list_templates(): Return sorted list of all template names

    Search Order:
        Directories are searched in order. First match wins:
            ```python
            loader = FileSystemLoader(["themes/custom/", "themes/default/"])
            # Looks in themes/custom/ first, then themes/default/
            ```

    Example:
            >>> loader = FileSystemLoader("templates/")
            >>> source, filename = loader.get_source("pages/about.html")
            >>> print(filename)
            'templates/pages/about.html'

            >>> loader = FileSystemLoader(["site/", "shared/"])
            >>> loader.list_templates()
        ['base.html', 'components/card.html', 'pages/home.html']

    Raises:
        TemplateNotFoundError: If template not found in any search path

    """

    __slots__ = ("_encoding", "_paths")

    def __init__(
        self,
        paths: str | Path | list[str | Path],
        encoding: str = "utf-8",
    ):
        if isinstance(paths, (str, Path)):
            paths = [paths]
        self._paths = [Path(p) for p in paths]
        self._encoding = encoding

    def get_source(self, name: str) -> tuple[str, str]:
        """Load template source from filesystem."""
        for base in self._paths:
            path = base / name
            if path.is_file():
                return path.read_text(self._encoding), str(path)

        raise TemplateNotFoundError(
            f"Template '{name}' not found in: {', '.join(str(p) for p in self._paths)}"
        )

    def list_templates(self) -> list[str]:
        """List all templates in search paths."""
        templates = set()
        for base in self._paths:
            if base.is_dir():
                for path in base.rglob("*.html"):
                    templates.add(str(path.relative_to(base)))
                for path in base.rglob("*.xml"):
                    templates.add(str(path.relative_to(base)))
        return sorted(templates)


class DictLoader:
    """Load templates from an in-memory dictionary.

    Maps template names to source strings. Useful for testing, embedded
    templates, or dynamically generated templates.

    Attributes:
        _mapping: Dict mapping template name → source string

    Methods:
        get_source(name): Return (source, None) for template
        list_templates(): Return sorted list of template names

    Note:
        Returns `None` as filename since templates are not file-backed.
        Error messages will show `<template>` instead of a path.

    Example:
            >>> loader = DictLoader({
            ...     "base.html": "<html>{% block content %}{% end %}</html>",
            ...     "page.html": "{% extends 'base.html' %}{% block content %}Hi{% end %}",
            ... })
            >>> env = Environment(loader=loader)
            >>> env.get_template("page.html").render()
            '<html>Hi</html>'

    Testing:
            >>> loader = DictLoader({"test.html": "{{ x * 2 }}"})
            >>> env = Environment(loader=loader)
            >>> assert env.render("test.html", x=21) == "42"

    Raises:
        TemplateNotFoundError: If template name not in mapping

    """

    __slots__ = ("_mapping",)

    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    def get_source(self, name: str) -> tuple[str, None]:
        if name not in self._mapping:
            from difflib import get_close_matches

            available = sorted(self._mapping.keys())
            msg = f"Template '{name}' not found"
            matches = get_close_matches(name, available, n=1, cutoff=0.6)
            if matches:
                msg += f". Did you mean '{matches[0]}'?"
            elif available:
                msg += f". Available: {', '.join(available[:10])}"
                if len(available) > 10:
                    msg += f" ... ({len(available)} total)"
            raise TemplateNotFoundError(msg)
        return self._mapping[name], None

    def list_templates(self) -> list[str]:
        return sorted(self._mapping.keys())


class ChoiceLoader:
    """Try multiple loaders in order, returning the first match.

    Useful for theme fallback patterns where a custom theme overrides
    a subset of templates and the default theme provides the rest.

    Search Order:
        Loaders are tried in order. First successful ``get_source()`` wins:
            ```python
            loader = ChoiceLoader([
                FileSystemLoader("themes/custom/"),
                FileSystemLoader("themes/default/"),
            ])
            # Looks in custom/ first, then default/
            ```

    Example:
            >>> custom = DictLoader({"nav.html": "<nav>Custom</nav>"})
            >>> default = DictLoader({
            ...     "nav.html": "<nav>Default</nav>",
            ...     "footer.html": "<footer>Default</footer>",
            ... })
            >>> loader = ChoiceLoader([custom, default])
            >>> env = Environment(loader=loader)
            >>> env.get_template("nav.html").render()     # from custom
            '<nav>Custom</nav>'
            >>> env.get_template("footer.html").render()  # from default
            '<footer>Default</footer>'

    Raises:
        TemplateNotFoundError: If no loader can find the template

    Thread-Safety:
        Safe if all child loaders are thread-safe.
    """

    __slots__ = ("_loaders",)

    def __init__(self, loaders: list[FileSystemLoader | DictLoader | ChoiceLoader | PrefixLoader]):
        self._loaders = loaders

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Try each loader in order, return first match."""
        for loader in self._loaders:
            try:
                return loader.get_source(name)
            except TemplateNotFoundError:
                continue
        raise TemplateNotFoundError(
            f"Template '{name}' not found in any of {len(self._loaders)} loaders"
        )

    def list_templates(self) -> list[str]:
        """Merge template lists from all loaders (deduplicated, sorted)."""
        templates: set[str] = set()
        for loader in self._loaders:
            if hasattr(loader, "list_templates"):
                templates.update(loader.list_templates())
        return sorted(templates)


class PrefixLoader:
    """Namespace templates by prefix, delegating to per-prefix loaders.

    Template names are split on a delimiter (default ``/``) and the first
    segment is used to select the appropriate loader. This enables plugin
    and theme architectures where different template sources are isolated
    by namespace.

    Example:
            >>> loader = PrefixLoader({
            ...     "app": FileSystemLoader("templates/app/"),
            ...     "admin": FileSystemLoader("templates/admin/"),
            ...     "shared": DictLoader({"header.html": "<header>Shared</header>"}),
            ... })
            >>> env = Environment(loader=loader)
            >>> env.get_template("app/index.html")     # FileSystemLoader("templates/app/")
            >>> env.get_template("shared/header.html") # DictLoader
            >>> env.get_template("admin/users.html")   # FileSystemLoader("templates/admin/")

    Raises:
        TemplateNotFoundError: If prefix not found or template not in loader

    Thread-Safety:
        Safe if all child loaders are thread-safe.
    """

    __slots__ = ("_delimiter", "_mapping")

    def __init__(
        self,
        mapping: dict[str, FileSystemLoader | DictLoader | ChoiceLoader | PrefixLoader],
        delimiter: str = "/",
    ):
        self._mapping = mapping
        self._delimiter = delimiter

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Split name on delimiter, look up prefix, delegate to loader."""
        if self._delimiter in name:
            prefix, rest = name.split(self._delimiter, 1)
        else:
            prefix = name
            rest = ""

        loader = self._mapping.get(prefix)
        if loader is None:
            available_prefixes = sorted(self._mapping.keys())
            raise TemplateNotFoundError(
                f"Template '{name}': no loader for prefix '{prefix}'. "
                f"Available prefixes: {', '.join(available_prefixes)}"
            )
        return loader.get_source(rest)

    def list_templates(self) -> list[str]:
        """List all templates across all prefixes, with prefix prepended."""
        templates: list[str] = []
        for prefix, loader in sorted(self._mapping.items()):
            if hasattr(loader, "list_templates"):
                templates.extend(
                    f"{prefix}{self._delimiter}{name}" for name in loader.list_templates()
                )
        return sorted(templates)
