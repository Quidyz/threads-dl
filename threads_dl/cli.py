from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .download import download_media
from .errors import ThreadsDlError
from .extractor import extract_post


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="threads-dl",
        description="Download text, images and videos from a public Threads post URL.",
    )
    parser.add_argument("url", help="Threads post URL, e.g. https://www.threads.com/@user/post/ABC123")
    parser.add_argument(
        "-o", "--output", metavar="DIR",
        help="Download media files into this directory (in addition to printing JSON metadata).",
    )
    parser.add_argument(
        "--no-headless", action="store_true",
        help="Run the browser with a visible window (useful for debugging login walls).",
    )
    parser.add_argument(
        "--storage-state", metavar="FILE",
        help="Path to a Playwright storageState.json (exported cookies) for posts behind a login wall.",
    )
    parser.add_argument(
        "--timeout", type=float, default=60.0,
        help="Page navigation timeout in seconds (default: 60).",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    storage_state = args.storage_state if args.storage_state else None
    try:
        post = await extract_post(
            args.url,
            headless=not args.no_headless,
            timeout=args.timeout,
            storage_state=storage_state,
        )
    except ThreadsDlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(post.to_dict(), ensure_ascii=False, indent=2))

    if args.output:
        saved = await download_media(post, args.output)
        for path in saved:
            print(f"saved: {path}", file=sys.stderr)
        if not saved and (post.images or post.videos):
            print("warning: found media URLs but none could be downloaded", file=sys.stderr)

    return 0


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
