from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

import httpx

from .models import ThreadsPost

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.threads.com/",
}


async def download_media(post: ThreadsPost, dest_dir: str | Path, *, timeout: float = 60.0) -> list[Path]:
    """Downloads every image/video URL on `post` into `dest_dir`.

    Files are named `<post.id>_<index>.<ext>`. Returns the list of paths
    written, in the order: videos first, then images.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=timeout) as client:
        for index, url in enumerate((*post.videos, *post.images), start=1):
            path = await _download_one(client, url, dest, post.id, index)
            if path is not None:
                saved.append(path)
    return saved


async def _download_one(client: httpx.AsyncClient, url: str, dest: Path, post_id: str, index: int) -> Path | None:
    try:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            ext = _guess_ext(url, resp.headers.get("content-type"))
            path = dest / f"{post_id}_{index}{ext}"
            f = await asyncio.to_thread(open, path, "wb")
            try:
                async for chunk in resp.aiter_bytes():
                    await asyncio.to_thread(f.write, chunk)
            finally:
                await asyncio.to_thread(f.close)
        return path
    except httpx.HTTPError:
        return None


def _guess_ext(url: str, content_type: str | None) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix
    if suffix and len(suffix) <= 5:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed
    return ".bin"
