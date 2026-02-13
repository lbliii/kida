"""t-string interpolation -- zero-parser-overhead with k(t"...") (Python 3.14+).

k(t"Hello {name}!") processes PEP 750 t-strings with automatic HTML escaping.
No template compilation. Ideal for high-frequency simple interpolation.

Run:
    python app.py
"""

from kida import Environment, k

# k() may be None on pre-3.14 Python
if k is None:
    output = ""
    output_escaped = ""
    template_equivalent = ""
else:
    # Simple interpolation
    name = "World"
    output = k(t"Hello {name}!")

    # Auto-escaping for HTML safety
    user_input = "<script>alert(1)</script>"
    output_escaped = k(t"<p>User said: {user_input}</p>")

    # Compare to traditional template (for context)
    env = Environment()
    template = env.from_string("Hello {{ name }}!")
    template_equivalent = template.render(name="World")


def main() -> None:
    if k is None:
        print("t-strings require Python 3.14+ (PEP 750)")
        return
    print("=== k(t\"...\") ===")
    print(output)
    print()
    print("=== Auto-escaping ===")
    print(output_escaped)
    print()
    print("=== Equivalent to from_string().render() ===")
    print(template_equivalent)
    print(f"Same output: {output == template_equivalent}")


if __name__ == "__main__":
    main()
