"""Template Bytecode Cache.

Persists compiled template code objects to disk for near-instant
cold-start loading. Uses marshal for code object serialization and
pickle for optional AST serialization.

Cache Invalidation:
Uses source hash in filename. When source changes, hash changes,
and old cache entry becomes orphan (cleaned up lazily).

Thread-Safety:
File writes use atomic rename pattern to prevent corruption.
Multiple processes can safely share the cache directory.

Example:
    >>> from pathlib import Path
    >>> from kida.bytecode_cache import BytecodeCache, hash_source
    >>>
    >>> cache = BytecodeCache(Path(".kida-cache"))
    >>>
    >>> # Check cache
    >>> code, ast, precomputed = cache.get("base.html", source_hash)
    >>> if code is None:
    ...     code = compile_template(source)
    ...     cache.set("base.html", source_hash, code)
    >>>
    >>> # Cache stats
    >>> stats = cache.stats()
    >>> print(f"Cached: {stats['file_count']} templates")

"""

from __future__ import annotations

import contextlib
import hashlib
import marshal
import pickle
import struct
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, cast

from kida.utils.template_keys import normalize_template_name

if TYPE_CHECKING:
    from types import CodeType

    from kida.nodes.base import Node

# Magic sentinel that prefixes the framed cache format (v2).
# Marshal code objects always start with 0xe3 (the TYPE_CODE byte), so this
# 4-byte sentinel — which starts with 0x00 — is unambiguous.
_FRAMED_MAGIC = b"\x00KDA"

# v3 magic: includes precomputed constants section for partial evaluator.
# Format: magic(4) + code_len(4) + code + pc_len(4) + pickle(precomputed) + pickle(ast)?
# pc_len is 0 when there are no precomputed values.
_FRAMED_MAGIC_V3 = b"\x01KDA"

# Python version tag for cache invalidation across Python upgrades
_PY_VERSION_TAG = f"py{sys.version_info.major}{sys.version_info.minor}"


class BytecodeCache:
    """Persist compiled template bytecode to disk.

    Uses marshal for code object serialization (Python stdlib).

    Thread-Safety:
        File writes use atomic rename pattern to prevent corruption.
        Multiple processes can safely share the cache directory.

    Cache Invalidation:
        Uses source hash in filename. When source changes, hash changes,
        and old cache entry becomes orphan (cleaned up lazily).

    Example:
            >>> cache = BytecodeCache(Path(".kida-cache"))
            >>>
            >>> # Miss: compile and cache
            >>> code, ast, precomputed = cache.get("base.html", source_hash)
            >>> if code is None:
            ...     code = compile_template(source)
            ...     cache.set("base.html", source_hash, code, ast=optimized_ast)
            >>>
            >>> # Hit: instant load (ast may be None for old cache entries)
            >>> code, ast, precomputed = cache.get("base.html", source_hash)

    """

    def __init__(
        self,
        directory: Path,
        pattern: str = "__kida_{version}_{name}_{hash}.pyc",
    ):
        """Initialize bytecode cache.

        Args:
            directory: Cache directory (created if missing)
            pattern: Filename pattern with {version}, {name}, {hash} placeholders
        """
        self._dir = directory
        self._pattern = pattern
        self._dir.mkdir(parents=True, exist_ok=True)

    def _make_path(self, name: str, source_hash: str, context_hash: str | None = None) -> Path:
        """Generate cache file path.

        Includes Python version in filename to prevent cross-version
        bytecode incompatibility (marshal format is version-specific).
        """
        name = normalize_template_name(name)
        # Sanitize name for filesystem
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        hash_key = source_hash[:16]
        if context_hash:
            hash_key = f"{hash_key}_{context_hash[:16]}"
        filename = self._pattern.format(
            version=_PY_VERSION_TAG,
            name=safe_name,
            hash=hash_key,
        )
        return self._dir / filename

    def get(
        self,
        name: str,
        source_hash: str,
        *,
        context_hash: str | None = None,
    ) -> tuple[CodeType, Node | None, list | None] | tuple[None, None, None]:
        """Load cached bytecode, optional AST, and precomputed constants.

        The cache file may contain either:
        - Legacy format: raw marshal-encoded code object only.
        - v2 format: ``_FRAMED_MAGIC`` sentinel, code length, code, optional AST.
        - v3 format: ``_FRAMED_MAGIC_V3`` sentinel, code length, code,
          precomputed length, precomputed constants, optional AST.

        Args:
            name: Template name
            source_hash: Hash of template source (for invalidation)

        Returns:
            ``(code, ast, precomputed)`` on a cache hit — ``ast`` and
            ``precomputed`` may be ``None``.  Returns ``(None, None, None)``
            on a cache miss or read error.
        """
        path = self._make_path(name, source_hash, context_hash)

        if not path.exists():
            return None, None, None

        try:
            data = path.read_bytes()
        except OSError:
            return None, None, None

        try:
            if data[: len(_FRAMED_MAGIC_V3)] == _FRAMED_MAGIC_V3:
                # Framed format (v3): magic(4) + code_len(4) + code
                #                     + pc_len(4) + pickle(precomputed)
                #                     + pickle(ast)?
                offset = len(_FRAMED_MAGIC_V3)
                (code_len,) = struct.unpack_from("<I", data, offset)
                offset += 4
                code_bytes = data[offset : offset + code_len]
                if len(code_bytes) != code_len:
                    with contextlib.suppress(OSError):
                        path.unlink(missing_ok=True)
                    return None, None, None

                code = cast("CodeType", marshal.loads(code_bytes))
                offset += code_len

                # Precomputed section — if present but corrupted, treat as
                # cache miss so the template is recompiled with valid _pc_N
                # bindings (returning code without precomputed would cause
                # NameError at render time).
                if len(data) - offset < 4:
                    with contextlib.suppress(OSError):
                        path.unlink(missing_ok=True)
                    return None, None, None

                (pc_len,) = struct.unpack_from("<I", data, offset)
                offset += 4
                precomputed: list | None = None
                if pc_len > 0:
                    pc_bytes = data[offset : offset + pc_len]
                    if len(pc_bytes) != pc_len:
                        with contextlib.suppress(OSError):
                            path.unlink(missing_ok=True)
                        return None, None, None
                    try:
                        precomputed = pickle.loads(pc_bytes)
                    except Exception:
                        with contextlib.suppress(OSError):
                            path.unlink(missing_ok=True)
                        return None, None, None
                    offset += pc_len

                # AST section (optional)
                ast_bytes = data[offset:]
                ast: Node | None = None
                if ast_bytes:
                    try:
                        ast = pickle.loads(ast_bytes)
                    except Exception:
                        ast = None

                return code, ast, precomputed

            elif data[: len(_FRAMED_MAGIC)] == _FRAMED_MAGIC:
                # Framed format (v2): magic(4) + code_len(4 LE) + code + pickle(ast)?
                offset = len(_FRAMED_MAGIC)
                (code_len,) = struct.unpack_from("<I", data, offset)
                offset += 4
                code_bytes = data[offset : offset + code_len]
                if len(code_bytes) != code_len:
                    # Truncated file — discard and signal miss.
                    with contextlib.suppress(OSError):
                        path.unlink(missing_ok=True)
                    return None, None, None

                code = cast("CodeType", marshal.loads(code_bytes))

                # AST section is optional; absence means preserve_ast was False
                # when the entry was written.
                ast_bytes = data[offset + code_len :]
                ast = None
                if ast_bytes:
                    try:
                        ast = pickle.loads(ast_bytes)
                    except Exception:
                        # Corrupted or incompatible pickle — signal re-parse
                        # by returning None for the AST (code is still valid).
                        ast = None

                return code, ast, None
            else:
                # Legacy format: plain marshal stream, no AST.
                code = cast("CodeType", marshal.loads(data))
                return code, None, None
        except ValueError, EOFError, struct.error:
            # Corrupted or incompatible cache file
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
            return None, None, None

    def set(
        self,
        name: str,
        source_hash: str,
        code: CodeType,
        *,
        context_hash: str | None = None,
        ast: Node | None = None,
        precomputed: list | None = None,
    ) -> None:
        """Cache compiled bytecode, optional precomputed constants, and optional AST.

        File format (v3, framed):
        ``[_FRAMED_MAGIC_V3 (4 B)][code_len (4 B)][marshal(code)]``
        ``[pc_len (4 B)][pickle(precomputed)?][pickle(ast)?]``

        When ``precomputed`` is ``None`` or empty, ``pc_len`` is 0 and the
        pickle section is omitted.  Falls back to v2 format when no
        precomputed values are present.

        Args:
            name: Template name
            source_hash: Hash of template source
            code: Compiled code object
            ast: Optimised AST root node (optional).
            precomputed: Non-constant-safe values folded by partial eval.
        """
        path = self._make_path(name, source_hash, context_hash)
        tmp_path: Path | None = None

        try:
            code_bytes = marshal.dumps(code)
            try:
                pc_bytes = pickle.dumps(precomputed, protocol=5) if precomputed else b""
            except Exception:
                # Non-picklable precomputed values (e.g. custom objects) —
                # fall back to v2 format without precomputed section.
                pc_bytes = b""
            use_v3 = bool(pc_bytes)

            # Write to a unique temp file in the same directory, then atomically
            # replace the target path. Unique temp naming prevents producer races.
            with NamedTemporaryFile(
                mode="wb",
                dir=self._dir,
                prefix=f"{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                tmp_path = Path(f.name)
                if use_v3:
                    # v3 format: includes precomputed section
                    f.write(_FRAMED_MAGIC_V3)
                    f.write(struct.pack("<I", len(code_bytes)))
                    f.write(code_bytes)
                    f.write(struct.pack("<I", len(pc_bytes)))
                    f.write(pc_bytes)
                else:
                    # v2 format: no precomputed
                    f.write(_FRAMED_MAGIC)
                    f.write(struct.pack("<I", len(code_bytes)))
                    f.write(code_bytes)
                if ast is not None:
                    f.write(pickle.dumps(ast, protocol=5))

            # Atomic replacement
            tmp_path.replace(path)
        except OSError:
            # Best effort - caching failure shouldn't break compilation
            with contextlib.suppress(OSError):
                if tmp_path is not None:
                    tmp_path.unlink(missing_ok=True)

    def clear(self, current_version_only: bool = False) -> int:
        """Remove cached bytecode.

        Args:
            current_version_only: If True, only clear current Python version's cache

        Returns:
            Number of files removed
        """
        count = 0
        pattern = f"__kida_{_PY_VERSION_TAG}_*.pyc" if current_version_only else "__kida_*.pyc"
        for path in self._dir.glob(pattern):
            try:
                path.unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
        return count

    def cleanup(self, max_age_days: int = 30) -> int:
        """Remove orphaned cache files older than max_age_days.

        Orphaned files are cache entries that are no longer referenced by
        active templates (e.g., after source changes or template deletion).

        Args:
            max_age_days: Maximum age in days before removal (default: 30)

        Returns:
            Number of files removed

        Example:
            >>> cache = BytecodeCache(Path(".kida-cache"))
            >>> removed = cache.cleanup(max_age_days=7)  # Remove files older than 7 days
            >>> print(f"Removed {removed} orphaned cache files")
        """
        threshold = time.time() - (max_age_days * 86400)
        count = 0

        for path in self._dir.glob("__kida_*.pyc"):
            try:
                if path.stat().st_mtime < threshold:
                    path.unlink(missing_ok=True)
                    count += 1
            except OSError:
                # Skip files that can't be accessed (permissions, etc.)
                pass

        return count

    def stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dict with file_count, total_bytes
        """
        files = list(self._dir.glob("__kida_*.pyc"))
        total_bytes = sum(f.stat().st_size for f in files if f.exists())

        return {
            "file_count": len(files),
            "total_bytes": total_bytes,
        }


def hash_source(source: str) -> str:
    """Generate hash of template source for cache key."""
    return hashlib.sha256(source.encode()).hexdigest()
