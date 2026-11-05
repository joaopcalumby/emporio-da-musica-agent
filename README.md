# Empório da Música - customer service agent

![ci](https://github.com/joaopcalumby/emporio-da-musica-agent/actions/workflows/ci.yml/badge.svg)

A text customer service agent for Empório da Música, a fictional musical instrument store in Campo
Grande/MS. It answers in Portuguese, the store's language, as the store's virtual assistant. Prices,
stock, promotions, shipping, installments and orders come from the store data through typed, read-only
tools. Opening hours, payment, returns, warranty and other rules come from the policy manual through
hybrid retrieval.

Example conversations, recorded from the running agent, are in
[docs/conversations.md](docs/conversations.md).

## Running it

You need a free [Groq](https://console.groq.com) API key.

```bash
cp .env.example .env    # then paste your key into GROQ_API_KEY
```

| Variable         | In `.env.example`     | Meaning                                                                |
| ---------------- | ----------------------- | ---------------------------------------------------------------------- |
| `GROQ_API_KEY` |                         | Groq key                                                               |
| `GROQ_MODEL`   | `openai/gpt-oss-120b` | Any Groq chat model with tool calling                                  |
| `STORE_NOW`    | `2026-03-25T14:30`    | Store clock, ISO date and time. `now` (or unset) uses the real clock |

The orders in the data go up to 22/03/2026, so with today's date every return window would already be
closed. `STORE_NOW` pins the store clock to a date that makes the data meaningful; change it, or set it
to `now`, to try other cases. The time matters too: the agent knows whether the store is open.

**With Docker** (one command, nothing else to install):

```bash
docker compose run --rm agent
```

**With [uv](https://docs.astral.sh/uv/)** (Python 3.13):

```bash
uv sync
uv run emporio
```

The first run downloads a small multilingual embedding model into `.cache/`; the Docker image already
has it. Type `sair` to leave.

**Tests:**

```bash
uv run pytest                 # 85 offline tests: store tools, retrieval, CLI, config
uv run pytest -m integration  # 13 behavior tests against the real model, needs GROQ_API_KEY
```

The CI builds the Docker image and runs the offline suite inside it on every push.

## How it works

```
customer -> CLI -> Agno agent (Groq LLM) -+-> store tools -> data/*.csv
                                          +-> search_policies -> hybrid index over store_policies.pdf
```

| Piece      | Choice                                                                                                                | Why                                                                                                                                                                                |
| ---------- | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework  | [Agno](https://github.com/agno-agi/agno) (`Agent`, `Groq` model, `InMemoryDb`)                                        | Runs the agent loop: sends the tool schemas to the model, executes the calls and keeps the session history. Small API, native Groq model, and I had used it before                 |
| LLM        | Groq, `openai/gpt-oss-120b` by default                                                                              | Free key for the evaluator, fast, reliable tool calling in the integration suite. The model is one variable                                                                        |
| Store data | Function calling over the CSVs                                                                                        | The model never computes or invents a price, a stock level or an order status. Tools are read-only and typed; there is no free SQL, so the model cannot read a table it should not |
| Policies   | RAG, one chunk per numbered section of the manual                                                                     | A section holds one complete rule, so a chunk never cuts a rule in half, and only three sections go into the context per question                                                  |
| Retrieval  | Hybrid: local embeddings (fastembed, `paraphrase-multilingual-MiniLM-L12-v2`) plus BM25, min-max scores fused 50/50 | Groq has no embedding endpoint. Dense search handles paraphrase ("me arrependi" finds "direito de arrependimento"); BM25 handles exact terms ("PIX", "SEDEX", "boquilha")          |
| Interface  | Terminal chat with rich panels                                                                                        | Runs anywhere with one command, no front end to install                                                                                                                            |
| History    | Last 4 turns of the session, in memory                                                                                | Enough for follow-ups like "e o frete pra Dourados?"                                                                                                                               |

**Tools exposed to the model** (`src/emporio/agent.py`): `list_categories`, `search_products`
(category, price ceiling, text, on sale), `get_product`, `simulate_installments`, `shipping_quote`,
`order_status` and `search_policies`. Business rules live in code (`src/emporio/store.py`), not in the
prompt: the PIX discount, the installment minimums, free shipping, the return window and identity checks
are computed and tested, so the model only reports them.

**Prompt strategy.** One system prompt in Portuguese with the persona from the manual (informal but
professional), the store clock, and short rules grouped by store data, policies, orders and scope. The
core rule is that no price, stock, promotion, freight, installment or order is stated without a tool
call, and policy answers use only the retrieved sections. Customer messages and tool results are
declared as data.

**Repository layout.**

```
src/emporio/agent.py     system prompt, tools exposed to the model, Agno agent
src/emporio/store.py     catalog, prices, PIX, installments, shipping, orders and identity checks
src/emporio/policies.py  PDF sectioning and the hybrid policy index
src/emporio/cli.py       terminal chat
src/emporio/config.py    environment settings and store clock
data/                    the case's CSVs and policy manual
tests/                   offline suite and the integration suite (-m integration)
scripts/                 record_conversations.py, which generates docs/conversations.*
```

## Data and policy assumptions

The case asks to document reasonable interpretations. These are the ones I made.

- **Catalog.** Only what is in the CSVs counts; the manual's "more than 300 instruments" does not.
  Categories without products (wind, orchestral strings) are answered with "we don't have this type of
  instrument". Accessories are not sold, and the agent does not invent partner stores.
- **Product status.** `active` with stock is offered; `active` with no stock is "unavailable", with
  alternatives. `coming_soon` is never offered, even with stock recorded (Kala KA-ABP-CTG).
  `discontinued` with stock is sold as "last units" (Ibanez Bass 2X); without stock it is "out of the
  catalog".
- **Price.** A promotion counts only when `is_active=1` and is always shown with the original price and
  the percentage (manual 6.2). PIX gives 5% only on products with no promotion; discounts do not stack.
- **Installments** (manual 3.1): up to 3x with a R$ 50 minimum installment, 4x to 6x with R$ 80, 7x to
  12x with R$ 100. Old orders are not audited against this rule (orders 9 and 16 break it).
- **Orders.** An order is shown only with its number plus the customer's email or phone (LGPD). One email
  belongs to two customers, so for it the phone is required. The agent reports the recorded total and
  never recalculates it with today's prices.
- **Returns.** Every order is treated as an online purchase (there is no channel field). There is no
  receipt date, so the 7-day withdrawal window counts from `estimated_delivery`, and the agent says it is
  an estimate.
- **Returns vs warranty.** They are separate sections of the manual and the agent keeps their deadlines
  apart. Section 4.2 sends the customer to the manufacturer after 30 days, which sits uneasily with the
  90-day legal warranty in 8.1; the agent presents both and gives no legal opinion.
- **Contact.** The manual writes the email as `contato@empóriodamusica.com.br`; I took the accent as a
  typo and use `contato@emporiodamusica.com.br`.
- **Shipping.** Campo Grande: free from R$ 500, R$ 35 below, own courier in 1 to 3 business days. Other
  cities: priced by destination CEP at checkout, so the agent lists carriers and delivery times and never
  quotes a value.

## Known limitations

- **LLM variance.** The integration suite checks behavior with the real model and is not deterministic;
  on a bad run one or two of the 13 tests can fail, while the deterministic logic is covered offline.
- **Groq free tier.** 8k tokens per minute and 200k tokens per day per model. A long session can hit the
  limit; `GROQ_MODEL=openai/gpt-oss-20b` has its own quota and works as a fallback, with somewhat weaker
  answers.
- **Retrieval tuning.** The 50/50 fusion weight was chosen on the same 16 questions the retrieval test
  uses (all 16 hit the right section in the top 3). A held-out set would give a fairer number.
- **History** lives in memory and is lost when the chat ends.
- **No injection classifier.** The defense is structural: read-only tools, identity checks in code and
  data declared as data. A dedicated guard model would add a layer.
- **Formatting.** The model sometimes writes thousands with a thin space ("R$ 1 000,00") instead of a dot.

## Future work

- **Persistent sessions and a web UI:** Agno's `SqliteDb` for history across sessions and AgentOS for a
  chat UI, in the same container, with a flag to run only the CLI. It was planned with a time cap and did
  not fit.
- **Generation evaluation** with RAGAS (faithfulness, context recall), on top of today's retrieval test
  and behavior suite.
- **WhatsApp** through the Evolution API. The verified sender phone would allow a safe "my orders"
  without asking for the email.
- **Store admin panel** to edit products, categories, promotions and payment rules, kept outside the
  agent: a write tool in the model's hands would let a customer change data through injection.

## How I used a coding assistant

I built this with **Claude Code** as a pair. The workflow:

1. **Scope before code.** We read the case and both data sources together, wrote down the business rules
   above and the open questions, and I decided each one before any code.
2. **Tests before implementation.** For every feature we agreed on the test list with expected values
   (for example "Takamine GD20: R$ 2.199,00, R$ 2.089,05 on PIX, no promotion"). I approved it, then each
   branch got a `test:` commit first and the implementation after. Expected values were never changed to
   make a test pass.
3. **Branches and review.** `main` and `dev`, one branch per feature merged into `dev` through a pull
   request. Claude wrote the code; I reviewed, committed, pushed and merged.
   [AGENTS.md](AGENTS.md) holds the rules the assistant follows in this repository.
4. **Testing by hand.** I chatted with the agent and reported what felt wrong (an internal rule leaking
   into an answer, the model name in the header, hard-to-follow long chats). Each report became a test
   and then a fix.
5. **Recording the examples.** `scripts/record_conversations.py` drives the same agent the CLI uses with
   scripted customer messages and writes the agent's real replies, plus every tool call and result in
   `docs/conversations.json`, so the examples are reproducible rather than typed.

**Repository history.** On the delivery day GitHub stopped accepting any ref update on the original
repository (`fatal error in commit_refs`, also through the REST API), so I moved everything to this new
repository with the same name. All commits and branches came along. The pull requests #1 to #8 stayed in
the original, now
[joaopcalumby/emporio-da-musica-agent-old](https://github.com/joaopcalumby/emporio-da-musica-agent-old/pulls?q=is%3Apr).
