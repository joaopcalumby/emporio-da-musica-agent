FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY data ./data
COPY tests ./tests
RUN uv sync --frozen

RUN uv run python -c "from emporio.config import DATA_DIR; from emporio.policies import PolicyIndex, load_sections; PolicyIndex.build(load_sections(DATA_DIR / 'store_policies.pdf'))"

CMD ["uv", "run", "--no-sync", "emporio"]
