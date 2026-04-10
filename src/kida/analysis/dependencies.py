"""Dependency analysis for template introspection.

Extracts context variable dependencies from AST expressions and blocks.
Produces a conservative superset — may include unused paths but never
excludes paths that are actually used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from kida.analysis.node_visitor import NodeVisitor
from kida.nodes import (
    Const,
    Getattr,
    Getitem,
    Name,
    OptionalGetattr,
    OptionalGetitem,
    Tuple,
)

if TYPE_CHECKING:
    from kida.nodes import (
        AsyncFor,
        Autoescape,
        Await,
        BinOp,
        Block,
        BoolOp,
        Break,
        Cache,
        CallBlock,
        Capture,
        Compare,
        Concat,
        CondExpr,
        Continue,
        Data,
        Def,
        Dict,
        Embed,
        Export,
        Extends,
        Filter,
        FilterBlock,
        For,
        FromImport,
        FuncCall,
        If,
        Import,
        Include,
        InlinedFilter,
        Let,
        List,
        ListComp,
        LoopVar,
        MarkSafe,
        Match,
        Node,
        NullCoalesce,
        Output,
        Pipeline,
        Range,
        Raw,
        Region,
        SafePipeline,
        Set,
        Slice,
        Slot,
        Spaceless,
        Template,
        Test,
        Trim,
        UnaryOp,
        While,
        With,
        WithConditional,
    )


# Names that are always available (not context dependencies)
_BUILTIN_NAMES = frozenset(
    {
        # Python builtins commonly used in templates
        "range",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "hasattr",
        "getattr",
        "isinstance",
        "type",
        # Boolean/None literals
        "true",
        "false",
        "none",
        "True",
        "False",
        "None",
        # Kida builtins
        "loop",  # Loop context variable
    }
)


class DependencyWalker(NodeVisitor):
    """Extract context variable dependencies from AST expressions.

    Walks the AST and collects all context paths (e.g., "page.title",
    "site.pages") that an expression or block may access.

    Produces a conservative superset: may include paths not actually
    used at runtime, but never excludes paths that are used.

    Thread-safe: Creates new state for each analyze() call.

    Example:
            >>> walker = DependencyWalker()
            >>> deps = walker.analyze(block_node)
            >>> print(deps)
        frozenset({'site.pages', 'site.title'})

    Scope Handling:
        - Loop variables ({% for x in items %}) are excluded
        - With bindings ({% with expr as x %}) are excluded
        - Function arguments ({% def fn(x) %}) are excluded
        - Set/let assignments create local scope

    """

    def __init__(self) -> None:
        """Initialize walker (stateless until analyze() is called)."""
        self._scope_stack: list[set[str]] = []
        self._all_locals: set[str] = set()
        self._dependencies: set[str] = set()

    def analyze(self, node: Node) -> frozenset[str]:
        """Analyze a node and return all context dependencies.

        Args:
            node: AST node to analyze (Block, Template, expression, etc.)

        Returns:
            Frozen set of context paths (e.g., {"page.title", "site.pages"})
        """
        # Reset state for each analysis
        self._scope_stack = [set()]
        self._all_locals = set()
        self._dependencies = set()
        self.visit(node)
        return frozenset(self._dependencies)

    def visit_Name(self, node: Name) -> None:  # noqa: N802
        """Handle variable reference."""
        name = node.name

        # Skip if it's a local variable (loop var, with binding, etc.)
        if self._is_local(name):
            return

        # Skip built-in names
        if name in _BUILTIN_NAMES:
            return

        # It's a context variable
        self._dependencies.add(name)

    def visit_Getattr(self, node: Getattr) -> None:  # noqa: N802
        """Handle attribute access: obj.attr"""
        path = self._build_path(node)
        if path:
            self._dependencies.add(path)
        else:
            # Couldn't build full path, visit children
            self.visit(node.obj)

    def visit_OptionalGetattr(self, node: OptionalGetattr) -> None:  # noqa: N802
        """Handle optional attribute access: obj?.attr"""
        # Same logic as regular getattr
        path = self._build_path(node)
        if path:
            self._dependencies.add(path)
        else:
            self.visit(node.obj)

    def visit_Getitem(self, node: Getitem) -> None:  # noqa: N802
        """Handle subscript access: obj[key]"""
        # We can only track static string keys
        if isinstance(node.key, Const) and isinstance(node.key.value, str):
            path = self._build_path(node)
            if path:
                self._dependencies.add(path)
                return

        # Dynamic key - track the base object and the key expression
        self.visit(node.obj)
        self.visit(node.key)

    def visit_OptionalGetitem(self, node: OptionalGetitem) -> None:  # noqa: N802
        """Handle optional subscript access: obj?[key]"""
        # Same logic as regular getitem
        if isinstance(node.key, Const) and isinstance(node.key.value, str):
            path = self._build_path(node)
            if path:
                self._dependencies.add(path)
                return

        self.visit(node.obj)
        self.visit(node.key)

    def visit_For(self, node: For | AsyncFor) -> None:  # noqa: N802
        """Handle for loop: push loop variable into scope."""
        # Visit the iterable (this IS a dependency)
        self.visit(node.iter)

        # Extract loop variables
        loop_vars = self._extract_targets(node.target)

        # Visit optional filter condition with loop var in scope
        test = getattr(node, "test", None)
        if test:
            self._push_scope(loop_vars | {"loop"})
            self.visit(test)
            self._pop_scope()

        # Push loop variable(s) into scope with implicit 'loop' variable
        self._push_scope(loop_vars | {"loop"})

        # Visit body with loop var in scope
        for child in node.body:
            self.visit(child)

        # Visit empty block (if any)
        empty = getattr(node, "empty", None)
        if empty:
            for child in empty:
                self.visit(child)

        # Pop scope
        self._pop_scope()

    def visit_AsyncFor(self, node: AsyncFor) -> None:  # noqa: N802
        """Handle async for loop (same as regular for)."""
        self.visit_For(node)

    def visit_While(self, node: While) -> None:  # noqa: N802
        """Handle while loop."""
        self.visit(node.test)
        for child in node.body:
            self.visit(child)

    def visit_With(self, node: With) -> None:  # noqa: N802
        """Handle with block: {% with x = expr %}...{% end %}"""
        # Collect all bindings
        bindings = set()
        for name, value in node.targets:
            self.visit(value)  # Value expression IS a dependency
            bindings.add(name)

        # Push bindings into scope
        self._push_scope(bindings)

        # Visit body
        for child in node.body:
            self.visit(child)

        # Pop scope
        self._pop_scope()

    def visit_WithConditional(self, node: WithConditional) -> None:  # noqa: N802
        """Handle conditional with: {% with expr as target %}"""
        # Visit the expression (IS a dependency)
        self.visit(node.expr)

        # Extract targets and push into scope
        targets = self._extract_targets(node.target)
        self._push_scope(targets)

        # Visit body
        for child in node.body:
            self.visit(child)

        # Pop scope
        self._pop_scope()

    def visit_Def(self, node: Def) -> None:  # noqa: N802
        """Handle function definition: push args into scope."""
        # Visit defaults (outside function scope)
        for default in node.defaults:
            self.visit(default)

        # Push function parameter names into scope
        self._push_scope({p.name for p in node.params})

        # Visit body
        for child in node.body:
            self.visit(child)

        self._pop_scope()

    def visit_Region(self, node: Region) -> None:  # noqa: N802
        """Handle region: push params into scope, visit body (same as def)."""
        # Visit defaults (outside region scope)
        for default in node.defaults:
            self.visit(default)

        # Push region parameter names into scope
        self._push_scope({p.name for p in node.params})

        # Visit body
        for child in node.body:
            self.visit(child)

        self._pop_scope()

    def visit_Macro(self, node: Node) -> None:  # noqa: N802
        """Handle macro definition (same as def)."""
        self.visit_Def(cast("Def", node))

    def visit_Set(self, node: Set) -> None:  # noqa: N802
        """Handle set statement."""
        # Visit the value expression
        self.visit(node.value)

        # Add target to current scope
        targets = self._extract_targets(node.target)
        if self._scope_stack:
            self._scope_stack[-1] |= targets

    def visit_Let(self, node: Let) -> None:  # noqa: N802
        """Handle let statement (template-scoped)."""
        # Visit the value expression
        self.visit(node.value)

        # Add to root scope
        if self._scope_stack:
            targets = self._extract_targets(node.name)
            self._scope_stack[0] |= targets

    def visit_Export(self, node: Export) -> None:  # noqa: N802
        """Handle export statement."""
        self.visit(node.value)
        # Export doesn't create a new scope

    def visit_Capture(self, node: Capture) -> None:  # noqa: N802
        """Handle capture block: {% capture name %}...{% end %}"""
        # Visit body
        for child in node.body:
            self.visit(child)

        # Visit filter if present
        filter_node = getattr(node, "filter", None)
        if filter_node:
            self.visit(filter_node)

        # Add captured name to current scope
        if self._scope_stack:
            self._scope_stack[-1].add(node.name)

    def visit_Filter(self, node: Filter) -> None:  # noqa: N802
        """Handle filter expression."""
        # Visit the value being filtered
        self.visit(node.value)

        # Visit filter arguments
        for arg in node.args:
            self.visit(arg)

        for value in node.kwargs.values():
            self.visit(value)

    def visit_OptionalFilter(self, node: Filter) -> None:  # noqa: N802
        """Handle optional filter expression (same as regular filter)."""
        self.visit_Filter(node)

    def visit_Pipeline(self, node: Pipeline) -> None:  # noqa: N802
        """Handle pipeline expression: expr |> filter1 |> filter2"""
        # Visit the initial value
        self.visit(node.value)

        # Visit arguments in each pipeline step
        for _name, args, kwargs in node.steps:
            for arg in args:
                self.visit(arg)
            for value in kwargs.values():
                self.visit(value)

    def visit_SafePipeline(self, node: SafePipeline) -> None:  # noqa: N802
        """Handle safe pipeline expression (same as regular pipeline)."""
        self.visit_Pipeline(node)

    def visit_FuncCall(self, node: FuncCall) -> None:  # noqa: N802
        """Handle function call."""
        # Visit the function expression
        self.visit(node.func)

        # Visit arguments
        for arg in node.args:
            self.visit(arg)

        for value in node.kwargs.values():
            self.visit(value)

        # Handle *args and **kwargs
        dyn_args = getattr(node, "dyn_args", None)
        if dyn_args:
            self.visit(dyn_args)
        dyn_kwargs = getattr(node, "dyn_kwargs", None)
        if dyn_kwargs:
            self.visit(dyn_kwargs)

    def visit_NullCoalesce(self, node: NullCoalesce) -> None:  # noqa: N802
        """Handle null coalescing: a ?? b"""
        self.visit(node.left)
        self.visit(node.right)

    def visit_CondExpr(self, node: CondExpr) -> None:  # noqa: N802
        """Handle conditional expression: a if cond else b"""
        self.visit(node.test)
        self.visit(node.if_true)
        self.visit(node.if_false)

    def visit_BoolOp(self, node: BoolOp) -> None:  # noqa: N802
        """Handle boolean operations: a and b, a or b"""
        for value in node.values:
            self.visit(value)

    def visit_BinOp(self, node: BinOp) -> None:  # noqa: N802
        """Handle binary operations: a + b, a - b, etc."""
        self.visit(node.left)
        self.visit(node.right)

    def visit_UnaryOp(self, node: UnaryOp) -> None:  # noqa: N802
        """Handle unary operations: -a, not a"""
        self.visit(node.operand)

    def visit_Compare(self, node: Compare) -> None:  # noqa: N802
        """Handle comparisons: a < b < c"""
        self.visit(node.left)
        for comp in node.comparators:
            self.visit(comp)

    def visit_Range(self, node: Range) -> None:  # noqa: N802
        """Handle range literal: start..end or start...end"""
        self.visit(node.start)
        self.visit(node.end)
        if node.step:
            self.visit(node.step)

    def visit_Slice(self, node: Slice) -> None:  # noqa: N802
        """Handle slice expression: [start:stop:step]"""
        if node.start:
            self.visit(node.start)
        if node.stop:
            self.visit(node.stop)
        if node.step:
            self.visit(node.step)

    def visit_Concat(self, node: Concat) -> None:  # noqa: N802
        """Handle string concatenation: a ~ b ~ c"""
        for child in node.nodes:
            self.visit(child)

    def visit_List(self, node: List) -> None:  # noqa: N802
        """Handle list literal: [a, b, c]"""
        for item in node.items:
            self.visit(item)

    def visit_ListComp(self, node: ListComp) -> None:  # noqa: N802
        """Handle list comprehension: [expr for x in iterable if cond]

        The iterable is a context dependency. The target variable is local
        to the comprehension — elt and ifs must be visited with it in scope.
        """
        # Iterable is evaluated in the enclosing scope
        self.visit(node.iter)

        # Push comprehension variable(s) into scope
        loop_vars = self._extract_targets(node.target)
        self._push_scope(loop_vars)

        # Visit element expression and conditions with target in scope
        self.visit(node.elt)
        for if_expr in node.ifs:
            self.visit(if_expr)

        self._pop_scope()

    def visit_Tuple(self, node: Tuple) -> None:  # noqa: N802
        """Handle tuple literal: (a, b, c)"""
        for item in node.items:
            self.visit(item)

    def visit_Dict(self, node: Dict) -> None:  # noqa: N802
        """Handle dict literal: {a: b, c: d}"""
        for key in node.keys:
            self.visit(key)
        for value in node.values:
            self.visit(value)

    def visit_Test(self, node: Test) -> None:  # noqa: N802
        """Handle test expression: x is defined"""
        self.visit(node.value)
        for arg in node.args:
            self.visit(arg)
        for value in node.kwargs.values():
            self.visit(value)

    def visit_Match(self, node: Match) -> None:  # noqa: N802
        """Handle match statement."""
        if node.subject is not None:
            self.visit(node.subject)
        for pattern, guard, body in node.cases:
            self.visit(pattern)
            if guard:
                self.visit(guard)
            for child in body:
                self.visit(child)

    def visit_Cache(self, node: Cache) -> None:  # noqa: N802
        """Handle cache block: {% cache key %}...{% end %}"""
        self.visit(node.key)
        if node.ttl:
            self.visit(node.ttl)
        for dep in node.depends:
            self.visit(dep)
        for child in node.body:
            self.visit(child)

    def visit_Include(self, node: Include) -> None:  # noqa: N802
        """Handle include statement."""
        self.visit(node.template)

    def visit_Import(self, node: Import) -> None:  # noqa: N802
        """Handle import statement."""
        self.visit(node.template)
        # Add imported name to scope
        if self._scope_stack:
            self._scope_stack[-1].add(node.target)

    def visit_FromImport(self, node: FromImport) -> None:  # noqa: N802
        """Handle from...import statement."""
        self.visit(node.template)
        # Add imported names to scope
        if self._scope_stack:
            for name, alias in node.names:
                self._scope_stack[-1].add(alias or name)

    def visit_If(self, node: If) -> None:  # noqa: N802
        """Handle if statement."""
        self.visit(node.test)
        for child in node.body:
            self.visit(child)
        for child in node.else_:
            self.visit(child)
        # Handle elif
        elif_ = getattr(node, "elif_", None)
        if elif_:
            for test, body in elif_:
                self.visit(test)
                for child in body:
                    self.visit(child)

    def visit_Output(self, node: Output) -> None:  # noqa: N802
        """Handle output: {{ expr }}"""
        self.visit(node.expr)

    def visit_Block(self, node: Block) -> None:  # noqa: N802
        """Handle block: {% block name %}...{% end %}"""
        for child in node.body:
            self.visit(child)

    def visit_Extends(self, node: Extends) -> None:  # noqa: N802
        """Handle extends: {% extends 'base.html' %}"""
        self.visit(node.template)

    def visit_Template(self, node: Template) -> None:  # noqa: N802
        """Handle template root node."""
        if node.extends:
            self.visit(node.extends)
        for child in node.body:
            self.visit(child)

    def visit_FilterBlock(self, node: FilterBlock) -> None:  # noqa: N802
        """Handle filter block: {% filter upper %}...{% end %}"""
        self.visit(node.filter)
        for child in node.body:
            self.visit(child)

    def visit_CallBlock(self, node: CallBlock) -> None:  # noqa: N802
        """Handle call block: {% call name(args) %}body{% end %} with named slots."""
        self.visit(node.call)
        for arg in node.args:
            self.visit(arg)
        for slot_body in node.slots.values():
            for child in slot_body:
                self.visit(child)

    def visit_Spaceless(self, node: Spaceless) -> None:  # noqa: N802
        """Handle spaceless block."""
        for child in node.body:
            self.visit(child)

    def visit_Autoescape(self, node: Autoescape) -> None:  # noqa: N802
        """Handle autoescape block."""
        for child in node.body:
            self.visit(child)

    def visit_Trim(self, node: Trim) -> None:  # noqa: N802
        """Handle trim block."""
        for child in node.body:
            self.visit(child)

    def visit_Embed(self, node: Embed) -> None:  # noqa: N802
        """Handle embed: {% embed 'card.html' %}...{% end %}"""
        self.visit(node.template)
        for block in node.blocks.values():
            self.visit(block)

    def visit_Await(self, node: Await) -> None:  # noqa: N802
        """Handle await expression."""
        self.visit(node.value)

    def visit_MarkSafe(self, node: MarkSafe) -> None:  # noqa: N802
        """Handle safe marker."""
        self.visit(node.value)

    def visit_InlinedFilter(self, node: InlinedFilter) -> None:  # noqa: N802
        """Handle inlined filter (optimization)."""
        self.visit(node.value)
        for arg in node.args:
            self.visit(arg)

    # Leaf nodes that don't need children visited
    def visit_Const(self, node: Const) -> None:  # noqa: N802
        """Constants have no dependencies."""

    def visit_Data(self, node: Data) -> None:  # noqa: N802
        """Static data has no dependencies."""

    def visit_Raw(self, node: Raw) -> None:  # noqa: N802
        """Raw blocks have no dependencies."""

    def visit_Slot(self, node: Slot) -> None:  # noqa: N802
        """Slots have no dependencies."""

    def visit_Break(self, node: Break) -> None:  # noqa: N802
        """Break has no dependencies."""

    def visit_Continue(self, node: Continue) -> None:  # noqa: N802
        """Continue has no dependencies."""

    def visit_Do(self, node: Node) -> None:  # noqa: N802
        """Handle do statement."""
        expr = getattr(node, "expr", None)
        if expr is not None:
            self.visit(expr)

    def visit_LoopVar(self, node: LoopVar) -> None:  # noqa: N802
        """Loop variable access (loop.index, etc.) - no context deps."""

    def _build_path(self, node: Node) -> str | None:
        """Build dotted path from chained attribute/item access.

        Returns None if the path can't be determined statically
        (e.g., dynamic keys, local variables).
        """
        parts: list[str] = []
        current = node

        while True:
            match current:
                case Getattr() | OptionalGetattr():
                    parts.append(current.attr)
                    current = current.obj
                case Getitem():
                    # Only static string keys
                    if isinstance(current.key, Const) and isinstance(current.key.value, str):
                        parts.append(current.key.value)
                        current = current.obj
                    else:
                        return None  # Dynamic key
                case OptionalGetitem():
                    if isinstance(current.key, Const) and isinstance(current.key.value, str):
                        parts.append(current.key.value)
                        current = current.obj
                    else:
                        return None
                case Name():
                    name = current.name
                    # Check if root is local
                    if self._is_local(name):
                        return None  # Local var, not a context dep
                    if name in _BUILTIN_NAMES:
                        return None  # Built-in
                    parts.append(name)
                    break
                case _:
                    return None  # Can't determine statically

        parts.reverse()
        return ".".join(parts)

    def _extract_targets(self, node: Node) -> set[str]:
        """Extract variable names from assignment target."""
        match node:
            case Name():
                return {node.name}
            case Tuple():
                names: set[str] = set()
                for item in node.items:
                    names |= self._extract_targets(item)
                return names
            case _:
                return set()

    def _push_scope(self, names: set[str]) -> None:
        """Push a new scope and update the flat locals set."""
        self._scope_stack.append(names)
        self._all_locals |= names

    def _pop_scope(self) -> None:
        """Pop the top scope and rebuild the flat locals set."""
        self._scope_stack.pop()
        # Rebuild flat set from remaining scopes
        self._all_locals = set().union(*self._scope_stack) if self._scope_stack else set()

    def _is_local(self, name: str) -> bool:
        """Check if a name is in local scope (O(1) via flat set)."""
        return name in self._all_locals
