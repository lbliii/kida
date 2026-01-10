from types import SimpleNamespace

from kida.tstring import k


def test_k_escapes_plain_values() -> None:
    tmpl = SimpleNamespace(
        strings=["Hello ", "!"],
        interpolations=[SimpleNamespace(value="<World>")],
    )

    assert k(tmpl) == "Hello &lt;World&gt;!"


def test_k_respects_html_interface() -> None:
    class HtmlLike:
        def __html__(self) -> str:
            return "<b>safe</b>"

    tmpl = SimpleNamespace(
        strings=["Welcome ", "!"],
        interpolations=[SimpleNamespace(value=HtmlLike())],
    )

    assert k(tmpl) == "Welcome <b>safe</b>!"
