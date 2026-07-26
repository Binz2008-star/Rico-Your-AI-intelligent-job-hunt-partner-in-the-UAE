"""Domain layer — framework-free rules extracted from the existing services.

Modules here must not import FastAPI, the database, repositories, or any
service that performs I/O. They take already-loaded values and return
decisions, so the same rule can be reused by a router, a chat path, or a
background job without any of them re-deriving it.
"""
