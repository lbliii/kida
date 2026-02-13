"""RenderedTemplate -- lazy wrapper for streaming without pre-consuming.

RenderedTemplate(template, context) wraps a template + context pair.
- str(rt) renders fully
- for chunk in rt iterates over render_stream() chunks

Use case: pass to StreamingResponse without calling render() first.

Run:
    python app.py
"""

from kida import Environment, RenderedTemplate

env = Environment()
template = env.from_string("""\
<ul>
{% for item in items %}
    <li>{{ item }}</li>
{% end %}
</ul>
""")

context = {"items": ["a", "b", "c"]}
rt = RenderedTemplate(template, context)

# Full render via str()
full_output = str(rt)

# Streaming: iterate over chunks
chunks = list(rt)
streamed_output = "".join(chunks)


def main() -> None:
    print("=== Full render (str) ===")
    print(full_output)
    print()
    print("=== Streamed chunks ===")
    for i, chunk in enumerate(RenderedTemplate(template, context)):
        print(f"  [chunk {i}] {chunk!r}")
    print()
    print("=== Verify equivalence ===")
    print(f"str(rt) == ''.join(rt): {full_output == streamed_output}")


if __name__ == "__main__":
    main()
