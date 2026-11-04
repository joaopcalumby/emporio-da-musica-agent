from datetime import datetime, timedelta

import pytest

from emporio.config import store_now


def test_fixed_store_clock():
    assert store_now("2026-03-25T19:30") == datetime(2026, 3, 25, 19, 30)


@pytest.mark.parametrize("value", ["now", "", None])
def test_current_clock(value):
    assert abs(store_now(value) - datetime.now()) < timedelta(seconds=5)


def test_invalid_store_clock():
    with pytest.raises(ValueError):
        store_now("25/03/2026 19:30")
