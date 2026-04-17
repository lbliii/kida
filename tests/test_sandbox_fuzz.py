"""Hypothesis-driven sandbox invariants.

Turns the claims in ``SECURITY.md`` into generative evidence. Each property
below is a differential or inclusive invariant that the sandbox must hold
under arbitrary attribute-chain / loop-count / output-size input.

Design rationale and property list:
    plan/design-render-surface-hardening.md (Decision 3).

Protocol for a real finding:
    A property failure on hypothesis-shrunken input is a security signal,
    not a flaky test. **Do not** suppress the example. Follow the protocol
    in ``SECURITY.md`` — file a private advisory, patch, re-run the fuzz.
"""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, seed, settings
from hypothesis import strategies as st

from kida import Environment
from kida.sandbox import (
    _BLOCKED_ATTRS,
    _SAFE_COLLECTION_METHODS,
    DEFAULT_POLICY,
    SandboxedEnvironment,
    SandboxPolicy,
    SecurityError,
    _is_attr_blocked,
)

# ─────────────────────────────────────────────────────────────────────────────
# Name pools — mirrors the design note's Decision 3 table
# ─────────────────────────────────────────────────────────────────────────────

# Dunders that the ``starts/ends with __`` rule does NOT block. Any other
# dunder (e.g. ``__doc__``, ``__name__``) is caught by the pattern rule.
_ALLOWED_DUNDERS = frozenset(
    {"__len__", "__iter__", "__contains__", "__getitem__", "__str__", "__repr__"}
)

_NAME_POOL = sorted(_SAFE_COLLECTION_METHODS | _BLOCKED_ATTRS | _ALLOWED_DUNDERS)


name_strategy = st.one_of(
    st.sampled_from(_NAME_POOL),
    # Random valid identifiers — bias toward short so chains stay readable.
    st.text(alphabet=string.ascii_letters + "_", min_size=1, max_size=8).filter(
        lambda s: s.isidentifier()
    ),
)


# Chains of length 1-4, biased toward 2-3 (typical SSTI hop count).
chain_strategy = st.lists(name_strategy, min_size=1, max_size=4)


# ─────────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────────


class AnyAttr:
    """Object that answers every non-blocked attribute access with itself.

    Used as the template's root binding so that hypothesis-generated chains
    do not dead-end on ``AttributeError`` before reaching the hop we want
    the sandbox to judge.

    ``__getattr__`` fires only when normal attribute lookup fails, so dunders
    the sandbox blocks (``__class__`` etc.) still go through the sandbox's
    allowlist/blocklist — they never reach our override.
    """

    def __getattr__(self, name: str) -> AnyAttr:
        return self

    def __str__(self) -> str:
        return ""

    def __repr__(self) -> str:
        return "<AnyAttr>"


def _template_for_chain(chain: list[str]) -> str:
    """Build ``{{ x.a.b.c }}`` from ``['a', 'b', 'c']``."""
    return "{{ x" + "".join(f".{name}" for name in chain) + " }}"


def _any_blocked(chain: list[str], policy: SandboxPolicy) -> bool:
    """Oracle: would the sandbox block any hop in this chain?"""
    return any(_is_attr_blocked(n, policy) for n in chain)


# Shared hypothesis settings. The design note pins ``max_examples=200`` and
# ``deadline=None``; the ``@seed(0)`` on each test makes CI reproducible.
_common_settings = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


# ─────────────────────────────────────────────────────────────────────────────
# Property 1 — blocklist is honored
# ─────────────────────────────────────────────────────────────────────────────


class TestBlocklistHonored:
    @_common_settings
    @seed(0)
    @given(chain=chain_strategy)
    def test_any_blocked_hop_raises_security_error(self, chain: list[str]) -> None:
        """A chain containing any blocked name must raise SecurityError.

        A chain with no blocked name must not raise SecurityError (other
        exception types are permitted — dunders like ``__iter__`` invoked
        on a random object routinely ``TypeError``, which is fine).
        """
        env = SandboxedEnvironment()
        tmpl = env.from_string(_template_for_chain(chain))
        has_blocked = _any_blocked(chain, DEFAULT_POLICY)

        if has_blocked:
            with pytest.raises(SecurityError):
                tmpl.render(x=AnyAttr())
        else:
            try:
                tmpl.render(x=AnyAttr())
            except SecurityError as e:
                pytest.fail(f"SecurityError raised on a chain with no blocked hop ({chain!r}): {e}")
            except Exception:
                # Non-security exceptions are out of scope for this property.
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Property 2 — allowlist mode is closed
# ─────────────────────────────────────────────────────────────────────────────


class TestAllowlistClosed:
    @_common_settings
    @seed(0)
    @given(chain=chain_strategy)
    def test_chain_outside_allowlist_raises(self, chain: list[str]) -> None:
        """With ``allowed_attributes={"name"}``, any hop not in
        ``{"name"} | _SAFE_COLLECTION_METHODS`` must raise SecurityError.
        """
        policy = SandboxPolicy(allowed_attributes=frozenset({"name"}))
        env = SandboxedEnvironment(sandbox_policy=policy)
        tmpl = env.from_string(_template_for_chain(chain))
        has_blocked = _any_blocked(chain, policy)

        if has_blocked:
            with pytest.raises(SecurityError):
                tmpl.render(x=AnyAttr())
        else:
            try:
                tmpl.render(x=AnyAttr())
            except SecurityError as e:
                pytest.fail(
                    f"SecurityError raised on a chain fully inside the allowlist ({chain!r}): {e}"
                )
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Property 3 — default Environment vs SandboxedEnvironment DIFFER
# ─────────────────────────────────────────────────────────────────────────────


# Fixed corpus, not hypothesis-generated: these encode the *differential*
# between default and sandboxed modes. Each expression must (a) render
# without raising under a default ``Environment`` and (b) raise SecurityError
# under ``SandboxedEnvironment``. If any expression succeeds under both, the
# sandbox has silently weakened.
_DIFFERENTIAL_ESCAPES: tuple[tuple[str, str], ...] = (
    ("class-of-string", '{{ "".__class__ }}'),
    ("class-of-list", "{{ [].__class__ }}"),
    ("class-of-dict", "{{ {}.__class__ }}"),
    ("mro-of-empty-tuple", "{{ ().__class__.__mro__ }}"),
    ("base-of-empty-tuple", "{{ ().__class__.__base__ }}"),
    ("subclasses-chain", '{{ "".__class__.__mro__[-1].__subclasses__() }}'),
    ("globals-of-callable", "{{ fn.__globals__ }}"),
    ("code-of-callable", "{{ fn.__code__ }}"),
)


class TestDefaultVsSandbox:
    @pytest.mark.parametrize(
        "name,expr", _DIFFERENTIAL_ESCAPES, ids=[n for n, _ in _DIFFERENTIAL_ESCAPES]
    )
    def test_sandbox_blocks_what_default_allows(self, name: str, expr: str) -> None:
        default_env = Environment()
        sandbox_env = SandboxedEnvironment()

        def fn() -> None:
            return None

        ctx = {"fn": fn}

        # Under default Environment: must not raise. (We ignore the rendered
        # value — merely not raising is what "weaker than sandbox" means.)
        try:
            default_env.from_string(expr).render(**ctx)
        except Exception as e:  # pragma: no cover — indicates corpus drift
            pytest.skip(
                f"Differential corpus entry {name!r} no longer succeeds under "
                f"default Environment ({type(e).__name__}: {e}). Update the "
                "corpus or the default-env capability model."
            )

        with pytest.raises(SecurityError):
            sandbox_env.from_string(expr).render(**ctx)


# ─────────────────────────────────────────────────────────────────────────────
# Property 4 — max_range enforced
# ─────────────────────────────────────────────────────────────────────────────


class TestMaxRangeEnforced:
    @_common_settings
    @seed(0)
    @given(n=st.integers(min_value=0, max_value=2_000))
    def test_range_size_respects_policy(self, n: int) -> None:
        """``{% for x in range(N) %}.{% end %}`` raises iff N > policy.max_range."""
        limit = 100
        policy = SandboxPolicy(max_range=limit)
        env = SandboxedEnvironment(sandbox_policy=policy)
        tmpl = env.from_string("{% for _ in range(n) %}.{% end %}")

        if n > limit:
            with pytest.raises(SecurityError):
                tmpl.render(n=n)
        else:
            # Must render without error (output is n dots).
            out = tmpl.render(n=n)
            assert out == "." * n


# ─────────────────────────────────────────────────────────────────────────────
# Property 5 — max_output_size enforced
# ─────────────────────────────────────────────────────────────────────────────


class TestMaxOutputSizeEnforced:
    @_common_settings
    @seed(0)
    @given(size=st.integers(min_value=0, max_value=2_000))
    def test_output_size_respects_policy(self, size: int) -> None:
        """A template whose output is ``size`` chars raises iff size > limit."""
        limit = 500
        policy = SandboxPolicy(max_output_size=limit)
        env = SandboxedEnvironment(sandbox_policy=policy)
        tmpl = env.from_string("{{ s }}")
        s = "a" * size

        if size > limit:
            with pytest.raises(SecurityError):
                tmpl.render(s=s)
        else:
            assert tmpl.render(s=s) == s
