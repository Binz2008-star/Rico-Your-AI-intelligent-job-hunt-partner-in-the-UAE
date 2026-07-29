# -*- coding: utf-8 -*-
"""Synthetic multi-user test-data factory (PR1 of the reliability test program).

See ``tests/factory/personas.py`` for the persona/CV-fixture matrix and
``tests/factory/isolation.py`` for cross-user isolation fixture helpers.

This package produces no network calls, no real user data, and no
production-code changes. It is deterministic: the same ``run_id`` always
yields the same persona set and the same synthetic CV bytes.
"""
from __future__ import annotations
