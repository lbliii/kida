"""Optional Mako comparison benchmarks.

Requires: pip install mako

Run with: pytest benchmarks/test_benchmark_mako.py --benchmark-only -v

Skips if Mako is not installed (pytest.importorskip).
"""

from __future__ import annotations

import pytest

pytest.importorskip("mako")

from pytest_benchmark.fixture import BenchmarkFixture

from kida import Environment as KidaEnvironment

# Equivalent templates (Kida vs Mako syntax)
MINIMAL_KIDA = "Hello {{ name }}!"
MINIMAL_MAKO = "Hello ${name}!"

MEDIUM_KIDA = """\
{% if user %}
  <div class="profile">
    <h1>{{ user.name | title }}</h1>
    <p>{{ user.bio | default("No bio") }}</p>
    {% for post in user.posts %}
      <article>
        <h2>{{ post.title }}</h2>
        <p>{{ post.content }}</p>
      </article>
    {% end %}
  </div>
{% else %}
  <p>Please log in.</p>
{% end %}
"""
MEDIUM_MAKO = """\
% if user:
  <div class="profile">
    <h1>${user['name'].title()}</h1>
    <p>${user.get('bio', 'No bio')}</p>
    % for post in user['posts']:
      <article>
        <h2>${post['title']}</h2>
        <p>${post['content']}</p>
      </article>
    % endfor
  </div>
% else:
  <p>Please log in.</p>
% endif
"""

MINIMAL_CONTEXT = {"name": "World"}
MEDIUM_CONTEXT = {
    "user": {
        "name": "alice",
        "bio": "Software engineer",
        "posts": [
            {"title": f"Post {i}", "content": f"Content {i}"} for i in range(5)
        ],
    }
}


@pytest.mark.benchmark(group="mako:minimal")
def test_render_minimal_kida(benchmark: BenchmarkFixture) -> None:
    env = KidaEnvironment()
    template = env.from_string(MINIMAL_KIDA)
    benchmark(template.render, **MINIMAL_CONTEXT)


@pytest.mark.benchmark(group="mako:minimal")
def test_render_minimal_mako(benchmark: BenchmarkFixture) -> None:
    from mako.template import Template

    template = Template(MINIMAL_MAKO)
    benchmark(template.render, **MINIMAL_CONTEXT)


@pytest.mark.benchmark(group="mako:medium")
def test_render_medium_kida(benchmark: BenchmarkFixture) -> None:
    env = KidaEnvironment()
    template = env.from_string(MEDIUM_KIDA)
    benchmark(template.render, **MEDIUM_CONTEXT)


@pytest.mark.benchmark(group="mako:medium")
def test_render_medium_mako(benchmark: BenchmarkFixture) -> None:
    from mako.template import Template

    template = Template(MEDIUM_MAKO)
    benchmark(template.render, **MEDIUM_CONTEXT)
