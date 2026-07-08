"""
Tool registry for the agent.

This is the "Tool calling" engineering improvement: the agent does NOT have a
hardcoded pipeline that always calls the same functions in the same order.
Instead, at each plan step marked needs_tool=True, an LLM call (see
executor.select_tool) is shown this registry's schema and picks which tool
to invoke, with what arguments, based on the step description and the
original user request. New tools can be added below with zero changes to
the planning/execution logic -- the agent will pick them up automatically.

All tools here return mock/synthetic data (explicitly allowed by the
assignment) since no real external systems are wired up.
"""

from datetime import date
import random

random.seed(42)  # deterministic mock data for reproducible demos


def get_current_date(**kwargs) -> dict:
    return {"today": date.today().isoformat()}


def fetch_mock_market_data(industry: str = "general", **kwargs) -> dict:
    return {
        "industry": industry,
        "market_growth_yoy": f"{random.randint(4, 18)}%",
        "top_competitors": ["Acme Corp", "Northwind Traders", "Globex Inc"],
        "customer_satisfaction_index": round(random.uniform(3.2, 4.6), 1),
    }


def fetch_mock_team_directory(department: str = "Cross-functional", **kwargs) -> dict:
    sample_people = [
        {"name": "Priya Nair", "role": "Project Lead", "dept": "IT"},
        {"name": "Daniel Osei", "role": "Sales Director", "dept": "Sales"},
        {"name": "Wei Chen", "role": "Finance Analyst", "dept": "Finance"},
        {"name": "Sara Malik", "role": "Product Manager", "dept": "Product"},
    ]
    return {"department_requested": department, "attendees": sample_people}


def estimate_project_effort(scope: str = "medium", complexity: str = "medium", **kwargs) -> dict:
    base_weeks = {"small": 2, "medium": 6, "large": 14}
    complexity_multiplier = {"low": 0.8, "medium": 1.0, "high": 1.4}
    weeks = round(
        base_weeks.get(scope, 6) * complexity_multiplier.get(complexity, 1.0)
    )
    budget = weeks * 8000  # a made-up $/week blended rate
    return {
        "scope": scope,
        "complexity": complexity,
        "estimated_weeks": weeks,
        "estimated_budget_usd": budget,
    }


# Registry: name -> (callable, description, arg schema) — this schema is what
# gets shown to the LLM so it can decide which tool fits a given plan step.
TOOL_REGISTRY = {
    "get_current_date": {
        "fn": get_current_date,
        "description": "Get today's date. Use for dating documents/timelines.",
        "args": {},
    },
    "fetch_mock_market_data": {
        "fn": fetch_mock_market_data,
        "description": "Get mock market/industry context data (growth, competitors, CSAT).",
        "args": {"industry": "string, e.g. 'retail', 'general'"},
    },
    "fetch_mock_team_directory": {
        "fn": fetch_mock_team_directory,
        "description": "Get a mock list of stakeholders/attendees for a department or project.",
        "args": {"department": "string, e.g. 'Sales', 'Cross-functional'"},
    },
    "estimate_project_effort": {
        "fn": estimate_project_effort,
        "description": "Get a mock timeline (weeks) and budget (USD) estimate for a project.",
        "args": {"scope": "'small'|'medium'|'large'", "complexity": "'low'|'medium'|'high'"},
    },
}


def registry_schema_text() -> str:
    """Human/LLM-readable description of available tools, used in prompts."""
    lines = []
    for name, spec in TOOL_REGISTRY.items():
        lines.append(f"- {name}({spec['args']}): {spec['description']}")
    return "\n".join(lines)


def call_tool(name: str, args: dict) -> dict:
    if name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return TOOL_REGISTRY[name]["fn"](**(args or {}))
    except TypeError as e:
        return {"error": f"Bad arguments for tool '{name}': {e}"}
