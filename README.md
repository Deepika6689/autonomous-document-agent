# Autonomous Document Agent

A FastAPI service that takes a natural-language request, autonomously plans its own
steps, executes them (choosing tools as it goes), and returns a polished Word (.docx)
document.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit LLM_PROVIDER / keys as needed
uvicorn main:app --reload --port 8000
```

In another terminal:

```bash
python test_requests.py       # fires both required test cases, downloads the .docx files
```

Or manually:

```bash
curl -X POST http://127.0.0.1:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Create meeting minutes for our CRM kickoff meeting"}'
```

### LLM provider options (`.env`)

| `LLM_PROVIDER`   | What it needs                               | Notes                                                                                                                                                                 |
| ------------------ | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mock` (default) | nothing                                     | Deterministic canned responses so you can demo/test the whole pipeline (planning, tool selection, drafting, docx build) with**zero API key and zero internet**. |
| `groq`           | `GROQ_API_KEY` (free at console.groq.com) | Fast, free-tier, OpenAI-compatible. Recommended for the real demo/video.                                                                                              |
| `ollama`         | local`ollama serve` running               | Fully offline, no key needed, needs a pulled model (e.g.`ollama pull llama3.1`).                                                                                    |

Switch providers by editing `.env` — no code changes required.

## Architecture

```
POST /agent {"request": "..."}
        │
        ▼
 ① planner.py        LLM decides: document_type, assumptions (for
                      ambiguous asks), its OWN step-by-step plan, and
                      the document's section list. No hardcoded template
                      per document type.
        │
        ▼
 ② executor.py        For each plan step marked needs_tool=True, a
    (tool calling)     dedicated LLM call PICKS which tool to invoke from
                       the registry (tools.py) and with what arguments —
                       the agent decides this at runtime, it isn't
                       hardcoded per request type. Results are folded
                       into shared context.
        │
        ▼
 ③ executor.py        Each planned section is drafted by the LLM using
    (drafting)         the original request + assumptions + gathered
                       tool context.
        │
        ▼
 ④ executor.py        Self-check pass: LLM compares the draft against the
    (reflection)       original request and flags anything missing
                       (logged in the response for transparency).
        │
        ▼
 ⑤ docx_builder.py    python-docx assembles a title page, an "Assumptions
                       Made by the Agent" box, and each section (headings,
                       paragraphs, bullets, tables) into a polished .docx.
        │
        ▼
 Response: plan, assumptions, tool call log, self-check result,
           and a /download/{filename} link for the generated Word doc.
```

## The mandatory engineering improvement: **Tool calling**

`tools.py` holds a registry of callables (mock market data, mock stakeholder
directory, effort/budget estimation, current date) each with a name, description,
and argument schema. For every plan step the planner marks `needs_tool: true`,
`executor.select_tool()` shows the LLM that registry and asks it to pick the single
best-fitting tool + arguments for that step, given the step description and the
original request — a JSON decision, not a hardcoded `if document_type == X: call Y`.

**Why this one:** the assignment already forces multi-step planning and API/document
work as baseline requirements. Tool calling is the piece that makes the agent
genuinely extensible: adding a new capability (say, a "fetch competitor pricing" tool)
requires only adding one entry to `TOOL_REGISTRY` — no changes to the planner, executor,
or prompts. The agent will start using it automatically whenever a plan step's
description makes it the best fit. That's a real "autonomous decision-making" property,
not just parameterized templating.

**How it improves the agent:** without it, every document type would need its own
hand-written data-gathering code path. With it, the same execution loop handles meeting
minutes, proposals, technical designs, etc. — the LLM decides per-request which (if any)
supporting data to pull in.

## Other robustness included (secondary, not the headline feature)

- **Retry/backoff** around LLM HTTP calls (`llm_client.py`) for transient free-tier flakiness.
- **JSON-repair fallback** when a model wraps JSON in markdown fences or adds stray text.
- **Request validation** via Pydantic (`main.py`) rejecting blank/junk input before any LLM call.
- **Lightweight self-check/reflection** step (see above) surfaced in the response rather than
  silently trusted.

## Two required test cases (`test_requests.py`)

1. **Standard**: "Create meeting minutes for our CRM kickoff meeting..." → clean, well-specified → Meeting Minutes doc.
2. **Complex/ambiguous**: "...tight budget... not sure if this should be a full project plan or just recommendations... use your judgment" → the agent has to pick a document type itself and record explicit assumptions (visible in the "Assumptions Made by the Agent" section of the .docx and in the API response).

## Talking points for the video

**Debugging insight (pick one you actually hit while wiring this up):**

- LLMs occasionally wrap JSON replies in `` ```json `` fences or add a sentence before/after
  the JSON, breaking `json.loads`. Root cause: prompting alone doesn't guarantee format
  compliance across providers. Fix: `chat_json()` strips fences and falls back to extracting
  the first `{...}` block before giving up.
- Free-tier APIs occasionally 429 under load. Root cause: shared rate limits on free tiers.
  Fix: retry with linear backoff in `_post_with_retry`.

**Tradeoff discussion:**

- **Autonomous planning vs. deterministic workflows** — letting the LLM invent its own plan/
  section list per request (autonomy, better fit to ambiguous asks) vs. a fixed template per
  document type (more predictable output, easier to test, cheaper). This project leans
  autonomous for planning/tools but keeps document assembly deterministic (python-docx),
  which is a middle ground worth explaining on camera.
- Alternative tradeoffs you could also discuss: Simplicity vs Extensibility (the tool registry
  pattern trades a little extra indirection for zero-code-change extensibility), or Speed vs
  Functionality (mock mode trades real intelligence for a demoable, dependency-free pipeline).

## Project layout

```
main.py                 FastAPI app, POST /agent, request validation
agent/
  planner.py            Step ① — autonomous plan + section list generation
  executor.py            Steps ②③④ — tool selection, drafting, self-check
  tools.py                Tool registry (the mandatory improvement)
  docx_builder.py        Step ⑤ — python-docx assembly
  llm_client.py          Provider abstraction: mock / groq / ollama + retry logic
test_requests.py         Runs both required test cases end-to-end
outputs/                 Generated .docx files land here
```
