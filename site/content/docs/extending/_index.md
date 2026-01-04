---
title: Extending
description: Extend Kida with custom filters, tests, globals, and loaders
draft: false
weight: 50
lang: en
type: doc
tags:
- extending
keywords:
- extending
- custom
- filters
- tests
- loaders
category: extending
cascade:
  type: doc
icon: starburst
---

# Extending

Extend Kida with custom functionality.

:::{cards}
:columns: 2
:gap: medium

:::{card} Custom Filters
:icon: filter
:link: ./custom-filters
:description: Transform values with `| filter`
Add domain-specific value transformations.
:::{/card}

:::{card} Custom Tests
:icon: check-circle
:link: ./custom-tests
:description: Create `is test` predicates
Build boolean tests for conditionals.
:::{/card}

:::{card} Custom Globals
:icon: globe
:link: ./custom-globals
:description: Add global functions and variables
Make utilities available everywhere.
:::{/card}

:::{card} Custom Loaders
:icon: folder
:link: ./custom-loaders
:description: Load from databases, APIs, etc.
Build custom template sources.
:::{/card}

:::{/cards}

## Quick Reference

```python
from kida import Environment

env = Environment()

# Custom filter
@env.filter()
def double(value):
    return value * 2

# Custom test
@env.test()
def is_even(value):
    return value % 2 == 0

# Custom global
env.add_global("site_name", "My Site")

# Use in templates
# {{ count | double }}
# {% if count is even %}
# {{ site_name }}
```

