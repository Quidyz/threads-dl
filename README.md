# threads-dl

Download the text, images and video from a **public Threads (threads.net / threads.com) post** by URL. No login, no API key.

```bash
threads-dl "https://www.threads.com/@zuck/post/ABC123xyz" -o downloads/
```

```json
{
  "id": "ABC123xyz",
  "url": "https://www.threads.com/@zuck/post/ABC123xyz",
  "author": { "username": "zuck", "display_name": "Mark Zuckerberg", "is_verified": true, ... },
  "content": "...",
  "timestamp": "2026-01-01T12:00:00+00:00",
  "stats": { "likes": 142, "replies": 23, "reposts": 8, "shares": 5 },
  "images": ["https://scontent...cdninstagram.com/..."],
  "videos": ["https://scontent...cdninstagram.com/....mp4"],
  "links": []
}
```

## Why this exists

Neither [yt-dlp](https://github.com/yt-dlp/yt-dlp/issues/7523) nor [gallery-dl](https://github.com/mikf/gallery-dl/issues/4281) support Threads as of writing — both issues have been open for a year+ with no merged extractor. Threads is a heavy client-rendered app, so there is no simple `requests.get()` + regex way to pull a post's media: you need to actually render the page.

This package does that with a headless browser (Playwright) and gives you back plain data: post text/author/stats plus direct, downloadable media URLs.

## Install

```bash
pip install threads-dl
playwright install chromium
```

(or from source: `pip install -e .` inside a clone of this repo)

## CLI

```bash
threads-dl <post-url>                  # print JSON metadata to stdout
threads-dl <post-url> -o ./downloads   # also download every image/video found
threads-dl <post-url> --no-headless    # show the browser window (debugging)
threads-dl <post-url> --storage-state cookies.json   # see Authentication below
```

## Library

```python
import asyncio
from threads_dl import extract_post, download_media

async def main():
    post = await extract_post("https://www.threads.com/@zuck/post/ABC123xyz")
    print(post.content, post.videos, post.images)
    await download_media(post, "downloads/")

asyncio.run(main())
```

`extract_post()` raises a subclass of `ThreadsDlError` on failure:

| Exception | Meaning |
|---|---|
| `InvalidUrlError` | not a Threads post URL |
| `PostNotFoundError` | Threads returned 404 |
| `LoginWallError` | this post needs a logged-in session (see below) |
| `RateLimitedError` | your IP is being throttled — back off |
| `ExtractionError` | page loaded but the post markup couldn't be parsed (Threads changed their DOM, or unexpected content) |

## Authentication (optional)

Public posts don't need login. If Threads shows you a login wall for a particular post, export cookies from a logged-in Playwright session once:

```python
# one-time, interactive
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://www.threads.com/login")
    input("Log in in the opened window, then press Enter here...")
    page.context().storage_state(path="storageState.json")
```

Then pass `--storage-state storageState.json` (CLI) or `storage_state="storageState.json"` (library).

## How it works / limitations

- Launches headless Chromium, blocks image/font/media network requests (saves bandwidth — the `src` attributes are still present in the DOM without downloading the bytes), loads the post page, and:
  - reads image/video URLs straight out of the DOM
  - additionally intercepts network responses for `video/*` content-type or `.mp4`/`.m3u8` URLs, since Threads sometimes lazy-attaches the real video source after initial render
  - walks up from the post's permalink `<a>` to find the container that has like/comment/repost buttons, then extracts author/content/stats from it
- No official Threads API is used anywhere — this parses the public web UI, so it **will break** whenever Meta changes Threads' markup. If it stops working, check [issues](https://github.com/Quidyz/threads-dl/issues) or open one.
- Only fetches a single post. No profile/search/hashtag scraping, no pagination, no comments.
- Text matching supports English + Chinese/Japanese/Korean UI strings (Threads localizes button labels); other locales may not parse stats/timestamps correctly.

## Credits

The DOM-walking heuristic (find the post permalink, walk up to the container with ≥2 stat buttons, then read fields off it) and the network-interception trick for video URLs are adapted from [Chuanyin1202/threads-toolkit](https://github.com/Chuanyin1202/threads-toolkit) (Apache-2.0), a Node/Playwright/Apify Threads scraper. This project is an independent Python rewrite scoped specifically to single-post media downloading — it does not include that project's profile/search/hashtag features.

## Disclaimer

For educational and personal use. Scrapes Threads' public web interface, which isn't an official API — comply with Threads' Terms of Service and don't use this for bulk/abusive scraping. Not affiliated with Meta.

## License

MIT — see [LICENSE](LICENSE).
