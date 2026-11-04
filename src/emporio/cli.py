from uuid import uuid4

from dotenv import load_dotenv

from emporio.agent import build_agent
from emporio.config import Settings
from emporio.policies import PolicyIndex, load_sections
from emporio.store import Store

EXIT_WORDS = {"sair", "exit", "quit"}


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    store = Store.from_dir(settings.data_dir, today=settings.today)
    policies = PolicyIndex.build(load_sections(settings.data_dir / "store_policies.pdf"))
    agent = build_agent(store, policies, model_id=settings.model_id)
    session_id = str(uuid4())
    print(f"Empório da Música ({settings.model_id}, data da loja {settings.today:%d/%m/%Y}). Digite 'sair' para encerrar.\n")
    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in EXIT_WORDS:
            break
        if message:
            print(f"\nEmpório: {agent.run(message, session_id=session_id).content}\n")


if __name__ == "__main__":
    main()
