"""Sandboxed environment example — running untrusted templates safely.

Demonstrates SandboxedEnvironment with default and custom security policies.

Run:
    python run.py
"""

from kida.sandbox import SandboxedEnvironment, SandboxPolicy, SecurityError


def main() -> None:
    # ── 1. Basic sandbox usage ──────────────────────────────────
    print("=== Basic Sandbox ===")
    env = SandboxedEnvironment()

    tmpl = env.from_string("Hello, {{ user.name }}!")
    print(tmpl.render(user={"name": "Alice"}))
    # Hello, Alice!

    # ── 2. Dunder access is blocked ────────────────────────────
    print("\n=== Dunder Access Blocked ===")
    for attr in ("__class__", "__globals__", "__dict__"):
        tmpl = env.from_string("{{ obj." + attr + " }}")
        try:
            tmpl.render(obj="hello")
        except SecurityError as e:
            print(f"  Blocked: {e}")

    # ── 3. Custom policy with allowed_attributes ───────────────
    print("\n=== Attribute Allowlist ===")
    policy = SandboxPolicy(
        allowed_attributes=frozenset({"name", "email"}),
    )
    restricted = SandboxedEnvironment(sandbox_policy=policy)

    tmpl = restricted.from_string("{{ user.name }} <{{ user.email }}>")
    print(tmpl.render(user={"name": "Bob", "email": "bob@example.com"}))
    # Bob <bob@example.com>

    # Accessing an unlisted attribute is blocked
    tmpl = restricted.from_string("{{ user.password }}")
    try:
        tmpl.render(user={"password": "secret123"})
    except SecurityError as e:
        print(f"  Blocked: {e}")

    # ── 4. Mutating methods ────────────────────────────────────
    print("\n=== Mutating Methods ===")

    # Default policy blocks mutating methods like .pop()
    tmpl = env.from_string("{{ items.pop() }}")
    try:
        tmpl.render(items=[1, 2, 3])
    except SecurityError as e:
        print(f"  Blocked by default: {e}")

    # Opt in to mutating methods
    mutable_policy = SandboxPolicy(allow_mutating_methods=True)
    mutable_env = SandboxedEnvironment(sandbox_policy=mutable_policy)

    tmpl = mutable_env.from_string("popped: {{ items.pop() }}, remaining: {{ items }}")
    print(tmpl.render(items=[1, 2, 3]))
    # popped: 3, remaining: [1, 2]

    # ── 5. Range limiting ──────────────────────────────────────
    print("\n=== Range Limiting ===")
    small_policy = SandboxPolicy(max_range=5)
    small_env = SandboxedEnvironment(sandbox_policy=small_policy)

    tmpl = small_env.from_string("{% for i in range(100) %}x{% endfor %}")
    try:
        tmpl.render()
    except SecurityError as e:
        print(f"  Blocked: {e}")


if __name__ == "__main__":
    main()
