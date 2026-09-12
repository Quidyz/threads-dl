"""Page-level helpers, ported from threads-toolkit's src/utils/page-helpers.ts.

The DOM inspection itself has to run inside the browser, so it's kept as a
JS snippet (translated 1:1 from the original TypeScript, types stripped) and
invoked via Playwright's `page.evaluate`.
"""

from __future__ import annotations

from playwright.async_api import Page

_NOT_FOUND_MARKERS = (
    "找不到這個頁面",
    "Page not found",
    "ページが見つかりません",
    "페이지를 찾을 수 없습니다",
)

# Blocking images/fonts saves bandwidth; the <img> `src` attribute is still
# present in the DOM even though the browser never downloads the bytes.
# Deliberately NOT blocking "media": video URLs are captured by watching
# network responses (see extractor.py), which only fires for requests that
# are allowed to complete. Threads' <video> element often only carries a
# blob: URL until playback starts, so the network response is the only
# reliable source for the real CDN video URL — blocking it (as the upstream
# reference implementation does) risks silently losing every video.
_BLOCKED_RESOURCE_TYPES = {"image", "font"}

_DETECT_PAGE_ERROR_JS = """
() => {
    const body = document.body;
    const bodyText = body ? body.textContent || '' : '';
    const bodyTextLower = bodyText.toLowerCase();

    const loginTexts = ['Log in', '登入', 'ログイン', '로그인'];
    const buttons = document.querySelectorAll('button, a[role="button"]');
    let isLoginWall = false;
    for (const btn of buttons) {
        const text = (btn.textContent || '').trim();
        if (loginTexts.some((lt) => text.includes(lt))) {
            isLoginWall = true;
            break;
        }
    }
    if (!isLoginWall) {
        const loginLink = document.querySelector('[role="dialog"] a[href*="login"]');
        isLoginWall = loginLink !== null;
    }

    const rateLimitPatterns = [
        'rate limit', 'too many requests', 'try again later',
        '請稍後再試', '请稍后再试', 'しばらくしてからもう一度お試しください',
        '나중에 다시 시도', 'slow down', 'temporarily blocked',
        '暫時被封鎖', '暂时被封锁', 'wait a few minutes',
        '請等待幾分鐘', '请等待几分钟',
    ];
    const isRateLimited = rateLimitPatterns.some((p) => bodyTextLower.includes(p.toLowerCase()));

    const errorPatterns = [
        'Something went wrong', '出了點問題', '出了点问题',
        '問題が発生しました', '문제가 발생했습니다', 'Try again',
        'blocked', 'unavailable',
    ];
    const isErrorPage = errorPatterns.some((p) => bodyTextLower.includes(p.toLowerCase()));

    const mainContent = document.querySelector('div[role="main"]');
    const hasMainContent = mainContent !== null && mainContent.children.length > 0;
    const postLinkCount = document.querySelectorAll('a[href*="/post/"]').length;
    const isEmpty = postLinkCount === 0 && (!hasMainContent || bodyText.trim().length < 50);

    let errorMessage = 'Unknown error';
    if (isRateLimited) {
        errorMessage = 'Rate limited by Threads';
    } else {
        for (const p of errorPatterns) {
            if (bodyTextLower.includes(p.toLowerCase())) { errorMessage = p; break; }
        }
    }

    return { isLoginWall, isErrorPage, isRateLimited, isEmpty, hasMainContent, postLinkCount, errorMessage };
}
"""


async def detect_page_error(page: Page) -> dict:
    """Returns a dict with keys: is_login_wall, is_error_page, is_rate_limited,
    is_empty, has_main_content, post_link_count, error_message."""
    result = await page.evaluate(_DETECT_PAGE_ERROR_JS)
    return {
        "is_login_wall": result["isLoginWall"],
        "is_error_page": result["isErrorPage"],
        "is_rate_limited": result["isRateLimited"],
        "is_empty": result["isEmpty"],
        "has_main_content": result["hasMainContent"],
        "post_link_count": result["postLinkCount"],
        "error_message": result["errorMessage"],
    }


async def is_not_found_page(page: Page) -> bool:
    content = await page.content()
    return any(marker in content for marker in _NOT_FOUND_MARKERS)


async def block_heavy_resources(page: Page) -> None:
    async def _handler(route):
        if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", _handler)
