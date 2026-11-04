# AGENTS.md

Instructions for coding agents working in this repository.

## Commands

```bash
uv sync                      # install
uv run pytest                # offline tests (store tools, policy retrieval)
uv run pytest -m integration # needs GROQ_API_KEY
uv run emporio               # chat in the terminal
```

## Rules

- Tests come first. Every feature branch opens with a commit containing its tests, written from the
  agreed specification, and only then the implementation. Never change an expected value to make a
  test pass; change the code or reopen the specification.
- Prices, stock, promotions and orders come only from `data/*.csv` through the tools in
  `src/emporio/store.py`. Store policies come only from `data/store_policies.pdf` through retrieval.
- Tools exposed to the model are read-only.
- No comments explaining what the code does, no redundant code. Names carry the meaning.
- Branches: `main` (release) and `dev` (integration). One branch per feature from `dev`, merged
  back into `dev`; `dev` goes into `main` when everything is green.
