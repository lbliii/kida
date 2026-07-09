"""Tests for the loop-unrolling partial-evaluation phase."""

from kida import Environment


def _env() -> Environment:
    return Environment(autoescape=False)


class TestStaticLoopUnrolling:
    """Static for-loops are unrolled at compile time."""

    def test_simple_unroll(self):
        """{% for x in items %}{{ x }}{% end %} with static items unrolls."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }},{% end %}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "1,2,3,"

    def test_unroll_with_attribute_access(self):
        """Unrolled items support attribute access."""
        env = _env()
        nav = [{"title": "Home", "url": "/"}, {"title": "About", "url": "/about"}]
        tmpl = env.from_string(
            '{% for item in nav %}<a href="{{ item.url }}">{{ item.title }}</a>{% end %}',
            static_context={"nav": nav},
        )
        assert tmpl.render() == '<a href="/">Home</a><a href="/about">About</a>'

    def test_unroll_with_loop_index(self):
        """loop.index works in unrolled loops."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ loop.index }}:{{ x }} {% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "1:a 2:b 3:c "

    def test_unroll_with_loop_first_last(self):
        """loop.first and loop.last work in unrolled loops."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}"
            "{% if loop.first %}[{% end %}"
            "{{ x }}"
            "{% if loop.last %}]{% end %}"
            "{% if not loop.last %},{% end %}"
            "{% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "[a,b,c]"

    def test_unroll_empty_list(self):
        """Empty static list → empty body (or {% empty %} branch)."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}none{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "none"

    def test_unroll_tuple_unpacking(self):
        """{% for k, v in items %}{{ k }}={{ v }}{% end %} unrolls."""
        env = _env()
        tmpl = env.from_string(
            "{% for k, v in pairs %}{{ k }}={{ v }} {% end %}",
            static_context={"pairs": [("a", 1), ("b", 2)]},
        )
        assert tmpl.render() == "a=1 b=2 "

    def test_unroll_list_literal(self):
        """{% for x in [1, 2, 3] %} unrolls with literal list."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in [1, 2, 3] %}{{ x }}{% end %}",
        )
        assert tmpl.render() == "123"

    def test_dynamic_iter_not_unrolled(self):
        """Dynamic iterable is not unrolled — works normally at runtime."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(items=[1, 2]) == "12"

    def test_unroll_mixed_static_dynamic_body(self):
        """Unrolled loop body can mix static and dynamic expressions."""
        env = _env()
        tmpl = env.from_string(
            "{% for item in nav %}{{ site_name }}: {{ item.title }}\n{% end %}",
            static_context={
                "nav": [{"title": "Home"}, {"title": "About"}],
                "site_name": "Kida",
            },
        )
        assert tmpl.render() == "Kida: Home\nKida: About\n"


class TestUnrolledLoopLetBinding:
    """Regression tests for loop variable references in {% let %} inside unrolled loops.

    When a for-loop is unrolled but a {% let %} value can only be *partially*
    resolved (e.g. it references both the loop variable and a runtime-only
    expression), the partial evaluator must still replace the resolvable
    sub-expressions with Const nodes.  Otherwise the unrolled body references
    the loop variable outside its defining scope, causing UndefinedError.

    See: https://github.com/<owner>/<repo>/issues/78
    """

    def test_let_with_loop_var_and_dynamic_expr(self):
        """{% let %} inside unrolled loop referencing loop var + dynamic expr."""
        env = _env()
        tmpl = env.from_string(
            "{% let items = [{'u': 'a.com'}, {'u': 'b.com'}] %}"
            "{% for it in items %}"
            "{% let url = it.u ~ '?q=' ~ query %}"
            "{{ url }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(query="hello") == "a.com?q=hello\nb.com?q=hello\n"

    def test_let_with_loop_var_and_pipeline(self):
        """{% let %} with pipeline operator inside unrolled loop."""
        env = _env()
        tmpl = env.from_string(
            "{% let items = [{'u': 'a.com'}, {'u': 'b.com'}] %}"
            "{% for it in items %}"
            "{% let url = it.u ~ '?q=' ~ (query |> upper) %}"
            "{{ url }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(query="hello") == "a.com?q=HELLO\nb.com?q=HELLO\n"

    def test_multiple_loops_with_let_and_match(self):
        """Multiple unrolled loops with match + let preserve loop var bindings."""
        env = _env()
        tmpl = env.from_string(
            "{% let actions = [{'type': 'a'}, {'type': 'b'}] %}"
            "{% let targets = [{'url': 'x.com'}, {'url': 'y.com'}] %}"
            "{% for act in actions %}"
            "{% match act.type %}{% case 'a' %}A{% case 'b' %}B{% end %}"
            "{% end %}"
            "{% for t in targets %}"
            "{% let link = t.url ~ '?r=' ~ ref %}"
            "{{ link }}\n"
            "{% end %}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(ref="z") == "ABx.com?r=z\ny.com?r=z\n"

    def test_cross_template_import_let_in_loop(self):
        """Imported def with unrolled loop + partially-dynamic let."""
        from kida.environment import DictLoader

        macros_src = (
            '{% let ITEMS = [{"name": "A", "url": "a.com"}, '
            '{"name": "B", "url": "b.com"}] %}'
            "{% def show(query) %}"
            "{% for item in ITEMS %}"
            '{% let link = item.url ~ "?q=" ~ query %}'
            '<a href="{{ link }}">{{ item.name }}</a>\n'
            "{% end %}"
            "{% end %}"
        )
        main_src = '{% from "m.html" import show %}{{ show(query=q) }}'
        loader = DictLoader({"m.html": macros_src, "main.html": main_src})
        env = Environment(loader=loader, static_context={"_placeholder": True})
        tmpl = env.get_template("main.html")
        result = tmpl.render(q="hi")
        assert '<a href="a.com?q=hi">A</a>' in result
        assert '<a href="b.com?q=hi">B</a>' in result

    def test_export_with_loop_var_and_dynamic_expr(self):
        """{% export %} inside unrolled loop with partially-dynamic value."""
        env = _env()
        tmpl = env.from_string(
            '{% let items = [{"name": "A"}, {"name": "B"}] %}'
            "{% for item in items %}"
            "{% export result = item.name ~ dynamic %}"
            "{% end %}"
            "{{ result }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(dynamic="!") == "B!"

    def test_capture_with_loop_var_and_dynamic_expr(self):
        """{% capture %} inside unrolled loop with partially-dynamic body."""
        env = _env()
        tmpl = env.from_string(
            '{% let items = [{"name": "A"}, {"name": "B"}] %}'
            "{% for item in items %}"
            "{% capture result %}{{ item.name }}:{{ dynamic }}{% end %}"
            "{% end %}"
            "{{ result }}",
            static_context={"_placeholder": True},
        )
        assert tmpl.render(dynamic="!") == "B:!"


class TestForLoopUnrolling:
    """For-loop unrolling with static iterables."""

    def test_unroll_basic(self):
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"items": [1, 2, 3]},
        )
        assert tmpl.render() == "123"

    def test_unroll_empty_iterable(self):
        """Empty iterable → empty output."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == ""

    def test_unroll_empty_with_fallback(self):
        """Empty iterable with else block → else body."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}none{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "none"

    def test_unroll_tuple_unpacking(self):
        """Tuple unpacking in for target."""
        env = _env()
        tmpl = env.from_string(
            "{% for k, v in pairs %}{{ k }}={{ v }} {% end %}",
            static_context={"pairs": [("a", 1), ("b", 2)]},
        )
        assert tmpl.render().strip() == "a=1 b=2"

    def test_unroll_with_test_filter(self):
        """For with if-filter on items."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items if x > 2 %}{{ x }}{% end %}",
            static_context={"items": [1, 2, 3, 4]},
        )
        assert tmpl.render() == "34"

    def test_unroll_loop_properties(self):
        """Loop.first / loop.last available during unrolling."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}"
            "{% if loop.first %}[{% end %}"
            "{{ x }}"
            "{% if loop.last %}]{% end %}"
            "{% end %}",
            static_context={"items": ["a", "b", "c"]},
        )
        assert tmpl.render() == "[abc]"

    def test_unroll_too_many_items_falls_back(self):
        """More than 200 items → not unrolled, still works at runtime."""
        env = _env()
        big_list = list(range(201))
        tmpl = env.from_string(
            "{{ items | length }}",
            static_context={"items": big_list},
        )
        assert tmpl.render() == "201"


class TestForLoopTestFilter:
    """For-loop with test (if) filter via partial eval."""

    def test_for_test_filter_static(self):
        """For with static iterable and test filter."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items if x > 0 %}{{ x }}{% end %}",
            static_context={"items": [-1, 0, 1, 2]},
        )
        assert tmpl.render() == "12"

    def test_for_empty_static_with_empty_block(self):
        """Empty static iterable triggers empty block."""
        env = _env()
        tmpl = env.from_string(
            "{% for x in items %}{{ x }}{% empty %}nothing{% end %}",
            static_context={"items": []},
        )
        assert tmpl.render() == "nothing"
