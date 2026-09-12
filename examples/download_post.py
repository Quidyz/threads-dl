"""Minimal library usage example.

Run with:
    python examples/download_post.py https://www.threads.com/@user/post/ABC123
"""

import asyncio
import sys

from threads_dl import download_media, extract_post


async def main(url: str) -> None:
    post = await extract_post(url)
    print(f"@{post.author.username}: {post.content[:80]!r}")
    print(f"images: {len(post.images)}, videos: {len(post.videos)}")

    if post.images or post.videos:
        saved = await download_media(post, "downloads")
        for path in saved:
            print(f"saved -> {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <threads-post-url>")
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1]))
