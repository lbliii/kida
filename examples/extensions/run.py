"""Extension plugin example: custom {% debug expr %} tag.

Demonstrates the Kida Extension API by building a tag that prints
a value to stdout during template rendering — useful for debugging.
"""

import ast
from dataclasses import dataclass
from typing import ClassVar

from kida import Environment, TokenType
from kida.diagnostics import (
    Diagnostic,
    DiagnosticConfidence,
    DiagnosticSeverity,
    SourcePosition,
    SourceSpan,
    diagnose_source,
)
from kida.extensions import Extension, ExtensionDiagnosticContext
from kida.nodes.base import Node


# 1. Define a custom AST node (frozen dataclass inheriting from Node)
@dataclass(frozen=True, slots=True)
class DebugNode(Node):
    """Node produced by {% debug expr %}."""

    expr: object  # An expression node from the parser


# 2. Define an Extension subclass
class DebugExtension(Extension):
    """Adds a {% debug expr %} tag that prints a value during rendering."""

    # Tags this extension handles (parser dispatch)
    tags: ClassVar[set[str]] = {"debug"}

    # Node class names this extension compiles (compiler dispatch)
    node_types: ClassVar[set[str]] = {"DebugNode"}

    # Diagnostic codes emitted by this extension use K-DEBUG-NNN.
    diagnostic_namespace: ClassVar[str] = "DEBUG"

    def diagnose(self, context: ExtensionDiagnosticContext):
        """Advise against leaving debug tags in committed templates."""
        findings = []
        for line_number, line in enumerate(context.source.splitlines(), start=1):
            column = line.find("{% debug")
            if column == -1:
                continue
            findings.append(
                Diagnostic(
                    code="K-DEBUG-001",
                    category="extension",
                    severity=DiagnosticSeverity.WARNING,
                    message="Remove the debug tag before committing the template.",
                    span=SourceSpan(start=SourcePosition(line_number, column)),
                    suggestion="Delete the debug tag after inspecting its value.",
                    confidence=DiagnosticConfidence.PROVEN,
                )
            )
        return tuple(findings)

    def parse(self, parser, tag_name):
        """Parse {% debug expr %} into a DebugNode."""
        token = parser._advance()  # consume the "debug" keyword token
        expr = parser._parse_expression()  # parse the expression
        parser._expect(TokenType.BLOCK_END)  # expect closing %}
        return DebugNode(lineno=token.lineno, col_offset=token.col_offset, expr=expr)

    def compile(self, compiler, node):
        """Compile DebugNode into an _append() call that writes to the output buffer."""
        expr = compiler._compile_expr(node.expr)
        # _append is always available in compiled template scope.
        # We write the debug marker directly into the rendered output.
        return [
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="_append", ctx=ast.Load()),
                    args=[
                        ast.JoinedStr(
                            values=[
                                ast.Constant(value="[debug] "),
                                ast.FormattedValue(
                                    value=expr,
                                    conversion=-1,
                                    format_spec=None,
                                ),
                                ast.Constant(value="\n"),
                            ]
                        )
                    ],
                    keywords=[],
                )
            )
        ]


# 3. Register the extension with Environment and use it in a template
def main():
    env = Environment(extensions=[DebugExtension])

    source = """\
{% set name = "Kida" %}
{% set version = 42 %}
{% debug name %}
{% debug version %}
Hello from {{ name }}, version {{ version }}.
"""
    template = env.from_string(source)

    report = diagnose_source(source, name="debug-example.html", environment=env)
    print("--- Static diagnostics ---")
    for finding in report.diagnostics:
        print(f"{finding.code}: {finding.message}")

    print("--- Rendered output ---")
    result = template.render()
    print(result)


if __name__ == "__main__":
    main()
