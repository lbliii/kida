---
title: API Reference
description: Kida API documentation auto-generated from source
draft: false
weight: 90
lang: en
type: doc
tags:
- api
- reference
keywords:
- api
- environment
- template
- filters
category: api
cascade:
  type: doc
icon: bookmark
---

# API Reference

Auto-generated API documentation from Kida source code.

:::{cards}
:columns: 2
:gap: medium

:::{card} Environment
:icon: settings
:link: ./environment/
:description: Configuration and template management hub
:::{/card}

:::{card} Template
:icon: file-code
:link: ./template/
:description: Compiled template with render() interface
:::{/card}

:::{card} Loaders
:icon: folder
:link: ./loaders/
:description: FileSystemLoader, DictLoader, custom loaders
:::{/card}

:::{card} Exceptions
:icon: alert-triangle
:link: ./exceptions/
:description: TemplateError, TemplateSyntaxError, UndefinedError
:::{/card}

:::{/cards}

## Quick Reference

```python
from kida import Environment, FileSystemLoader, Markup

# Create environment with loader
env = Environment(loader=FileSystemLoader("templates/"))

# Load and render template
template = env.get_template("page.html")
html = template.render(title="Hello", items=[1, 2, 3])

# Mark content as safe HTML
safe_html = Markup("<b>Bold</b>")
```

See the [[docs/reference/api|API Quick Reference]] for common patterns.

