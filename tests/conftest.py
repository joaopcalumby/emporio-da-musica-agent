from datetime import date
from pathlib import Path

import pytest

from emporio.store import Store

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_TODAY = date(2026, 3, 25)


@pytest.fixture(scope="session")
def store() -> Store:
    return Store.from_dir(DATA_DIR, today=STORE_TODAY)
