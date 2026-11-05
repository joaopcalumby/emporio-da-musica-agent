from uuid import uuid4

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from emporio.agent import build_agent
from emporio.config import Settings
from emporio.policies import PolicyIndex, load_sections
from emporio.store import Store

EXIT_WORDS = {"sair", "exit", "quit"}
TITLE = "Empório da Música · Atendimento"


def header(settings: Settings) -> str:
    return f"{TITLE}\nData da loja: {settings.now:%d/%m/%Y %H:%M}. Digite 'sair' para encerrar."


def reply(content: str) -> Panel:
    return Panel(Markdown(content), title="Empório", title_align="left", border_style="red")


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    store = Store.from_dir(settings.data_dir, today=settings.now.date())
    policies = PolicyIndex.build(load_sections(settings.data_dir / "store_policies.pdf"))
    agent = build_agent(store, policies, model_id=settings.model_id, now=settings.now)
    session_id = str(uuid4())
    console = Console()
    console.print(Text(header(settings)), end="\n\n")
    while True:
        try:
            message = console.input("[bold]Você:[/bold] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in EXIT_WORDS:
            break
        if message:
            console.print(reply(agent.run(message, session_id=session_id).content), end="\n\n")


if __name__ == "__main__":
    main()
