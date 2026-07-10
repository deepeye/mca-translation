import pytest
from app.services.review_language_guard import contains_cjk, strip_cjk


def test_contains_cjk_detects_chinese():
    assert contains_cjk("侥幸 psychology") is True


def test_contains_cjk_false_for_ascii():
    assert contains_cjk("psychology") is False


def test_strip_cjk_removes_chinese():
    assert strip_cjk("resolutely overcome complacency and侥幸 psychology") == "resolutely overcome complacency and psychology"
