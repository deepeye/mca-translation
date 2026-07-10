from app.services.review_han_guard import contains_han, strip_han


def test_contains_han_detects_chinese():
    assert contains_han("侥幸 psychology") is True


def test_contains_han_false_for_ascii():
    assert contains_han("psychology") is False


def test_strip_han_removes_chinese():
    assert strip_han("resolutely overcome complacency and侥幸 psychology") == "resolutely overcome complacency and psychology"
