"""Framework integrations for Kida template engine.

Each integration is its own self-contained module — import the one you
need directly:

    from kida.contrib.flask import KidaFlask
    from kida.contrib.django import KidaDjangoBackend
    from kida.contrib.starlette import KidaStarlette

This package intentionally does not re-export anything: integrations are
optional and may pull in framework-specific imports at module load time.
"""
