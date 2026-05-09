"""Stream + extract a GitHub repository tarball to a temp directory.

Why tarballs and not `git clone`:
  - No `git` binary required on the host.
  - GitHub's tarball endpoint authenticates via the same installation
    token we already mint.
  - We only need a snapshot at a specific commit -- never `git pull`.

Safety properties:
  - **Zip-slip / tar-slip protection.** Reject any `..` path component
    (defense in depth: even an in-dest path with `..` escapes the
    expected single-root layout) AND check the resolved path against
    `dest`.
  - **Absolute-path rejection.** Members starting with `/` are refused.
  - **Symlink rejection.** Symlinks are skipped silently.
  - **Size cap.** Streaming download stops once `max_bytes` are written.
"""

from __future__ import annotations

import io
import logging
import tarfile
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CloneError(RuntimeError):
    """Raised when we cannot produce a usable repo snapshot."""


class TarballTooLargeError(CloneError):
    """Raised when the tarball exceeds the configured size cap."""


async def stream_tarball_to_buffer(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    ref: str,
    *,
    max_bytes: int,
) -> io.BytesIO:
    """Download `/repos/{o}/{r}/tarball/{ref}` into an in-memory buffer.

    Raises `TarballTooLargeError` if the response body exceeds `max_bytes`.
    """
    url = f"/repos/{owner}/{repo}/tarball/{ref}"
    buf = io.BytesIO()
    written = 0

    async with client.stream("GET", url, follow_redirects=True) as resp:
        if resp.status_code >= 400:
            raise CloneError(
                f"GET {url} returned {resp.status_code}: "
                f"{(await resp.aread()).decode('utf-8', errors='replace')[:200]}"
            )
        async for chunk in resp.aiter_bytes():
            written += len(chunk)
            if written > max_bytes:
                raise TarballTooLargeError(f"tarball exceeds max_bytes={max_bytes}")
            buf.write(chunk)

    buf.seek(0)
    return buf


def _is_within(directory: Path, target: Path) -> bool:
    """True if `target` resolves to a path inside `directory`."""
    try:
        target.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def extract_safely(
    tarball: io.BytesIO,
    dest: Path,
    *,
    max_files: int = 50_000,
) -> Path:
    """Extract a gzipped tarball into `dest` with safety checks.

    Returns the single top-level directory inside the tarball -- GitHub
    tarballs always have exactly one top-level dir named
    `{owner}-{repo}-{short_sha}`.
    """
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    extracted_files = 0
    top_dir_name: str | None = None

    with tarfile.open(fileobj=tarball, mode="r:gz") as tf:
        for member in tf:
            extracted_files += 1
            if extracted_files > max_files:
                raise CloneError(f"tarball has more than {max_files} entries; refusing")

            if member.issym() or member.islnk():
                logger.debug("skipping symlink/hardlink: %s", member.name)
                continue
            if not (member.isfile() or member.isdir()):
                logger.debug("skipping non-file/dir: %s (%s)", member.name, member.type)
                continue

            # Defense-in-depth zip-slip protection.
            normalized_name = member.name.replace("\\", "/")
            if normalized_name.startswith("/"):
                raise CloneError(f"tarball entry has absolute path: {member.name}")
            if ".." in normalized_name.split("/"):
                raise CloneError(f"tarball entry contains parent traversal: {member.name}")
            target = (dest / member.name).resolve()
            if not _is_within(dest, target):
                raise CloneError(f"tarball entry escapes destination: {member.name}")

            top = member.name.split("/", 1)[0] if member.name else ""
            if top_dir_name is None:
                top_dir_name = top
            elif top and top != top_dir_name:
                continue

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            data = tf.extractfile(member)
            if data is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as out:
                out.write(data.read())

    if top_dir_name is None:
        raise CloneError("tarball was empty")

    root = (dest / top_dir_name).resolve()
    if not root.is_dir():
        raise CloneError(f"expected top-level dir {top_dir_name} not found after extract")
    return root


async def fetch_and_extract(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    ref: str,
    dest_parent: Path,
    *,
    max_bytes: int,
) -> Path:
    """End-to-end: stream + extract. Returns path to the extracted root."""
    buf = await stream_tarball_to_buffer(client, owner, repo, ref, max_bytes=max_bytes)
    return extract_safely(buf, dest_parent)


def diff_filenames_to_repo_paths(
    file_rows: list[dict[str, Any]],
) -> list[str]:
    """Convert GitHub's PR-files response into POSIX-style paths.

    Skips removed files; dedupes.
    """
    out: list[str] = []
    seen: set[str] = set()
    for row in file_rows:
        path = row.get("filename")
        if not isinstance(path, str) or not path:
            continue
        if row.get("status") == "removed":
            continue
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out
