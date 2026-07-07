"""Framework integrations for Kida template engine.

Each integration is its own self-contained module — import the one you
need directly:

    from kida.contrib.flask import init_kida, render_template
    from kida.contrib.django import KidaTemplates as DjangoKidaTemplates
    from kida.contrib.starlette import KidaTemplates as StarletteKidaTemplates

This package intentionally does not re-export anything: integrations are
optional and may pull in framework-specific imports at module load time.
"""
