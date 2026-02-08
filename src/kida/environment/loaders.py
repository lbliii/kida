"""Template loaders for Kida environment.

Loaders provide template source to the Environment. They implement
`get_source(name)` returning `(source, filename)`.

Built-in Loaders:
- `FileSystemLoader`: Load from filesystem directories
- `DictLoader`: Load from in-memory dictionary (testing/embedded)
- `ChoiceLoader`: Try multiple loaders in order (theme fallback)
- `PrefixLoader`: Namespace templates by prefix (plugin architectures)
- `PackageLoader`: Load from installed Python packages (importlib.resources)
- `FunctionLoader`: Wrap a callable as a loader (quick one-offs)

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
delegate to their child loaders, PackageLoader reads via importlib,
FunctionLoader delegates to the user-provided callable).

"""

from __future__ import annotations

import importlib.resources
from collections.abc import Callable
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

    def __init__(
        self,
        loaders: list[
            FileSystemLoader
            | DictLoader
            | ChoiceLoader
            | PrefixLoader
            | PackageLoader
            | FunctionLoader
        ],
    ):
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
        mapping: dict[
            str,
            FileSystemLoader
            | DictLoader
            | ChoiceLoader
            | PrefixLoader
            | PackageLoader
            | FunctionLoader,
        ],
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


class PackageLoader:
    """Load templates from an installed Python package.

    Uses ``importlib.resources`` to locate template files inside a package's
    directory tree. This enables pip-installable packages to ship templates
    that are loadable without knowing the installation path.

    Use Cases:
        - Framework default templates (admin panels, error pages)
        - Distributable themes (``pip install my-theme``)
        - Plugin/extension templates namespaced by package

    Example:
            >>> # Package structure:
            >>> # my_app/
            >>> #   __init__.py
            >>> #   templates/
            >>> #     base.html
            >>> #     pages/
            >>> #       index.html
            >>> loader = PackageLoader("my_app", "templates")
            >>> env = Environment(loader=loader)
            >>> env.get_template("base.html")
            >>> env.get_template("pages/index.html")

    Args:
        package_name: Dotted Python package name (e.g. ``"my_app"``)
        package_path: Subdirectory within the package for templates
            (default: ``"templates"``)
        encoding: File encoding (default: ``"utf-8"``)

    Raises:
        TemplateNotFoundError: If template not found in package
        ModuleNotFoundError: If ``package_name`` is not installed

    Thread-Safety:
        Safe. ``importlib.resources`` is thread-safe for reads.
    """

    __slots__ = ("_encoding", "_package_name", "_package_path")

    def __init__(
        self,
        package_name: str,
        package_path: str = "templates",
        encoding: str = "utf-8",
    ):
        self._package_name = package_name
        self._package_path = package_path
        self._encoding = encoding

    def _get_root(self) -> importlib.resources.abc.Traversable:
        """Get the traversable root for the template directory."""
        root = importlib.resources.files(self._package_name)
        for part in self._package_path.split("/"):
            if part:
                root = root.joinpath(part)
        return root

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Load template source from package resources."""
        root = self._get_root()
        resource = root.joinpath(name)

        try:
            source = resource.read_text(self._encoding)
        except (FileNotFoundError, TypeError, IsADirectoryError):
            raise TemplateNotFoundError(
                f"Template '{name}' not found in package "
                f"'{self._package_name}/{self._package_path}'"
            )

        # Provide a meaningful filename for error messages
        filename = f"{self._package_name}/{self._package_path}/{name}"
        return source, filename

    def list_templates(self) -> list[str]:
        """List all templates in the package directory."""
        root = self._get_root()
        return sorted(self._walk(root, ""))

    def _walk(self, traversable: importlib.resources.abc.Traversable, prefix: str) -> list[str]:
        """Recursively walk a traversable, collecting file paths."""
        templates: list[str] = []
        try:
            for item in traversable.iterdir():
                name = f"{prefix}{item.name}" if not prefix else f"{prefix}/{item.name}"
                if item.is_file() and not item.name.startswith("."):
                    templates.append(name if prefix else item.name)
                elif item.is_dir() and not item.name.startswith((".", "__")):
                    templates.extend(self._walk(item, name if prefix else item.name))
        except (FileNotFoundError, TypeError):
            pass
        return templates


class FunctionLoader:
    """Wrap a callable as a template loader.

    The simplest way to create a custom loader. Pass a function that takes
    a template name and returns the source (or ``None`` if not found).

    The function can return either:
        - ``str``: Template source (filename will be ``"<function>"``).
        - ``tuple[str, str | None]``: ``(source, filename)`` for custom
          filenames in error messages.
        - ``None``: Template not found (raises ``TemplateNotFoundError``).

    Example:
            >>> def load(name):
            ...     if name == "greeting.html":
            ...         return "Hello, {{ name }}!"
            ...     return None
            >>> env = Environment(loader=FunctionLoader(load))
            >>> env.get_template("greeting.html").render(name="World")
            'Hello, World!'

    Use with tuple return for better error messages:
            >>> def load(name):
            ...     source = my_cms.get_template(name)
            ...     if source:
            ...         return source, f"cms://{name}"
            ...     return None
            >>> env = Environment(loader=FunctionLoader(load))

    Args:
        load_func: Callable that takes a template name and returns source
            string, ``(source, filename)`` tuple, or ``None``.

    Raises:
        TemplateNotFoundError: If ``load_func`` returns ``None``

    Thread-Safety:
        Safe if ``load_func`` is thread-safe.
    """

    __slots__ = ("_load_func",)

    def __init__(
        self,
        load_func: Callable[[str], str | tuple[str, str | None] | None],
    ):
        self._load_func = load_func

    def get_source(self, name: str) -> tuple[str, str | None]:
        """Call the load function and normalize the result."""
        result = self._load_func(name)

        if result is None:
            raise TemplateNotFoundError(f"Template '{name}' not found")

        if isinstance(result, str):
            return result, "<function>"

        # tuple[str, str | None]
        return result

    def list_templates(self) -> list[str]:
        """FunctionLoader cannot enumerate templates."""
        return []
