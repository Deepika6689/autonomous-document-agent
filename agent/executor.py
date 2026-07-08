"""
Executor: carries out the plan produced by planner.py.

For each plan step:
  - if needs_tool: True -> ask the LLM to CHOOSE which registered tool fits this
    step (tool calling), run it, and fold the result into shared context.
  - content-drafting steps use accumulated tool context + assumptions to write
    each document section.

After drafting, a lightweight self-check pass asks the LLM to compare the
draft against the original request and flag any missing requirements, which
are logged in the response (kept simple: logged/reported, not an infinite
re-drafting loop, to keep behavior predictable and fast).
"""

from agent.llm_client import chat, chat_json
from agent.tools import call_tool, registry_schema_text

TOOL_CHOICE_SYSTEM_PROMPT = f"""You are the tool-selection module of an autonomous agent.
Given a plan step description and the original user request, choose the single best-fitting
tool from this registry (or "none" if no tool is needed):

{registry_schema_text()}

Respond ONLY with a JSON object choosing a tool, matching exactly this shape:
{{"tool": "tool_name_or_none", "args": {{...}}}}
"""

SECTION_SYSTEM_PROMPT = """You are the content-drafting module of an autonomous document agent.
Write the content for the document section named in the user message. Use the supplied
context (original request, assumptions, and any gathered data) to write realistic, specific,
professional business content -- do not use generic filler.

Respond ONLY with a JSON object matching exactly this shape (omit table if not relevant):
{"paragraphs": ["string", ...], "bullets": ["string", ...], "table": {"headers": ["..."], "rows": [["..."]]}}
"""

SELF_CHECK_SYSTEM_PROMPT = """You are the self-check (reflection) module of an autonomous agent.
Compare the drafted document sections against the ORIGINAL user request. Identify anything
explicitly requested that appears to be missing or under-addressed.

Respond ONLY with a JSON object matching exactly this shape:
{"complete": true|false, "missing": ["string", ...], "notes": "string"}
"""


def select_tool(step_description: str, user_request: str) -> dict:
    prompt = f"Original user request: {user_request}\nPlan step: {step_description}"
    choice = chat_json(TOOL_CHOICE_SYSTEM_PROMPT, prompt)
    return choice


def run_tool_steps(plan: dict, user_request: str) -> tuple[dict, list]:
    """Executes every needs_tool step, returns (context_dict, log_of_calls)."""
    context = {}
    log = []
    for step in plan["plan"]:
        if not step.get("needs_tool"):
            continue
        choice = select_tool(step["description"], user_request)
        tool_name = choice.get("tool", "none")
        if tool_name and tool_name != "none":
            result = call_tool(tool_name, choice.get("args", {}))
            context[tool_name] = result
            log.append({"step": step["step"], "tool_called": tool_name,
                        "args": choice.get("args", {}), "result": result})
        else:
            log.append({"step": step["step"], "tool_called": None, "result": None})
    return context, log


def draft_section(section_name: str, user_request: str, assumptions: list, context: dict) -> dict:
    prompt = (
        f"Original user request: {user_request}\n"
        f"Assumptions made: {assumptions}\n"
        f"Gathered supporting data: {context}\n"
        f"Section to write: {section_name}"
    )
    return chat_json(SECTION_SYSTEM_PROMPT, prompt)


def self_check(user_request: str, sections: dict) -> dict:
    prompt = f"Original user request: {user_request}\nDrafted sections: {list(sections.keys())}"
    return chat_json(SELF_CHECK_SYSTEM_PROMPT, prompt)


def run_agent(user_request: str, plan: dict) -> dict:
    context, tool_log = run_tool_steps(plan, user_request)

    sections = {}
    for section_name in plan["sections"]:
        sections[section_name] = draft_section(
            section_name, user_request, plan["assumptions"], context
        )

    check = self_check(user_request, sections)

    return {
        "tool_log": tool_log,
        "sections": sections,
        "self_check": check,
    }
