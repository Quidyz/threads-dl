"""Core extraction logic.

The DOM-walking heuristic ("find the post link, then walk up parents until a
container with >=2 like/comment/repost buttons is found") and the field
parsing (author, content, stats, images, videos) are ported from
threads-toolkit's src/utils/parser.ts (parsePostFromElement /
extractSinglePostFromPage), released under Apache-2.0:
https://github.com/Chuanyin1202/threads-toolkit

That logic only exists as in-browser DOM code, so it's kept as a single JS
snippet here (types stripped, otherwise translated line-for-line) and run via
Playwright's `evaluate`. Everything else — browser lifecycle, retries, error
classification, the public Python API — is new.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from playwright.async_api import Page, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .errors import (
    ExtractionError,
    InvalidUrlError,
    LoginWallError,
    PostNotFoundError,
    RateLimitedError,
)
from .models import Author, PostStats, ThreadsPost
from .page_helpers import block_heavy_resources, detect_page_error, is_not_found_page
from .text_utils import parse_relative_time
from .url_utils import extract_post_id, normalize_post_url

logger = logging.getLogger(__name__)

_VIDEO_URL_RE = re.compile(r"\.(mp4|m3u8)(\?|$)", re.IGNORECASE)

# Ported from parser.ts::parsePostFromElement. Takes {id, networkVideos} and
# returns the raw field dict, or null if no suitable container is found.
_EXTRACT_POST_JS = r"""
(arg) => {
    const { id, networkVideos } = arg;

    const firstLink = document.querySelector('a[href*="/post/"]');
    if (!firstLink) return null;

    let container = firstLink.parentElement;
    let depth = 0;
    const MAX_DEPTH = 15;
    let found = null;
    while (container && depth < MAX_DEPTH) {
        const roleButtons = container.querySelectorAll('div[role="button"]');
        let statsCount = 0;
        for (const btn of roleButtons) {
            const text = btn.textContent || '';
            if (
                text.includes('讚') || text.includes('留言') || text.includes('轉發') ||
                /^Like/i.test(text) || /^Comment/i.test(text) || /^Repost/i.test(text)
            ) {
                statsCount++;
            }
        }
        if (statsCount >= 2) { found = container; break; }
        container = container.parentElement;
        depth++;
    }
    if (!found) return null;

    // Get post URL / author username
    const postLink = found.querySelector('a[href*="/post/"]');
    const href = postLink ? postLink.getAttribute('href') || '' : '';
    const urlMatch = href.match(/\/@([^/]+)\/post\/([A-Za-z0-9_-]+)/);
    const username = urlMatch ? urlMatch[1] : 'unknown';

    // The "found" container can be wider than just this one post — it may
    // also wrap the next reply or a quoted post, since Threads doesn't put
    // a clean per-post boundary in the DOM. The next post-permalink link
    // that points to a DIFFERENT post ID marks where that other post
    // starts (the current post itself is often linked more than once —
    // e.g. the username and the timestamp are separate <a> tags to the
    // same post — so comparing by ID, not by node identity, matters).
    const currentPostId = urlMatch ? urlMatch[2] : null;
    const boundaryLink = Array.from(found.querySelectorAll('a[href*="/post/"]')).find((l) => {
        const m = (l.getAttribute('href') || '').match(/\/post\/([A-Za-z0-9_-]+)/);
        return m && m[1] !== currentPostId;
    });
    const isBeforeBoundary = (el) => {
        if (!boundaryLink) return true;
        // eslint-disable-next-line no-bitwise
        return !!(el.compareDocumentPosition(boundaryLink) & Node.DOCUMENT_POSITION_FOLLOWING);
    };

    const usernameLink = found.querySelector(`a[href="/@${username}"]`);
    const displayName = (usernameLink && usernameLink.textContent && usernameLink.textContent.trim()) || username;

    const avatarImg = found.querySelector('img[alt*="大頭貼"], img[alt*="profile"], img[alt*="avatar"]');
    const avatarUrl = avatarImg ? avatarImg.getAttribute('src') || undefined : undefined;

    const verifiedBadge = found.querySelector('svg[aria-label*="已驗證"], svg[aria-label*="Verified"], img[alt*="已驗證"], img[alt*="Verified"]');
    const isVerified = verifiedBadge !== null;

    // Content text, scoped to before the boundary (see isBeforeBoundary above).
    // A few section headings (not post content) can still appear before that
    // boundary — e.g. "Related threads" introduces the list of other posts
    // whose links define the boundary in the first place, so it always sits
    // just inside it.
    const NON_CONTENT_HEADINGS = new Set([
        'related threads', '相關串文', '相关串文',
        'author', '作者',
    ]);
    const texts = [];
    const textElements = found.querySelectorAll('div[dir="auto"], span[dir="auto"]');
    for (const el of textElements) {
        if (!isBeforeBoundary(el)) break;
        if (el.closest('[role="button"]') || el.closest('a')) continue;
        const text = (el.textContent || '').trim();
        if (NON_CONTENT_HEADINGS.has(text.toLowerCase())) continue;
        if (
            text.length > 5 &&
            text !== username &&
            text !== displayName &&
            !text.match(/^\d+[小時分鐘秒天週月年]?前?$/) &&
            !text.match(/^\d+[mhd]$/) &&
            !text.match(/^[\d,]+$/) &&
            !text.match(/^\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}$/) &&
            !text.match(/^[\d,.]+[KkMm]?\s*(views?|次瀏覽|次浏览)$/i) &&
            !text.match(/^(讚|留言|轉發|分享|翻譯|Like|Comment|Repost|Share|Translate)/i) &&
            !text.toLowerCase().includes('trouble playing this video')
        ) {
            // Threads appends a "Translate"/"Learn more" affordance right inside
            // the same text node as the paragraph, not as a separate element —
            // strip it per-paragraph, not just once at the very end.
            const cleaned = text
                .replace(/[\s ]*(Learn more|了解更多)[\s ]*$/i, '')
                .replace(/[\s ]*(Translate|翻譯)[\s ]*$/i, '')
                .trim();
            if (cleaned) texts.push(cleaned);
        }
    }
    let content = texts.join('\n\n').trim();

    // Timestamp
    const timeEl = found.querySelector('time');
    const timestamp = timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent || '') : '';

    // External links
    const links = [];
    for (const a of found.querySelectorAll('a[href^="http"]')) {
        const externalHref = a.getAttribute('href') || '';
        if (externalHref && !externalHref.includes('threads.com')) links.push(externalHref);
    }

    // Stats
    let likes = 0, replies = 0, reposts = 0, shares = 0;
    const parseNum = (text) => {
        const m = text.match(/[\d,.]+[KkMm]?/);
        if (!m) return 0;
        const s = m[0].replace(/,/g, '');
        if (/[Kk]$/.test(s)) return Math.round(parseFloat(s.slice(0, -1)) * 1000);
        if (/[Mm]$/.test(s)) return Math.round(parseFloat(s.slice(0, -1)) * 1000000);
        return parseInt(s, 10) || 0;
    };
    for (const btn of found.querySelectorAll('div[role="button"]')) {
        const text = btn.textContent || '';
        const num = parseNum(text);
        if (text.includes('讚') || /like/i.test(text)) likes = num;
        else if (text.includes('留言') || text.includes('回覆') || /comment|reply/i.test(text)) replies = num;
        else if (text.includes('轉發') || /repost/i.test(text)) reposts = num;
        else if (text.includes('分享') || /share/i.test(text)) shares = num;
    }

    // Images (exclude avatars, scoped to before the boundary)
    const images = [];
    for (const img of found.querySelectorAll('img')) {
        if (!isBeforeBoundary(img)) continue;
        const src = img.getAttribute('src');
        const alt = img.getAttribute('alt') || '';
        if (src && !src.includes('profile') && !alt.includes('大頭貼') && !alt.includes('profile') && !alt.includes('avatar')) {
            images.push(src);
        }
    }

    // Videos: DOM <video>/<source> elements (scoped), plus network-captured URLs passed in
    const videos = [];
    for (const v of found.querySelectorAll('video source, video')) {
        if (!isBeforeBoundary(v)) continue;
        const src = v.getAttribute('src');
        if (src) videos.push(src);
    }
    for (const v of (networkVideos || [])) {
        if (!videos.includes(v)) videos.push(v);
    }

    return {
        id, username, displayName, avatarUrl, isVerified,
        content: content ? content.slice(0, 2000) : '',
        timestamp, likes, replies, reposts, shares, images, videos, links,
        href,
    };
}
"""


async def _extract_from_page(page: Page, post_id: str, post_url: str, network_videos: list[str]) -> ThreadsPost | None:
    data: dict[str, Any] | None = await page.evaluate(
        _EXTRACT_POST_JS, {"id": post_id, "networkVideos": network_videos}
    )
    if data is None:
        return None

    author = Author(
        username=data["username"],
        display_name=data["displayName"] or data["username"],
        profile_url=f"https://www.threads.com/@{data['username']}",
        avatar_url=data.get("avatarUrl"),
        is_verified=bool(data["isVerified"]),
    )
    timestamp = data["timestamp"] or ""
    if timestamp and not re.match(r"^\d{4}-\d{2}-\d{2}", timestamp):
        timestamp = parse_relative_time(timestamp)

    return ThreadsPost(
        id=data["id"],
        url=post_url,
        author=author,
        content=data["content"],
        timestamp=timestamp,
        stats=PostStats(
            likes=data["likes"], replies=data["replies"], reposts=data["reposts"], shares=data["shares"]
        ),
        images=list(data["images"]),
        videos=list(data["videos"]),
        links=list(data["links"]),
    )


async def extract_post(
    url: str,
    *,
    headless: bool = True,
    timeout: float = 60.0,
    storage_state: dict | str | None = None,
) -> ThreadsPost:
    """Fetch a single public Threads post and return its text/author/stats
    plus direct image and video URLs. No login required for public posts.

    Raises InvalidUrlError, PostNotFoundError, LoginWallError,
    RateLimitedError or ExtractionError on failure.
    """
    normalized = normalize_post_url(url)
    if normalized is None:
        raise InvalidUrlError(f"Not a Threads URL: {url}")
    # A /share/<code>/ link (from the app's Share button) has no post ID of
    # its own — Threads redirects it to the canonical @user/post/<id> URL
    # client-side, so we resolve the real ID from page.url after navigating
    # instead of failing here.
    post_id = extract_post_id(normalized)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless, args=["--disable-gpu", "--no-sandbox"])
        try:
            context = await browser.new_context(storage_state=storage_state)
            page = await context.new_page()

            video_urls: set[str] = set()

            def _on_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if ct.startswith("video/") or _VIDEO_URL_RE.search(response.url):
                        video_urls.add(response.url)
                except Exception:
                    # Fire-and-forget event handler; a closed connection/page
                    # mid-response shouldn't crash extraction.
                    logger.debug("Ignoring error while inspecting response", exc_info=True)

            page.on("response", _on_response)
            await block_heavy_resources(page)

            await page.goto(normalized, wait_until="domcontentloaded", timeout=timeout * 1000)

            try:
                await page.wait_for_selector('a[href*="/post/"]', timeout=15_000)
            except PlaywrightTimeoutError:
                info = await detect_page_error(page)
                if info["is_rate_limited"]:
                    raise RateLimitedError("Threads is rate-limiting this IP; back off and retry later.")
                if info["is_login_wall"]:
                    raise LoginWallError(
                        "Threads is showing a login wall for this post. "
                        "Pass storage_state from a logged-in session to retry."
                    )
                if info["is_error_page"]:
                    raise ExtractionError(f"Threads returned an error page: {info['error_message']}")
                if await is_not_found_page(page):
                    raise PostNotFoundError(f"Post not found: {url}")
                raise ExtractionError(f"Failed to load post page: {url}")

            # Now that navigation (and any share-link redirect) has settled,
            # resolve the real post ID and canonical URL from the address bar.
            resolved_id = extract_post_id(page.url)
            if resolved_id:
                post_id = resolved_id
                normalized = normalize_post_url(page.url) or normalized
            if post_id is None:
                raise InvalidUrlError(f"Could not find a post ID in URL: {url}")

            # Threads only requests the real video CDN URL once its player
            # detects the post is in view (IntersectionObserver), which a
            # headless page that never scrolls may not trigger reliably.
            # Nudge it with a trivial scroll, then poll for the network
            # capture instead of guessing a fixed delay from the DOM (a
            # <video> element checked for presence here is unreliable: it's
            # often mounted by React after this point anyway).
            await page.evaluate("() => { window.scrollBy(0, 200); window.scrollBy(0, -200); }")
            for _ in range(10):  # up to ~3s; observed capture in practice: <1s
                if video_urls:
                    break
                await asyncio.sleep(0.3)

            post = await _extract_from_page(page, post_id, normalized, list(video_urls))
            if post is None:
                raise ExtractionError(f"Failed to locate post content on page: {url}")
            return post
        finally:
            await browser.close()
