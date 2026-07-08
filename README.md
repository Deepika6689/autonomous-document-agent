# Autonomous Document Agent

A FastAPI-based autonomous AI agent that accepts a natural-language request, creates its own execution plan, selects tools dynamically, generates content, performs a self-check, and produces a polished Microsoft Word (.docx) document.

Built as a demonstration of autonomous planning, decision-making, tool orchestration, and end-to-end document generation.

---

# Features

- FastAPI-based autonomous AI agent
- Dynamic task planning and execution
- LLM-driven tool selection
- Automated DOCX document generation
- Reflection / self-check validation
- Request validation and guardrails
- Retry and recovery logic for LLM calls
- Multiple LLM providers (Groq, Ollama, Mock)
- Extensible tool registry architecture

---

# Tech Stack

- Python 3.12
- FastAPI
- Pydantic
- python-docx
- Requests
- Groq API (Free Tier)
- Ollama (Local Models)
- Mock LLM Mode

---

# Quickstart

Install dependencies:

```bash
pip install -r requirements.txt
```

Create environment file:

```bash
cp .env.example .env
```

Edit `.env` as needed.

Start the API:

```bash
uvicorn main:app --reload --port 8000
```

Run test cases:

```bash
python test_requests.py
```

---

# API Usage

### Endpoint

```http
POST /agent
```

### Request

```json
{
  "request": "Create meeting minutes for our CRM kickoff meeting"
}
```

### Example cURL

```bash
curl -X POST http://127.0.0.1:8000/agent \
-H "Content-Type: application/json" \
-d '{"request":"Create meeting minutes for our CRM kickoff meeting"}'
```

### Example Response

```json
{
  "plan": [
    "Gather context",
    "Create document structure",
    "Generate content",
    "Perform self-check"
  ],
  "assumptions": [
    "Meeting duration assumed to be 60 minutes"
  ],
  "tool_calls": [
    {
      "tool": "current_date",
      "result": "2026-07-08"
    }
  ],
  "self_check": {
    "missing_items": []
  },
  "download_url": "/download/Meeting_Minutes_xxx.docx"
}
```

---

# LLM Provider Options

Configure via `.env`.

| Provider | Requirements | Notes |
|----------|-------------|--------|
| mock | None | Deterministic responses for testing and demos |
| groq | GROQ_API_KEY | Free tier, fast, OpenAI-compatible |
| ollama | Local Ollama server | Fully offline execution |

Example:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```

Switching providers requires no code changes.

---

# Architecture

```text
POST /agent {"request":"..."}

        │
        ▼

① planner.py
   Generates:
   - Document type
   - Assumptions
   - Execution plan
   - Section structure

        │
        ▼

② executor.py
   Tool Selection

   For each step requiring external information,
   the LLM dynamically selects the most suitable tool.

        │
        ▼

③ executor.py
   Content Generation

   Generates document sections using:
   - User request
   - Assumptions
   - Tool outputs

        │
        ▼

④ executor.py
   Reflection / Self Check

   Reviews generated content
   against original requirements.

        │
        ▼

⑤ docx_builder.py

   Creates polished DOCX file:
   - Title page
   - Assumptions section
   - Structured content

        │
        ▼

Response:
- Plan
- Assumptions
- Tool usage log
- Self-check results
- Download URL
```

---

# Assignment Requirement Implemented

## Mandatory Engineering Improvement

✅ Tool Calling

The agent uses a dynamic tool registry defined in `tools.py`.

Instead of hardcoding tool usage for specific document types, the agent:

1. Reviews the current plan step.
2. Evaluates available tools.
3. Selects the most appropriate tool.
4. Generates arguments automatically.
5. Executes the selected tool.
6. Uses the result in later document generation.

### Why Tool Calling?

The assignment already requires planning and execution.

Tool calling makes the agent genuinely extensible.

Adding a new capability only requires:

```python
TOOL_REGISTRY["new_tool"] = ...
```

No planner changes.

No executor changes.

No prompt modifications.

The agent can automatically select newly added tools whenever their capabilities best match the current planning step.

### Benefits

- Extensible architecture
- Autonomous decision-making
- Reduced hardcoded logic
- Easier future expansion
- More realistic agent behavior

---

# Additional Robustness Features

### Retry & Recovery

Implemented in `llm_client.py`.

Handles:

- Temporary API failures
- Free-tier rate limits
- Network interruptions

Uses retry with backoff.

---

### JSON Repair Logic

LLMs sometimes return:

```json
{
  "example": true
}
```

wrapped in markdown fences or extra text.

The parser:

- Removes markdown fences
- Extracts valid JSON
- Attempts recovery before failing

---

### Request Validation

Implemented with Pydantic.

Rejects:

- Empty requests
- Invalid payloads
- Malformed input

before any LLM call is made.

---

### Reflection / Self-Check

Before generating the final document:

1. Draft is reviewed.
2. Requirements are compared.
3. Missing information is reported.

Results are returned transparently in the API response.

---

# Sample Outputs

The agent can generate:

- Meeting Minutes
- Business Proposals
- Project Plans
- Technical Design Documents
- Product Specifications
- SOP Documents
- Business Reports

Generated files are available through:

```http
GET /download/{filename}
```

---

# Required Test Cases

Implemented in:

```text
test_requests.py
```

### Test Case 1 — Standard Request

```text
Create meeting minutes for our CRM kickoff meeting.
```

Expected Outcome:

- Meeting Minutes document
- Structured agenda
- Action items
- Clear ownership

---

### Test Case 2 — Complex / Ambiguous Request

```text
We have a tight budget and are unsure whether we need
a full project plan or recommendations.
Use your judgment.
```

Expected Outcome:

- Agent determines document type
- Makes assumptions
- Explains decisions
- Produces final document

Assumptions are included in:

- API response
- DOCX output

---

# Debugging Insight

One issue encountered:

### Problem

Some LLM providers wrapped JSON responses inside:

```text
```json
{ ... }
```
```

which caused `json.loads()` failures.

### Root Cause

Prompt instructions alone cannot guarantee output formatting.

### Solution

Implemented JSON repair logic that:

- Removes markdown fences
- Extracts valid JSON blocks
- Falls back gracefully before failure

---

# Engineering Tradeoff

## Autonomous Planning vs Deterministic Workflows

### Autonomous Planning

Pros:

- Handles ambiguity
- Adapts to user requests
- More flexible

Cons:

- Less predictable
- Harder to test

### Deterministic Workflows

Pros:

- Easier testing
- Predictable outputs

Cons:

- Less adaptable
- More hardcoded logic

### Decision

This project uses:

- Autonomous planning and tool selection
- Deterministic DOCX generation

This balances flexibility with reliability.

---

# Project Structure

```text
main.py
│
├── FastAPI application
├── Request validation
└── API endpoints

agent/
│
├── planner.py
│   Autonomous planning
│
├── executor.py
│   Tool selection
│   Draft generation
│   Reflection
│
├── tools.py
│   Tool registry
│
├── docx_builder.py
│   DOCX generation
│
└── llm_client.py
    Provider abstraction
    Retry logic

test_requests.py
│
└── Executes both assignment test cases

outputs/
│
└── Generated DOCX files
```

---

# Future Improvements

- Multi-agent architecture
- Vector database + RAG
- Persistent conversation memory
- Human approval workflow
- Additional external tools
- Advanced document templates

---

# Author

Deepika

Python AI Engineer – Autonomous Agents Assignment
