from threads_dl.url_utils import extract_post_id, normalize_post_url


def test_normalize_adds_protocol():
    assert normalize_post_url("www.threads.net/@user/post/ABC123").startswith("https://")


def test_normalize_rewrites_net_to_com():
    result = normalize_post_url("https://www.threads.net/@user/post/ABC123")
    assert result == "https://www.threads.com/@user/post/ABC123"


def test_normalize_rejects_non_threads_url():
    assert normalize_post_url("https://example.com/post/ABC123") is None


def test_normalize_rejects_empty():
    assert normalize_post_url("") is None


def test_extract_post_id_dotted_username():
    url = "https://www.threads.com/@quidyz.of/post/DcQ19PgAG_d/media"
    assert extract_post_id(url) == "DcQ19PgAG_d"


def test_extract_post_id_missing():
    assert extract_post_id("https://www.threads.com/@user") is None
