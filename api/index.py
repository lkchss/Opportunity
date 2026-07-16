"""Vercel serverless entrypoint for the Law School Matcher.

Vercel's @vercel/python runtime serves the module-level ``app`` (a WSGI
callable). All paths — the SPA shell, static assets, SEO landing pages, and the
/api/* endpoints — are handled by the Flask app in ``law/server.py``;
``vercel.json`` rewrites every request to this function.

Note: the in-memory usage counters in ``law/analytics`` are per-invocation on
serverless and reset between cold starts, so ``GET /stats`` reflects only one
instance. The durable, aggregate record is the per-event ``usage {...}`` line
emitted to stdout, captured in Vercel's log stream.
"""

from law.server import app  # noqa: F401 — Vercel looks up the `app` WSGI callable

# Alias some platforms expect; harmless if unused.
application = app
