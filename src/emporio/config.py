import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def store_now(value: str | None) -> datetime:
    if not value or value == "now":
        return datetime.now()
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class Settings:
    model_id: str
    now: datetime
    data_dir: Path = DATA_DIR

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_id=os.getenv("GROQ_MODEL") or DEFAULT_MODEL,
            now=store_now(os.getenv("STORE_NOW")),
        )
