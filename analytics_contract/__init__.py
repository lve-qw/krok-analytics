"""Canonical analytics.csv contract, validator and dashboard.

This package is self-contained: it does not import the analysis pipeline. The
only optional coupling is `registry.load_project_registries`, which reads the
project's `config.py` when it is importable.
"""
