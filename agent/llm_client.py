"""
LLM client abstraction.

Supports three providers, switchable via the LLM_PROVIDER env var:
  - "groq"   : free-tier Groq API (OpenAI-compatible /chat/completions)
  - "ollama" : local Ollama server (no API key, no internet needed)
  - "mock"   : deterministic canned responses, so the whole agent pipeline
               can be demoed/tested with zero network access and zero API key.

All providers expose the same method: chat(system, user) -> str (raw text reply).
Includes basic retry/backoff around the HTTP call since network calls to free-tier
LLM APIs are the most failure-prone part of this system.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

MAX_RETRIES = 3
BACKOFF_SECONDS = 1.5


class LLMError(Exception):
    pass


def _post_with_retry(url, headers, payload, timeout=30):
    """Small retry/backoff wrapper -> basic resilience against transient
    free-tier API flakiness (rate limits, cold starts, timeouts)."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 429:
                # Rate limited: back off and retry
                time.sleep(BACKOFF_SECONDS * attempt)
                last_err = f"429 rate limited (attempt {attempt})"
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(BACKOFF_SECONDS * attempt)
    raise LLMError(f"LLM request failed after {MAX_RETRIES} attempts: {last_err}")


def _chat_groq(system: str, user: str) -> str:
    if not GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    data = _post_with_retry(url, headers, payload)
    return data["choices"][0]["message"]["content"]


def _chat_ollama(system: str, user: str) -> str:
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }
    data = _post_with_retry(url, headers={}, payload=payload, timeout=120)
    return data["message"]["content"]


# ---------------------------------------------------------------------------
# Mock provider: lets the whole agent run end-to-end with no network/API key.
# It pattern-matches on markers we embed in our own prompts (see planner.py,
# executor.py) so the mock stays deterministic and useful for demoing the
# *pipeline* (planning -> tool selection -> content generation -> docx)
# even when a real LLM isn't reachable.
# ---------------------------------------------------------------------------
def _chat_mock(system: str, user: str) -> str:
    if "Respond ONLY with a JSON plan" in system:
        return _mock_plan(user)
    if "Respond ONLY with a JSON object choosing a tool" in system:
        return _mock_tool_choice(user)
    if "Write the content for the document section" in system:
        return _mock_section_content(user)
    if "self-check" in system.lower():
        return _mock_selfcheck(user)
    return "Mock response: no matching handler for this prompt."


def _mock_plan(user: str) -> str:
    is_complex = any(
        kw in user.lower()
        for kw in ["not sure", "tight", "decide what", "ambiguous", "fast", "unclear"]
    )
    doc_type = "Business Proposal" if is_complex else "Meeting Minutes"
    sections = (
        ["Executive Summary", "Problem Statement", "Recommended Approach",
         "Timeline & Budget", "Risks & Assumptions", "Next Steps"]
        if is_complex
        else ["Meeting Overview", "Attendees", "Discussion Summary",
              "Decisions Made", "Action Items"]
    )
    plan = {
        "document_type": doc_type,
        "assumptions": (
            ["No fixed budget was given, so a lean/phased option is assumed.",
             "Timeline compressed to 4-6 weeks given stated urgency."]
            if is_complex else
            ["Meeting assumed to be 45 minutes based on typical kickoff length."]
        ),
        "plan": [
            {"step": 1, "name": "gather_context", "description": "Collect supporting data needed for the document.", "needs_tool": True},
            {"step": 2, "name": "estimate_effort", "description": "Estimate timeline/budget if relevant.", "needs_tool": True},
            {"step": 3, "name": "draft_sections", "description": "Draft each document section.", "needs_tool": False},
            {"step": 4, "name": "self_check", "description": "Review draft against the original request for gaps.", "needs_tool": False},
            {"step": 5, "name": "assemble_document", "description": "Compile sections into a formatted Word document.", "needs_tool": False},
        ],
        "sections": sections,
    }
    return json.dumps(plan)


def _mock_tool_choice(user: str) -> str:
    if "budget" in user.lower() or "timeline" in user.lower() or "estimate" in user.lower():
        return json.dumps({"tool": "estimate_project_effort", "args": {"scope": "medium", "complexity": "medium"}})
    if "stakeholder" in user.lower() or "team" in user.lower() or "attendee" in user.lower():
        return json.dumps({"tool": "fetch_mock_team_directory", "args": {"department": "Cross-functional"}})
    if "market" in user.lower() or "industry" in user.lower() or "context" in user.lower():
        return json.dumps({"tool": "fetch_mock_market_data", "args": {"industry": "general"}})
    return json.dumps({"tool": "get_current_date", "args": {}})


def _mock_section_content(user: str) -> str:
    return json.dumps({
        "paragraphs": [
            "This section was generated by the mock LLM provider for offline testing. "
            "Swap LLM_PROVIDER to 'groq' or 'ollama' for real generated content."
        ],
        "bullets": ["Sample point one", "Sample point two"],
        "table": None,
    })


def _mock_selfcheck(user: str) -> str:
    return json.dumps({"complete": True, "missing": [], "notes": "Mock self-check: draft covers requested sections."})


def chat(system: str, user: str) -> str:
    """Unified entry point used by the rest of the agent."""
    if LLM_PROVIDER == "groq":
        return _chat_groq(system, user)
    if LLM_PROVIDER == "ollama":
        return _chat_ollama(system, user)
    return _chat_mock(system, user)


def chat_json(system: str, user: str) -> dict:
    """Call chat() and parse the reply as JSON, with one repair retry if the
    model wraps its JSON in markdown fences or adds stray text."""
    raw = chat(system, user)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: try to find the first {...} block in the text.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError as e:
                raise LLMError(f"Could not parse LLM JSON response: {e}\nRaw: {raw[:500]}")
        raise LLMError(f"Could not parse LLM JSON response.\nRaw: {raw[:500]}")