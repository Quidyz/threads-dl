class ThreadsDlError(Exception):
    """Base error for all threads-dl failures."""


class InvalidUrlError(ThreadsDlError):
    """The given string is not a recognizable Threads post URL."""


class PostNotFoundError(ThreadsDlError):
    """Threads returned a 404 / "page not found" for this post."""


class LoginWallError(ThreadsDlError):
    """Threads is hiding this content behind a login wall.

    Retry with a `storage_state` (exported Playwright cookies) from a logged-in
    session — see README "Authentication" section.
    """


class RateLimitedError(ThreadsDlError):
    """Threads is rate-limiting this IP. Back off and retry later."""


class ExtractionError(ThreadsDlError):
    """The page loaded but the post content could not be parsed."""
