"""URL normalization, ported from threads-toolkit's src/actions/post.ts
(normalizePostUrl / extractPostId)."""

from __future__ import annotations

import re

_POST_ID_RE = re.compile(r"/post/([A-Za-z0-9_-]+)")


def normalize_post_url(url: str) -> str | None:
    """Accepts threads.net or threads.com, with or without protocol.

    Returns the URL with domain normalized to threads.com, or None if the
    string doesn't look like a Threads URL at all.
    """
    if not url:
        return None
    normalized = url.strip()
    if "threads.net" not in normalized and "threads.com" not in normalized:
        return None
    if not normalized.startswith("http"):
        normalized = f"https://{normalized}"
    return normalized.replace("threads.net", "threads.com")


def extract_post_id(url: str) -> str | None:
    match = _POST_ID_RE.search(url)
    return match.group(1) if match else None
