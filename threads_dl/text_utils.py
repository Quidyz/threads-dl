"""Text/number parsing helpers, ported from threads-toolkit's src/utils/parser.ts
(parseRelativeTime / parseStatNumber)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_EN_RELATIVE_RE = re.compile(r"(\d+)\s*(s|m|h|d|w)", re.IGNORECASE)
_CJK_RELATIVE_RE = re.compile(r"(\d+)\s*(秒鐘?|秒|分鐘?|分|小時|小时|時|天|日|週|周|星期|礼拜|月)\s*前?")
_STAT_NUMBER_RE = re.compile(r"[\d,]+\.?\d*[KkMm]?")


def parse_relative_time(text: str) -> str:
    """Converts a relative-time label ("5m", "2h", "3天前") to an ISO-8601
    timestamp. Returns "" if the format isn't recognized — caller decides
    what to do (e.g. fall back to "now" or drop the field)."""
    if not text:
        return ""
    lowered = text.strip().lower()
    now = datetime.now(timezone.utc)

    if "just now" in lowered or "now" in lowered or "剛剛" in text:
        return now.isoformat()

    en_match = _EN_RELATIVE_RE.search(lowered)
    if en_match:
        value = int(en_match.group(1))
        unit = en_match.group(2).lower()
        delta = {
            "s": timedelta(seconds=value),
            "m": timedelta(minutes=value),
            "h": timedelta(hours=value),
            "d": timedelta(days=value),
            "w": timedelta(weeks=value),
        }.get(unit)
        if delta is not None:
            return (now - delta).isoformat()

    zh_match = _CJK_RELATIVE_RE.search(text)
    if zh_match:
        value = int(zh_match.group(1))
        unit = zh_match.group(2)
        if "秒" in unit:
            delta = timedelta(seconds=value)
        elif "分" in unit:
            delta = timedelta(minutes=value)
        elif any(u in unit for u in ("小時", "小时", "時")):
            delta = timedelta(hours=value)
        elif any(u in unit for u in ("天", "日")):
            delta = timedelta(days=value)
        elif any(u in unit for u in ("週", "周", "星期", "礼拜")):
            delta = timedelta(weeks=value)
        elif "月" in unit:
            delta = timedelta(days=value * 30)  # approximate, matches upstream
        else:
            return ""
        return (now - delta).isoformat()

    return ""


def parse_stat_number(text: str) -> int:
    """Parses engagement counters like "讚 2,049", "1.5K", "2M" -> int."""
    match = _STAT_NUMBER_RE.search(text or "")
    if not match:
        return 0
    num_str = match.group(0).replace(",", "")
    if re.search(r"[Kk]", num_str):
        return round(float(re.sub(r"[Kk]", "", num_str)) * 1_000)
    if re.search(r"[Mm]", num_str):
        return round(float(re.sub(r"[Mm]", "", num_str)) * 1_000_000)
    try:
        return int(num_str)
    except ValueError:
        return 0
