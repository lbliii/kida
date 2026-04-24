"""Render-surface parity — sync and async paths must produce identical output.

Invariant (sync-compatible trusted templates):

    render(C)          == "".join(render_stream(C))
                       == "".join(render_stream_async(C))
    render_block(b, C) == "".join(render_block_stream_async(b, C))

See plan/epic-render-surface-hardening.md and
plan/design-render-surface-hardening.md for the corpus rationale.

Regression guard: reverting the render_block_stream_async preamble-setup fix
(commit adding ``self._run_globals_setup_chain(ctx)`` inside
``Template.render_block_stream_async``) must turn the region + preamble cases
red. This is the whole reason the file exists.

Known divergences surfaced by this corpus should be tracked as strict xfails
with a bug tag and removed as soon as the corresponding fix lands.
"""

from __future__ import annotations

import inspect
import string
from dataclasses import dataclass
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kida import DictLoader, Environment
from kida.template import core as template_core

MACROS = "{% def tag(x) %}<em>{{ x }}</em>{% end %}"


@dataclass(frozen=True)
class ParityCase:
    """A parity corpus entry.

    ``block is None`` means the case is exercised only via full render (no
    block-level parity assertion). ``skip_full`` covers templates that cannot
    render to completion by themselves.

    ``xfail_full`` / ``xfail_block`` carry the bug tag documenting a known
    divergence; the corresponding test marks the case ``xfail(strict=True)``
    so the marker has to be removed the moment the bug is fixed.
    """

    name: str
    files: tuple[tuple[str, str], ...]
    target: str
    block: str | None
    context: tuple[tuple[str, Any], ...] = ()
    skip_full: bool = False
    xfail_full: str | None = None
    xfail_block: str | None = None


def _mk(
    name: str,
    files: dict[str, str],
    target: str,
    block: str | None = None,
    context: dict[str, Any] | None = None,
    *,
    skip_full: bool = False,
    xfail_full: str | None = None,
    xfail_block: str | None = None,
) -> ParityCase:
    return ParityCase(
        name=name,
        files=tuple(files.items()),
        target=target,
        block=block,
        context=tuple((context or {}).items()),
        skip_full=skip_full,
        xfail_full=xfail_full,
        xfail_block=xfail_block,
    )


def _env(case: ParityCase) -> Environment:
    return Environment(loader=DictLoader(dict(case.files)))


def _ctx(case: ParityCase) -> dict[str, Any]:
    return dict(case.context)


# ─────────────────────────────────────────────────────────────────────────────
# Corpus (per plan/design-render-surface-hardening.md)
# ─────────────────────────────────────────────────────────────────────────────

CORPUS: list[ParityCase] = [
    # Depth 0 — blocks, various preambles
    _mk("01.none.block.d0", {"page": "{% block content %}hello{% endblock %}"}, "page", "content"),
    _mk(
        "02.let.block.d0",
        {"page": '{% let brand = "Kida" %}{% block content %}{{ brand }}{% endblock %}'},
        "page",
        "content",
    ),
    _mk(
        "03.def.block.d0",
        {
            "page": "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            '{% block content %}{{ wrap("Kida") }}{% endblock %}'
        },
        "page",
        "content",
    ),
    _mk(
        "04.import.block.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            '{% block content %}{{ tag("Kida") }}{% endblock %}',
        },
        "page",
        "content",
    ),
    _mk(
        "05.all.block.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            '{% let brand = "Kida" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% block content %}{{ tag(brand) }}-{{ wrap(brand) }}{% endblock %}",
        },
        "page",
        "content",
    ),
    # Depth 0 — regions
    _mk(
        "06.none.region.d0",
        {"page": '{% region sidebar(p="/") %}<nav>{{ p }}</nav>{% end %}'},
        "page",
        "sidebar",
        {"p": "/about"},
    ),
    _mk(
        "07.let.region.d0",
        {"page": '{% let brand = "Kida" %}{% region sidebar() %}<nav>{{ brand }}</nav>{% end %}'},
        "page",
        "sidebar",
    ),
    _mk(
        "08.def.region.d0",
        {
            "page": "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% region sidebar(label='X') %}{{ wrap(label) }}{% end %}"
        },
        "page",
        "sidebar",
        {"label": "Y"},
    ),
    _mk(
        "09.import.region.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            "{% region sidebar(label='X') %}{{ tag(label) }}{% end %}",
        },
        "page",
        "sidebar",
        {"label": "Y"},
    ),
    _mk(
        "10.all.region.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            '{% let brand = "Kida" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% region sidebar(label='X') %}"
            "{{ tag(label) }}/{{ wrap(brand) }}"
            "{% end %}",
        },
        "page",
        "sidebar",
        {"label": "Y"},
    ),
    # Depth 0 — fragments (skipped in full render but block-level must match)
    _mk(
        "11.none.fragment.d0",
        {"page": "Before {% fragment oob %}<div>oob</div>{% end %} After"},
        "page",
        "oob",
    ),
    _mk(
        "12.let.fragment.d0",
        {"page": '{% let label = "L" %}Hi {% fragment oob %}<div>{{ label }}</div>{% end %} Bye'},
        "page",
        "oob",
    ),
    _mk(
        "13.import.fragment.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            'Hi {% fragment oob %}{{ tag("x") }}{% end %} Bye',
        },
        "page",
        "oob",
    ),
    # {% globals %} block + top-level def-in-globals
    _mk(
        "14.globals.block.d0",
        {
            "page": "{% globals %}{% def g() %}G{% end %}{% end %}"
            "{% block content %}{{ g() }}{% endblock %}"
        },
        "page",
        "content",
    ),
    # region-in-block composition
    _mk(
        "15.region_in_block.d0",
        {
            "page": "{% block content %}"
            "{% region panel() %}"
            "{% block inner %}I{% end %}"
            "{% end %}"
            "{{ panel() }}"
            "{% endblock %}"
        },
        "page",
        "content",
    ),
    # Depth 1 — inheritance, various preambles
    _mk(
        "16.none.block.d1",
        {
            "base": "<html>{% block content %}base{% endblock %}</html>",
            "child": '{% extends "base" %}{% block content %}overridden{% endblock %}',
        },
        "child",
        "content",
    ),
    _mk(
        "17.let.block.d1",
        {
            "base": "<html>{% block content %}{{ brand }}{% endblock %}</html>",
            "child": '{% extends "base" %}{% let brand = "Kida" %}'
            "{% block content %}{{ brand }}!{% endblock %}",
        },
        "child",
        "content",
    ),
    _mk(
        "18.def_child.block.d1",
        {
            "base": "<html>{% block content %}base{% endblock %}</html>",
            "child": '{% extends "base" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            '{% block content %}{{ wrap("Kida") }}{% endblock %}',
        },
        "child",
        "content",
    ),
    _mk(
        "19.import_child.block.d1",
        {
            "macros": MACROS,
            "base": "<html>{% block content %}base{% endblock %}</html>",
            "child": '{% extends "base" %}'
            '{% from "macros" import tag %}'
            '{% block content %}{{ tag("Kida") }}{% endblock %}',
        },
        "child",
        "content",
    ),
    _mk(
        "20.none.region_parent.d1",
        {
            "base": '{% region sidebar(p="/") %}<nav>{{ p }}</nav>{% end %}'
            "{% block content %}{{ sidebar(p='/about') }}{% endblock %}",
            "child": '{% extends "base" %}{% block content %}leaf{% endblock %}',
        },
        "child",
        "sidebar",
        {"p": "/x"},
    ),
    _mk(
        "21.let.region_parent.d1",
        {
            "base": '{% let brand = "Kida" %}'
            "{% region sidebar() %}<nav>{{ brand }}</nav>{% end %}"
            "{% block content %}{{ sidebar() }}{% endblock %}",
            "child": '{% extends "base" %}{% block content %}leaf{% endblock %}',
        },
        "child",
        "sidebar",
    ),
    _mk(
        "22.all.block_plus_region.d1",
        {
            "macros": MACROS,
            "base": '{% from "macros" import tag %}'
            '{% let brand = "Kida" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% region sidebar() %}{{ tag(brand) }}{% end %}"
            "{% block content %}{{ wrap(brand) }}-{{ sidebar() }}{% endblock %}",
            "child": '{% extends "base" %}',
        },
        "child",
        "content",
    ),
    # Depth 2 — three-level inheritance
    _mk(
        "23.none.block.d2",
        {
            "base": "<html>{% block content %}base{% endblock %}</html>",
            "layout": '{% extends "base" %}{% block content %}layout{% endblock %}',
            "page": '{% extends "layout" %}{% block content %}leaf{% endblock %}',
        },
        "page",
        "content",
    ),
    _mk(
        "24.let.block.d2",
        {
            "base": "<html>{% block content %}{{ brand }}{% endblock %}</html>",
            "layout": '{% extends "base" %}{% let brand = "Layout" %}',
            "page": '{% extends "layout" %}'
            '{% let brand = "Leaf" %}'
            "{% block content %}{{ brand }}{% endblock %}",
        },
        "page",
        "content",
    ),
    _mk(
        "25.all.block_plus_region.d2",
        {
            "macros": MACROS,
            "base": "<html>{% block content %}base{% endblock %}</html>",
            "layout": '{% extends "base" %}'
            '{% from "macros" import tag %}'
            "{% region sidebar() %}{{ tag(brand) }}{% end %}"
            "{% block content %}layout-{{ sidebar() }}{% endblock %}",
            "page": '{% extends "layout" %}{% let brand = "Leaf" %}',
        },
        "page",
        "content",
    ),
    # Combined preamble variants
    _mk(
        "26.let_def.region.d0",
        {
            "page": '{% let brand = "Kida" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% region shell() %}{{ wrap(brand) }}{% end %}"
        },
        "page",
        "shell",
    ),
    _mk(
        "27.def.region_calling_def.d0",
        {
            "page": "{% def label(x) %}[{{ x }}]{% end %}"
            "{% region nav(section='home') %}{{ label(section) }}{% end %}"
        },
        "page",
        "nav",
        {"section": "about"},
    ),
    _mk(
        "28.import.region_calling_import.d0",
        {
            "macros": MACROS,
            "page": '{% from "macros" import tag %}'
            "{% region crumbs(current='home') %}{{ tag(current) }}{% end %}",
        },
        "page",
        "crumbs",
        {"current": "about"},
    ),
    # Fragments with inheritance
    _mk(
        "29.let.fragment.d1",
        {
            "base": '{% let brand = "Kida" %}'
            "{% block content %}base{% endblock %}"
            "{% fragment oob %}<div>{{ brand }}</div>{% end %}",
            "child": '{% extends "base" %}{% block content %}leaf{% endblock %}',
        },
        "child",
        "oob",
    ),
    _mk(
        "30.all.fragment.d1",
        {
            "macros": MACROS,
            "base": '{% from "macros" import tag %}'
            '{% let brand = "Kida" %}'
            "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
            "{% block content %}base{% endblock %}"
            "{% fragment oob %}{{ tag(brand) }}/{{ wrap(brand) }}{% end %}",
            "child": '{% extends "base" %}{% block content %}leaf{% endblock %}',
        },
        "child",
        "oob",
    ),
    # Control flow inside blocks
    _mk(
        "31.for_loop.block.d0",
        {"page": "{% block list %}{% for x in items %}<li>{{ x }}</li>{% end %}{% endblock %}"},
        "page",
        "list",
        {"items": ["a", "b", "c"]},
    ),
    _mk(
        "32.if_branch.block.d0",
        {
            "page": "{% let gate = true %}"
            "{% block gate %}"
            "{% if gate %}YES{% else %}NO{% end %}"
            "{% endblock %}"
        },
        "page",
        "gate",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Parity assertions
# ─────────────────────────────────────────────────────────────────────────────


def _param_for(case: ParityCase, tag: str | None) -> Any:
    """Wrap a case in pytest.param, xfail(strict=True) if ``tag`` is set.

    Strict — a bug fix that restores parity flips XPASS → FAIL, which forces
    the corresponding xfail tag to be removed from ``CORPUS``. Applying the
    marker at parametrize time (rather than via a runtime ``pytest.xfail()``
    call) is what makes strictness reachable.
    """
    marks: list[Any] = []
    if tag is not None:
        marks.append(
            pytest.mark.xfail(
                strict=True,
                reason=f"known divergence: {tag} — see module docstring",
            )
        )
    return pytest.param(case, id=case.name, marks=marks)


_FULL_PARAMS = [_param_for(c, c.xfail_full) for c in CORPUS]
_BLOCK_PARAMS = [_param_for(c, c.xfail_block) for c in CORPUS if c.block is not None]


class TestFullRenderParity:
    """render / render_stream / render_stream_async must all agree."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", _FULL_PARAMS)
    async def test_full_parity(self, case: ParityCase) -> None:
        if case.skip_full:
            pytest.skip("case excluded from full render")
        tmpl = _env(case).get_template(case.target)
        ctx = _ctx(case)

        expected = tmpl.render(**ctx)
        sync_stream = "".join(tmpl.render_stream(**ctx))
        async_stream = "".join([chunk async for chunk in tmpl.render_stream_async(**ctx)])

        assert sync_stream == expected, f"render_stream diverges from render for {case.name}"
        assert async_stream == expected, f"render_stream_async diverges from render for {case.name}"


class TestBlockRenderParity:
    """render_block / render_block_stream_async must agree for every (template, block)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", _BLOCK_PARAMS)
    async def test_block_parity(self, case: ParityCase) -> None:
        tmpl = _env(case).get_template(case.target)
        ctx = _ctx(case)
        assert case.block is not None  # type narrowing

        expected = tmpl.render_block(case.block, **ctx)
        async_stream = "".join(
            [chunk async for chunk in tmpl.render_block_stream_async(case.block, **ctx)]
        )

        assert async_stream == expected, (
            f"render_block_stream_async diverges from render_block for {case.name}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Property-based parity — hypothesis-generated contexts
# ─────────────────────────────────────────────────────────────────────────────


@settings(max_examples=40, deadline=None)
@given(
    name=st.text(alphabet=string.ascii_letters + string.digits, min_size=0, max_size=20),
    count=st.integers(min_value=0, max_value=10),
)
@pytest.mark.asyncio
async def test_let_block_fragment_render_parity(name: str, count: int) -> None:
    """Arbitrary context values agree across render_block and its async stream."""
    env = Environment(
        loader=DictLoader(
            {
                "page": (
                    '{% let brand = "Kida" %}'
                    "{% def wrap(x) %}<b>{{ x }}</b>{% end %}"
                    "{% block content %}"
                    "{{ brand }}-{{ wrap(name) }}-{{ count }}"
                    "{% endblock %}"
                )
            }
        )
    )
    tmpl = env.get_template("page")
    sync = tmpl.render_block("content", name=name, count=count)
    async_chunks = [
        c async for c in tmpl.render_block_stream_async("content", name=name, count=count)
    ]
    assert "".join(async_chunks) == sync


# ─────────────────────────────────────────────────────────────────────────────
# Meta-test — new render methods must be accounted for
# ─────────────────────────────────────────────────────────────────────────────


# Every public render-surface method on Template is either exercised by this
# file or explicitly marked exempt. Adding a new method forces a decision:
# either wire it into the parity tests, or document why it is out of scope.
_EXERCISED_METHODS = frozenset(
    {
        "render",
        "render_stream",
        "render_stream_async",
        "render_block",
        "render_block_stream_async",
    }
)
_EXEMPT_METHODS = frozenset(
    {
        "render_async",  # thread-wraps render(); no new surface to parity-check
        "render_with_blocks",  # block-injection variant, not a parity-same surface
    }
)


class TestRenderSurfaceMeta:
    def test_every_render_method_is_classified(self) -> None:
        render_methods = {
            name
            for name, _ in inspect.getmembers(template_core.Template, predicate=inspect.isfunction)
            if name.startswith("render")
        }
        classified = _EXERCISED_METHODS | _EXEMPT_METHODS
        unclassified = render_methods - classified
        assert not unclassified, (
            f"New render-surface methods not classified: {sorted(unclassified)}. "
            "Either add to _EXERCISED_METHODS and the parity assertions above, "
            "or add to _EXEMPT_METHODS with a justification comment."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Fragment-scaffold gate — every fragment-render method must route through
# ``_fragment_scaffold`` or ``_fragment_scaffold_async``. This is the
# structural forcing function that prevented the render_block_stream_async
# preamble-setup bug from recurring.
# ─────────────────────────────────────────────────────────────────────────────


# Fragment-render methods on Template. A method is "fragment" iff it renders
# a single block or injects block overrides — i.e., it must run
# ``_run_globals_setup_chain`` to mirror what full render does inline.
_FRAGMENT_METHODS = frozenset(
    {
        "render_block",
        "render_with_blocks",
        "render_block_stream_async",
    }
)


class TestFragmentScaffoldGate:
    def test_fragment_methods_route_through_scaffold(self) -> None:
        """Every fragment method's source must mention a fragment scaffold."""
        for method_name in _FRAGMENT_METHODS:
            method = getattr(template_core.Template, method_name, None)
            assert method is not None, (
                f"Template.{method_name} disappeared — remove it from "
                "_FRAGMENT_METHODS or restore the method."
            )
            src = inspect.getsource(method)
            assert "_fragment_scaffold(" in src or "_fragment_scaffold_async(" in src, (
                f"Template.{method_name} does not route through "
                "_fragment_scaffold / _fragment_scaffold_async. Fragment "
                "methods must use a scaffold so top-level let/def/region/import "
                "setup is not silently skipped (see "
                "plan/epic-render-surface-hardening.md, Sprint 2)."
            )

    def test_run_globals_setup_chain_callers_are_scaffolds_only(self) -> None:
        """Only the scaffolds call ``_run_globals_setup_chain``.

        If a new caller appears, it means the scaffold was bypassed — the bug
        class this sprint was designed to eliminate.
        """
        src = inspect.getsource(template_core)
        # Count call expressions (``self._run_globals_setup_chain(``), not
        # definitions or comments. The method's own ``def`` line is excluded
        # by matching the call syntax specifically. The sync path has two
        # guarded call sites in ``_render_scaffold`` (one inside the
        # enhance-errors try-block, one in the early-yield branch when
        # ``enhance_errors=False``); both are gated on
        # ``run_globals_setup=True``, which only fragment callers set via
        # ``_fragment_scaffold``. The async path has its own call site in
        # ``_fragment_scaffold_async``.
        call_count = src.count("self._run_globals_setup_chain(")
        assert call_count == 3, (
            f"Expected exactly 3 call sites for _run_globals_setup_chain "
            f"(two guarded sites in _render_scaffold, one in "
            f"_fragment_scaffold_async); found {call_count}. A new caller "
            "means a fragment method is bypassing the scaffold — route it "
            "through _fragment_scaffold(_async) instead."
        )
