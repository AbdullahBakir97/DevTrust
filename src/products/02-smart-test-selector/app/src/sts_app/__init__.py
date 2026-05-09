"""Smart Test Selector GitHub App.

A small FastAPI service that wraps the `sts` engine. On pull-request
events from GitHub, it fetches the PR's changed files + repository tree,
runs the selector, and posts the verdict as a sticky PR comment.

See README.md for the full design and deployment notes.
"""

__version__ = "0.0.3"
