from datetime import date

import pytest

from emporio.config import store_today


def test_fixed_store_date():
    assert store_today("2026-03-25") == date(2026, 3, 25)


@pytest.mark.parametrize("value", ["today", "", None])
def test_current_date(value):
    assert store_today(value) == date.today()


def test_invalid_store_date():
    with pytest.raises(ValueError):
        store_today("25/03/2026")
