import traceback

import pytest

from leropilot.exceptions import reraise_if_expected


def _raise_value():
    raise ValueError("boom")


def wrapper_raise_expected():
    try:
        _raise_value()
    except Exception as e:
        reraise_if_expected(e, (ValueError,))


def test_reraise_expected_preserves_traceback():
    """Ensure expected exceptions are re-raised and original traceback preserved."""
    try:
        wrapper_raise_expected()
    except ValueError as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        assert any(f.name == "_raise_value" for f in frames), "original frame not in traceback"
    else:
        pytest.fail("ValueError was not re-raised")


def test_no_reraise_for_non_expected():
    """If exception type is not expected, helper should return silently."""

    def _raise_runtime():
        raise RuntimeError("oops")

    def wrapper():
        try:
            _raise_runtime()
        except Exception as e:
            reraise_if_expected(e, (ValueError,))
            return "continued"

    assert wrapper() == "continued"
