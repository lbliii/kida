"""Terminal table and tree example."""

from kida import Environment


def main():
    env = Environment(autoescape="terminal", terminal_color="basic")

    # Table example
    table_template = env.from_string("""{{ "Package Dependencies" | bold | cyan }}
{{ packages | table(border="round") }}
""")

    packages = [
        {"Package": "kida", "Version": "0.3.0", "Size": "142 KiB", "Status": "installed"},
        {"Package": "bengal", "Version": "0.2.6", "Size": "89 KiB", "Status": "installed"},
        {"Package": "chirp", "Version": "0.1.0", "Size": "204 KiB", "Status": "dev"},
        {"Package": "pytest", "Version": "8.3.0", "Size": "1.2 MiB", "Status": "dev"},
    ]
    print(table_template.render(packages=packages))

    # Tree example
    tree_template = env.from_string("""{{ "Project Structure" | bold | cyan }}
{{ structure | tree }}
""")

    structure = {
        "src/": {
            "kida/": {
                "__init__.py": None,
                "compiler/": {"core.py": None, "statements/": {"...": None}},
                "environment/": {"core.py": None, "filters/": {"...": None}},
                "template/": {"core.py": None},
                "utils/": {"ansi_width.py": None, "terminal_escape.py": None},
            },
        },
        "tests/": {"test_terminal.py": None},
        "examples/": {"terminal_basic/": None, "terminal_dashboard/": None},
    }
    print(tree_template.render(structure=structure))


if __name__ == "__main__":
    main()
