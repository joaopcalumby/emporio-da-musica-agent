import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def store_today(value: str | None) -> date:
    if not value or value == "today":
        return date.today()
    return date.fromisoformat(value)


@dataclass(frozen=True)
class Settings:
    model_id: str
    today: date
    data_dir: Path = DATA_DIR

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_id=os.getenv("GROQ_MODEL") or DEFAULT_MODEL,
            today=store_today(os.getenv("STORE_TODAY")),
        )
