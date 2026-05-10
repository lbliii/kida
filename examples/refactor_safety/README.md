# Refactor Safety

A compact before/after demo for template refactors.

## Run

```bash
cd examples/refactor_safety
python app.py
```

## Check The Broken Templates

```bash
kida check templates/broken --validate-calls --lint-fragile-paths
```

## What It Shows

- typed component props caught by `kida check --validate-calls`
- duplicate keyword arguments rejected by the parser
- fragile same-folder include paths flagged before a folder move
- missing context detected with `validate_context()`
- relative imports in the passing tree so components can move with their pages
