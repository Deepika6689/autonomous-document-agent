"""
Planner: turns a natural-language request into the agent's own execution plan.

This is the autonomy core -- there is no hardcoded "if proposal then do X"
branching. The LLM decides the document type, the section list, which
assumptions it needs to make (for ambiguous/incomplete requests), and which
plan steps require an external tool call.
"""

from agent.llm_client import chat_json
from agent.tools import registry_schema_text

PLANNER_SYSTEM_PROMPT = f"""You are the planning module of an autonomous document-writing agent.

Given a user's natural language request, you must:
1. Decide what type of business document best satisfies the request (e.g. Meeting Minutes,
   Project Plan, Business Proposal, Technical Design, SOP, Product Spec, Business Report).
2. If the request is ambiguous, incomplete, or has conflicting requirements, make and record
   REASONABLE ASSUMPTIONS rather than stalling -- state them explicitly.
3. Produce your own step-by-step execution plan (not a fixed template). Each step needs a
   short name, a description, and whether it requires calling an external tool.
4. Decide the list of section headings the final Word document should contain.

Tools available for steps that need external/supporting data:
{registry_schema_text()}

Respond ONLY with a JSON plan and nothing else (no markdown fences, no commentary), matching
exactly this shape:
{{
  "document_type": "string",
  "assumptions": ["string", ...],
  "plan": [
    {{"step": 1, "name": "string", "description": "string", "needs_tool": true|false}}
  ],
  "sections": ["string", ...]
}}
"""


def create_plan(user_request: str) -> dict:
    plan = chat_json(PLANNER_SYSTEM_PROMPT, user_request)
    # Minimal guardrail: make sure the shape is usable before execution proceeds.
    required_keys = {"document_type", "assumptions", "plan", "sections"}
    if not required_keys.issubset(plan.keys()):
        missing = required_keys - plan.keys()
        raise ValueError(f"Planner returned an incomplete plan, missing keys: {missing}")
    if not plan["sections"]:
        raise ValueError("Planner returned zero document sections.")
    return plan
