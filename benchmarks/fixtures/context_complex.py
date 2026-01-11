from __future__ import annotations

COMPLEX_CONTEXT = {
    "heading": "Benchmark Page",
    "description": "Complex layout with inheritance and includes",
    "nav": [
        {"href": "#intro", "label": "Intro"},
        {"href": "#body", "label": "Body"},
        {"href": "#footer", "label": "Footer"},
    ],
    "footer": "Rendered by Kida benchmarks",
    "article": {
        "title": "Template Engine Performance",
        "subtitle": "Validating claims with reproducible data",
        "sections": [
            {"title": "Overview", "body": "Benchmarking approach and goals."},
            {"title": "Methodology", "body": "Warmups, iterations, and metrics."},
            {"title": "Results", "body": "Compare Kida with Jinja2 baselines."},
        ],
        "tags": ["performance", "benchmark", "kida", "jinja2"],
    },
}
