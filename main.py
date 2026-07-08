"""
Autonomous document-writing agent - FastAPI entrypoint.

POST /agent  {"request": "..."}  ->
  runs: plan -> tool selection & execution -> section drafting -> self-check -> docx build
  returns: JSON with the agent's plan, assumptions, tool log, self-check result,
           and a download link for the generated .docx.

Run:
  uvicorn main:app --reload --port 8000

Environment (see .env.example):
  LLM_PROVIDER = mock | groq | ollama
"""

import os
import re
import uuid
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from agent.planner import create_plan
from agent.executor import run_agent
from agent.docx_builder import build_docx
from agent.llm_client import LLMError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(
    title="Autonomous Document Agent",
    description="Accepts a natural-language request, plans its own steps, "
                "executes them (with tool calling), and returns a generated Word document.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request validation & guardrails (kept lightweight and separate from the
# headline "Tool calling" improvement, but necessary basic robustness):
# ---------------------------------------------------------------------------
class AgentRequest(BaseModel):
    request: str = Field(..., min_length=8, max_length=4000)

    @field_validator("request")
    @classmethod
    def not_blank_or_junk(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("request must not be blank")
        if not re.search(r"[A-Za-z]", cleaned):
            raise ValueError("request must contain readable text")
        return cleaned


class AgentResponse(BaseModel):
    message: str
    document_type: str
    assumptions: list
    plan: list
    tool_log: list
    self_check: dict
    download_url: str


@app.get("/")
def root():
    return {"status": "ok", "service": "autonomous-document-agent"}


@app.post("/agent", response_model=AgentResponse)
def agent_endpoint(payload: AgentRequest):
    user_request = payload.request

    # --- Step 1: autonomous planning ---
    try:
        plan = create_plan(user_request)
    except (LLMError, ValueError) as e:
        logger.error(f"Planning failed: {e}")
        raise HTTPException(status_code=502, detail=f"Planning step failed: {e}")

    # --- Step 2: execute plan (tool calling + drafting + self-check) ---
    try:
        result = run_agent(user_request, plan)
    except LLMError as e:
        logger.error(f"Execution failed: {e}")
        raise HTTPException(status_code=502, detail=f"Execution step failed: {e}")

    # --- Step 3: assemble the Word document ---
    file_id = uuid.uuid4().hex[:10]
    filename = f"{plan['document_type'].replace(' ', '_')}_{file_id}.docx"
    output_path = os.path.join(OUTPUT_DIR, filename)

    try:
        build_docx(
            document_type=plan["document_type"],
            user_request=user_request,
            assumptions=plan["assumptions"],
            sections=result["sections"],
            output_path=output_path,
        )
    except Exception as e:
        logger.error(f"Document assembly failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document assembly failed: {e}")

    return AgentResponse(
        message=(
            f"Generated a {plan['document_type']} with {len(plan['sections'])} sections. "
            f"Self-check: {'complete' if result['self_check'].get('complete') else 'gaps found'}."
        ),
        document_type=plan["document_type"],
        assumptions=plan["assumptions"],
        plan=plan["plan"],
        tool_log=result["tool_log"],
        self_check=result["self_check"],
        download_url=f"/download/{filename}",
    )


@app.get("/download/{filename}")
def download(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
