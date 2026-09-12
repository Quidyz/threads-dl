from datetime import datetime, timezone

from threads_dl.text_utils import parse_relative_time, parse_stat_number


def test_parse_stat_number_plain():
    assert parse_stat_number("讚 2,049") == 2049


def test_parse_stat_number_k_suffix():
    assert parse_stat_number("1.5K") == 1500


def test_parse_stat_number_m_suffix():
    assert parse_stat_number("2M") == 2_000_000


def test_parse_stat_number_no_digits():
    assert parse_stat_number("讚") == 0


def test_parse_relative_time_minutes():
    result = parse_relative_time("5m")
    parsed = datetime.fromisoformat(result)
    delta = datetime.now(timezone.utc) - parsed
    assert 4 * 60 <= delta.total_seconds() <= 6 * 60


def test_parse_relative_time_unrecognized_returns_empty():
    assert parse_relative_time("not a time") == ""


def test_parse_relative_time_empty_input():
    assert parse_relative_time("") == ""
