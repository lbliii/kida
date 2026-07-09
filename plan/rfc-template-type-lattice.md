# RFC: Internal Template Type Lattice and Component Signatures

**Status**: Proposed — internal design only

| Field | Value |
|---|---|
| Tracking | [GitHub issue #248](https://github.com/lbliii/kida/issues/248) |
| Parent | [GitHub issue #194](https://github.com/lbliii/kida/issues/194) |
| Coordinates with | #159 compiled t-string components, #172 component API diffing, #173 catalogs |
| Runtime target | Python 3.14+, pure Python, zero runtime dependencies |

## Decision summary

Kida should add one private, immutable type-and-signature intermediate
representation (IR) for static analysis. It must be conservative: absence of
proof produces `Unknown`, proven impossibility produces `Never`, and a proven
invalid operation produces `Error`. `Unknown` is not `Any` and never makes an
unsafe call valid.

The initial IR models:

- `object`, `none`, `bool`, `int`, `float`, and `str`;
- typed literals, normalized unions, and optional values;
- mutable lists and dictionaries, immutable tuples, read-only sequences and
  mappings, and closed/open record shapes;
- callable and component signatures, including parameter kinds, defaults,
  slots, and ambient context requirements;
- deterministic unknown reasons and source evidence.

`bool` is distinct from `int`. The numeric widening rule is `int <: float`, but
`bool` is a subtype of neither. Mutable containers are invariant; read-only
views are covariant where safe. Analysis never imports application modules,
evaluates annotations, invokes descriptors, or calls user code.

This RFC does **not** approve a public type API, parser syntax, extension
protocol, runtime validation, new diagnostics, stricter defaults, or changes to
generated function annotations.

## Existing contracts to preserve

Today the same component facts appear in several shapes:

| Producer or consumer | Current fact shape | Required adapter into the IR |
|---|---|---|
| `parser/blocks/functions.py` | `DefParam.annotation: str | None` | Normalize the raw annotation without evaluating it. |
| `nodes/functions.py` | `Def`/`Region`, defaults, variadics | Derive ordered parameter and default facts. |
| `nodes/structure.py` | `TemplateContext.declarations` | Normalize declared context types; keep names-only behavior until enforcement is approved. |
| `compiler/callable_plans.py` | `CallableSignaturePlan` | Prove lowering plans agree with the canonical signature; do not make codegen depend on analysis initially. |
| `analysis/analyzer.py` | private `_DefSignature` and literal-only type map | Replace duplication only after parity tests; unsupported annotations remain unknown. |
| `analysis/metadata.py` | public `DefMetadata`/`DefParamInfo` with raw strings | Project a backward-compatible public view; do not change fields in the initial phases. |
| `template/introspection.py` | independently rebuilds `DefMetadata` | Compare its output with the canonical adapter before consolidation. |
| Python t-string component | ordinary Python callable signature | Future trusted adapter; never import a module or evaluate an annotation to discover it. |

The compiler currently emits Python annotation AST from the raw string. That is
a runtime/codegen contract separate from semantic normalization. The first
implementation phases leave it untouched.

## Type IR

The names below describe private immutable variants, not proposed public Python
classes.

| Variant | Meaning |
|---|---|
| `Object` | Top of the proven type lattice. It says only “some template value.” |
| `Never` | Bottom: no value reaches this point, such as an unreachable branch. |
| `Error(error_id, evidence)` | Recovery sentinel for an already-proven invalid expression. It prevents cascades but is not assignable to other types. |
| `Unknown(reasons, evidence)` | Insufficient proof. It is neither top nor bottom and cannot satisfy an assignability check. |
| `Primitive(name)` | One of `none`, `bool`, `int`, `float`, or `str`. |
| `Literal(value, base)` | A source literal with its tagged base type. `true` and `1` remain distinct. |
| `Union(members)` | Flattened, deduplicated, deterministically ordered alternatives. `none | T` is the canonical optional form. |
| `List(element)` | Mutable homogeneous list; invariant. |
| `Dict(key, value)` | Mutable mapping; invariant in key and value. |
| `Tuple(items)` | Immutable fixed-length tuple; covariant element by element. |
| `Sequence(element)` | Read-only sequence view; covariant. |
| `Mapping(key, value)` | Read-only mapping view; key invariant, value covariant. |
| `Record(fields, open)` | Explicit structural fields supplied by trusted static metadata. An open record returns unknown for undeclared fields. |
| `Callable(signature)` | Callable parameter and return contract. |
| `Component(signature)` | Callable contract plus slot and ambient-context facts. |

Safe-string or escaping state is not encoded as a primitive type in this phase.
`Markup` behavior is an output-safety effect and must remain governed by the
escaping analysis. A later design may attach an effect to `str`; it must not
make `Markup` and ordinary `str` interchangeable by accident.

### Error, unknown, and object are different

- `Object` is a proven but broad type and may be used only by rules valid for
  every template value.
- `Unknown` records why analysis could not prove a type. A call expecting `str`
  and receiving `Unknown` has an **unknown** result, not a successful match.
- `Error` means a prior rule already proved the expression invalid. Consumers
  propagate it without inventing additional mismatch diagnostics.
- `Never` means the control-flow path cannot produce a value and is a subtype
  of every proven type.

## Subtyping and assignability

Write `A <: B` when every value represented by `A` is safe wherever `B` is
required. Assignability has three outcomes: `yes`, `no`, or `unknown`.

1. Subtyping is reflexive and transitive.
2. `Never <: T` and every proven `T <: Object`.
3. `Literal[v: T] <: T`.
4. `int <: float`; `bool` is separate from both `int` and `float`.
5. `A | B <: T` only if both `A <: T` and `B <: T`.
6. `T <: A | B` if `T` is a subtype of at least one member.
7. `List[A] <: List[B]` and `Dict[K1, V1] <: Dict[K2, V2]` only when the
   corresponding arguments are equal after normalization.
8. `Tuple[A1, ... An] <: Tuple[B1, ... Bn]` when each `Ai <: Bi`.
9. `Sequence[A] <: Sequence[B]` when `A <: B`.
10. `Mapping[K, A] <: Mapping[K, B]` when `A <: B`.
11. `List[A] <: Sequence[B]` when `A <: B`; `Dict[K, A] <: Mapping[K, B]`
    when `A <: B`.
12. A closed record is a subtype of a record whose required fields it contains
    with covariant field types. Open records do not prove absent fields.
13. Callable parameters are contravariant and returns covariant, subject to
    compatible parameter kinds, required/default status, and variadics.
14. `Unknown` produces assignability `unknown`; it is not silently accepted.
15. `Error` short-circuits assignability because the originating error already
    owns the diagnostic.

Python's runtime relation `isinstance(True, int)` does not override rule 4.
Template authors usually intend flags and counts to be different contracts, and
separating them prevents `true` from proving an integer component prop.

## Join, meet, and normalization

`join(A, B)` is the least representable common supertype used when control-flow
paths merge. `meet(A, B)` is their greatest representable common subtype used
for proven narrowing.

| Inputs | Join | Meet |
|---|---|---|
| identical normalized types | that type | that type |
| `Never`, `T` | `T` | `Never` |
| `int`, `float` | `float` | `int` |
| `bool`, `int` | `bool | int` | `Never` |
| literal and its base | base | literal |
| disjoint proven types | normalized union | `Never` |
| unions | flattened member union | pairwise non-`Never` intersections |
| same-length tuples | tuple of element joins | tuple of element meets, unless any element is `Never` |
| unequal tuples | `Sequence[join(all elements)]` | `Never` unless another rule proves overlap |
| equal mutable container types | that type | that type |
| unequal mutable containers | union of containers | `Never` unless one union member overlaps |
| read-only containers | container of argument joins | container of argument meets when variance permits |
| `Unknown`, `T` | merged `Unknown` | merged `Unknown` |
| `Error`, `T` | same `Error` | same `Error` |

Narrowing an unknown value through a runtime predicate is a transfer rule, not
`meet(Unknown, T)`. For example, the true branch of `x is none` may prove
`x: none`, while the false branch retains an unknown with evidence that `none`
was excluded.

Unions are flattened, duplicate members removed, `Never` removed, and members
sorted by a stable structural key. `Object` absorbs other proven members.
`Error` and `Unknown` are never hidden inside an ordinary union.

### Literal widening

Literal facts are retained for call checks, equality/match narrowing, and
defaults. Widening is deterministic:

- joining a literal with its base yields the base;
- a mutable collection literal widens its element/key/value literals to their
  base after computing the member join, so `[1, 2]` is `List[int]`;
- a union retains at most eight distinct literals of the same base; the ninth
  widens that group to the base type;
- `Literal[true] | Literal[false]` normalizes to `bool`;
- widening never runs merely to make an incompatible call pass.

The eight-literal threshold is an internal analysis budget, not a public
language promise. Changing it may alter explanations but must not alter whether
a proven mismatch is accepted.

## Canonical annotation normalization

Normalization consumes syntax already parsed as data. It never uses `eval`,
`typing.get_type_hints`, application imports, descriptor access, or arbitrary
Python attribute lookup.

### Initially recognized forms

| Source form | Canonical form |
|---|---|
| `None` or `none` | `none` |
| `bool`, `int`, `float`, `str`, `object` | corresponding primitive/top type |
| `T | U` | normalized union |
| `Optional[T]` | `T | none` when the existing syntax can represent it |
| `list[T]` | `List[T]` |
| `dict[K, V]` | `Dict[K, V]` |
| `tuple[T]` | fixed one-element `Tuple[T]`; homogeneous variadic tuples need syntax the current parser does not accept |
| `Sequence[T]` | read-only `Sequence[T]` |
| `Mapping[K, V]` | read-only `Mapping[K, V]` |
| unannotated parameter | `Unknown(unannotated)` |
| unsupported arity/form | `Unknown(unsupported_annotation)` |
| unresolved user name | `Unknown(unresolved_name)` unless a trusted offline catalog supplies it |

Aliases are explicit, not case-folded. The normalizer may accept a small
documented alias table, but must not resolve dotted Python names dynamically.

The current template annotation parser does not represent string-valued
`Literal[...]`, standard `Callable[[...], R]`, tuple ellipsis, dotted names, or
arbitrary Python typing expressions. This RFC does not expand that grammar.
Python-component adapters may construct the richer IR from explicitly supplied
facts. Any new template annotation syntax crosses parser/compiler/formatter,
analysis, malformed-source tests, and published docs and therefore requires a
separate stop-and-ask decision.

Malformed annotations remain parser errors where the parser already rejects
them. Well-formed but unsupported annotations normalize to `Unknown`; they do
not become a false type mismatch.

## Unknown reasons and evidence

Unknowns must be explainable and deterministic. The proposed private shape is:

```text
Unknown(
  reasons: sorted tuple[UnknownReason, ...],
  evidence: sorted tuple[TypeEvidence, ...],
)

TypeEvidence(
  kind, path, line, column, subject, detail_code
)
```

Evidence contains stable identifiers, bounded source facts, and locations. It
must not contain object `repr`, memory addresses, arbitrary application values,
or secrets.

Initial reason identifiers:

| Reason | Meaning |
|---|---|
| `unannotated` | No declaration exists. |
| `unsupported_annotation` | Syntax is valid but outside the recognized type subset. |
| `unresolved_name` | A named type has no trusted offline definition. |
| `dynamic_import` | The template or component target is not statically known. |
| `missing_signature` | A callable is known but has no canonical signature facts. |
| `dynamic_attribute` | Attribute shape cannot be proven statically. |
| `dynamic_item` | Item key or container shape cannot be proven. |
| `dynamic_call` | Callee identity is not statically known. |
| `variadic_unpack` | `*args` or `**kwargs` contents are not statically known. |
| `external_callable` | Registered callable lacks explicitly supplied safe metadata. |
| `cyclic_dependency` | A template graph cycle prevents a complete result. |
| `analysis_budget` | A documented analysis bound was reached. |
| `upstream_unknown` | The result depends on another unknown expression. |

Reason identifiers are internal stability points for tests and future explain
output. Exposing them through diagnostics, JSON, an LSP, or an extension API is
a separate public-contract review.

## Safe attribute and item inference

Analysis may infer only from IR facts already in memory.

### Attributes

- `Record{field: T}.field` yields `T`.
- Access to an undeclared field on a closed record is a proven `Error`.
- Access to an undeclared field on an open record is
  `Unknown(dynamic_attribute)`.
- A statically known template import namespace may expose a component signature
  as an attribute when the complete template graph proves the binding.
- Primitive methods, arbitrary Python classes, properties, descriptors, and
  `__getattr__` are unknown until a separately reviewed, static signature table
  supplies facts. Analysis never calls `getattr` or `hasattr` on application
  objects.

### Items

- `str[int]` and `str[slice]` yield `str` when the key kind is proven.
- `List[T][int]` and `Sequence[T][int]` yield `T`.
- `Tuple[...]` with a literal integer key yields that element; a dynamic integer
  yields the join of all element types.
- `Dict[K, V][key]` and `Mapping[K, V][key]` yield `V` only when the key type is
  assignable to `K`; an incompatible proven key is `Error`.
- A record or precise dictionary shape with a literal string key yields the
  declared field type.
- Other accesses yield `Unknown(dynamic_item)` rather than guessing from a
  runtime object.

Optional attribute/item operators add `none` to the successful result when the
receiver may be `none`. A non-optional access on a proven optional receiver is a
potential error, but introducing that diagnostic requires later approval.

## Canonical callable and component signature

One private signature must serve local/imported call validation, catalogs,
component diffing, and future Python t-string components:

```text
Signature(
  identity,
  kind: callable | component | region | python_component,
  parameters: tuple[Parameter, ...],
  return_type,
  slots: tuple[Slot, ...],
  context_requirements: tuple[ContextRequirement, ...],
  origin,
  unknowns,
)

Parameter(
  name,
  kind: positional_only | positional_or_keyword | keyword_only |
        var_positional | var_keyword,
  accepted_type,
  default: required | present | unknown,
  default_type,
  evidence,
)

Slot(
  name,
  required,
  bindings: tuple[Parameter, ...],
  evidence,
)
```

`identity` is a deterministic template key plus component name, or an explicit
registry identity for a Python component. It is not an object identity.
`origin` contains a source kind, template path, and location.

Current `{% def %}` and `{% region %}` adapters populate ordered parameters,
defaults, variadics, slots, and dependency names. Slot-binding types and return
types begin as unknown where the current AST has no proof. Public
`DefMetadata.annotation` remains the original raw spelling during the internal
phases.

For substitution and component diffing, a replacement signature is compatible
with the prior signature only if it accepts every call the prior signature
accepted. Therefore it must not add a required parameter, remove an accepted
parameter/variadic capability, narrow an accepted parameter type, remove a
supported slot, or add a required slot. It may add optional parameters/slots,
widen accepted parameter types, and narrow the return type. These are design
facts for #172, not approval to publish diff classifications now.

Python callable signatures are admitted only from an already trusted
registration boundary with explicit static metadata. Offline or untrusted
analysis does not import a module, evaluate a forward reference, read a
potentially active descriptor, or execute a PEP 649 annotation function. The
#159 adapter must separately define how trusted registration supplies facts.

## Soundness corpus

“Positive” means the rule proves compatibility or a result type. “Negative”
means it proves incompatibility or an invalid operation. “Unknown” means it
must decline to decide without producing false certainty.

| Rule | Positive case | Negative case | Unknown case |
|---|---|---|---|
| object top | every proven template value is assignable to `Object` | `Object` does not prove `str` | upstream type has no proof |
| tagged literals | `"x" <: str`, `1 <: int` | `"1"` is not `int` | literal produced by unknown callable |
| bool/int separation | `true <: bool` | `true` is not `int` | dynamically supplied flag without annotation |
| numeric widening | `int <: float` | `float` is not `int` | unresolved numeric alias |
| none/optional | `none <: str | none` | `none` is not `str` | unsupported optional spelling |
| union source | `str <: str | int` | `str | int` is not `str` | union contains unresolved member |
| branch join | `join(int, float) -> float` | join does not discard `bool` into `int` | either branch is unknown |
| narrowing meet | `meet(int, float) -> int` | `meet(bool, int) -> Never` | unknown predicate needs a transfer rule |
| literal widening | nine string literals widen to `str` | widening never makes `str` an `int` | source member is unknown |
| never | unreachable branch contributes no value to a join | reachable `str` is not `Never` | reachability depends on unknown predicate |
| error recovery | one proven bad item access owns one error | error is not accepted as a prop | downstream expression sees the existing error sentinel |
| unknown | later declaration may replace `unannotated` with `str` | unknown does not satisfy required `str` | dynamic call remains unknown |
| list invariance | `List[int] <: List[int]` | `List[int]` is not `List[float]` | element inference includes unknown |
| list read-only bridge | `List[int] <: Sequence[float]` | `Sequence[int]` is not mutable `List[int]` | unknown sequence origin |
| sequence covariance | `Sequence[int] <: Sequence[float]` | not mutable through the covariant view | element type is unknown |
| dict invariance | `Dict[str, int] <: Dict[str, int]` | not `Dict[str, float]` | dynamic `**mapping` |
| mapping covariance | `Dict[str, int] <: Mapping[str, float]` | wrong key type is rejected | key type is unknown |
| tuple covariance | `(int, str) <: (float, object)` | unequal fixed shapes do not subtype | dynamic tuple construction |
| record attribute | closed `{name: str}.name -> str` | closed `.missing` is an error | open `.missing` is unknown |
| sequence item | `List[str][int] -> str` | string key into list is an error | key type unknown |
| mapping item | `Mapping[str, int]["x"] -> int` | integer key is incompatible | mapping key/value unknown |
| optional item | `(List[str] | none)?[0] -> str | none` | ordinary item access still has optional risk | receiver unknown |
| annotation alias | `none` and `None` normalize identically | `list[int]` is not `dict[str, int]` | wrong generic arity or `MyModel` without catalog facts |
| callable variance | wider parameter and narrower return substitute safely | added required parameter breaks substitution | missing callable signature |
| component call | required props supplied with assignable types | known wrong/missing prop | dynamic callee or unpacked kwargs |
| component slot | retained optional slot is compatible | removing an accepted slot is breaking | dynamic slot name |
| static import | literal template path resolves known component signature | known component lacks requested prop | computed import path |
| application attribute | explicit offline record fact is usable | closed record disproves field | arbitrary class/property is never inspected |

Each implementation phase must turn its applicable rows into table-driven
tests with exact normalized types, tri-state assignability, unknown reasons, and
source evidence.

## Import closure and untrusted-analysis boundary

- The IR and normalizer use only the standard library and Kida AST/metadata
  types. They add no runtime dependency.
- Type-analysis modules remain lazy and must not join the isolated basic-render
  import closure. The current import-closure ratchet remains authoritative.
- Template paths resolve only through Kida loaders and the existing static
  template graph. Dynamic paths produce unknown.
- Application modules, framework models, filter bodies, properties,
  descriptors, and forward references are never imported or executed.
- Registered filters/tests/globals without explicit safe signature metadata are
  external unknowns. Runtime values are not sampled to infer a static type.
- Analysis budgets and cycles produce deterministic unknown evidence rather
  than partial guesses.
- No type fact may weaken sandbox, escaping, or runtime undefined behavior.

## Implementation decomposition

Every child below is independently testable and leaves current public behavior
unchanged unless its gate explicitly says otherwise.

1. **Private IR and algebra** — implement immutable variants, normalization,
   structural keys, join/meet, tri-state assignability, literal widening, and
   the primitive/container corpus. No parser or environment changes.
2. **Safe annotation normalizer** — normalize only current raw annotation forms
   from `DefParam` and `TemplateContext`; emit unknown reasons/evidence for
   unsupported forms. Prove no `eval`, import, or application lookup occurs.
3. **Canonical template signature adapter** — map `Def` and `Region` to the
   signature IR. Compare parameter/default/variadic/slot facts against
   `CallableSignaturePlan`, `_DefSignature`, and `DefMetadata` fixtures without
   changing those contracts.
4. **Signature consolidation** — migrate private local/imported call validators
   to the canonical adapter behind exact diagnostic and location parity tests.
   Public `DefMetadata` stays unchanged.
5. **Expression inference: literals and collections** — infer literals,
   names with declarations, unions, lists, tuples, dictionaries, basic
   operators, and branch joins. Add positive/negative/unknown tests.
6. **Safe attribute/item inference** — add record, sequence, mapping, and static
   import rules with hostile objects proving no runtime introspection occurs.
7. **Control-flow transfer** — loop-item/destructuring inference and sound
   narrowing for `is defined`, `is none`, truthiness, and match guards.
8. **Built-in callable metadata** — design internal signature facts for curated
   built-in filters/tests/globals. Any public registration or extension
   protocol is excluded and requires approval.
9. **Complete static template graph** — propagate canonical component
   signatures across literal imports, cycles, aliases, and forwarded slots;
   coordinate downstream canaries before stricter enforcement.
10. **Trusted Python-component adapter research** — define how #159 supplies
    already-loaded callable facts without imports or annotation evaluation.
11. **Diagnostics and explain output** — separately review error codes,
    severity/default behavior, JSON/LSP shape, safe edits, docs, and migration
    impact before surfacing inferred types or unknown reasons.

## Stop-and-ask boundaries

The RFC is design evidence, not approval for any of the following:

- a new AST node, template annotation grammar, tag, or formatter behavior;
- changes to generated Python annotations or runtime callable behavior;
- a public type/signature/extension protocol or new top-level export;
- an `Environment` flag, default filter/test/global metadata API, or config
  surface;
- runtime validation, coercion, imports, annotation evaluation, or execution of
  application code during analysis;
- new diagnostics, codes, severity, CLI/LSP/JSON fields, or stricter defaults;
- public `DefMetadata` field or semantic changes;
- shared mutable caches or concurrency-sensitive signature registries;
- import-closure growth, runtime dependencies, or eager authoring imports;
- sandbox or escaping semantic changes;
- catalog/diff compatibility becoming a published guarantee;
- compiler/analysis hot-path changes without benchmark evidence;
- downstream-enforced component changes without canary proof.

## Proof required before implementation is called complete

- Table-driven tests cover every soundness-corpus row on all three outcomes.
- Parser, compiler plan, analyzer, introspection metadata, and canonical
  signature facts agree on the same fixture corpus.
- Unsupported and dynamic cases preserve stable unknown reasons and locations.
- Hostile objects and annotations prove that analysis performs no imports,
  descriptor access, annotation evaluation, or calls.
- The isolated basic-render import closure does not increase.
- `make lint`, `make ty`, focused analysis tests, and `make verify-stability`
  pass for contract-affecting phases.
- Analysis benchmarks report cost for propagation or graph-wide phases; runtime
  warm render remains unchanged.
- Any later public behavior includes published docs, examples, changelog,
  downstream canaries, and an explicit parity matrix.

## Not now

- Reimplementing Python's full typing system or resolving arbitrary nominal
  application classes.
- Runtime prop coercion or validation.
- Treating unknown as success or as an automatic warning.
- Inferring types by rendering, importing application modules, or executing
  filters/globals.
- Encoding HTML safety as ordinary `str` subtyping.
- Publishing the internal IR as a stable schema before implementation evidence
  shows which facts consumers actually need.
