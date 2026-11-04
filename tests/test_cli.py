import io
from datetime import datetime

from rich.console import Console

from emporio.cli import TITLE, header, reply
from emporio.config import Settings

SETTINGS = Settings(model_id="openai/gpt-oss-120b", now=datetime(2026, 3, 25, 19, 30))


def rendered(renderable) -> str:
    console = Console(file=io.StringIO(), width=80, record=True)
    console.print(renderable)
    return console.export_text()


def test_header_hides_the_model():
    assert SETTINGS.model_id not in header(SETTINGS)


def test_header_shows_store_name_and_clock():
    text = header(SETTINGS)
    assert TITLE == "Empório da Música · Atendimento"
    assert TITLE in text
    assert "25/03/2026 19:30" in text


def test_reply_is_framed_in_a_panel():
    text = rendered(reply("O Takamine GD20 sai por R$ 2.199,00."))
    assert "╭" in text and "╰" in text
    assert "Empório" in text
    assert "O Takamine GD20 sai por R$ 2.199,00." in text


def test_reply_keeps_brackets_literal():
    assert "[pedido 8]" in rendered(reply("Seu [pedido 8] foi enviado."))


def test_reply_renders_markdown():
    text = rendered(reply("O **Taylor 110e** está em promoção."))
    assert "Taylor 110e" in text
    assert "**" not in text
