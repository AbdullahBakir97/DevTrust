"""Agent-PR Reviewer GitHub App.

A FastAPI service that wraps the `apr` engine. On pull-request events
from GitHub, it fetches the PR's metadata, downloads the changed files
to a temp dir, runs `apr.engine.review()`, and posts the verdict as a
sticky PR comment.

See README.md for the full design and deployment notes.
"""

__version__ = "0.0.1"
