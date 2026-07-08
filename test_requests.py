"""
Fires the two required test cases at a running instance of the agent API,
prints the plan/response, and downloads each generated .docx locally.

Usage:
    uvicorn main:app --reload --port 8000        # in one terminal
    python test_requests.py                        # in another
"""

import json
import requests

BASE_URL = "http://127.0.0.1:8000"

TEST_CASES = {
    "standard_business_request": (
        "Create meeting minutes for our project kickoff meeting for the new CRM "
        "implementation project. Attendees are from Sales, IT, and Finance. "
        "We discussed scope, timeline, and next steps."
    ),
    "complex_ambiguous_request": (
        "We need some kind of proposal for improving our customer onboarding process. "
        "Budget is tight but leadership wants results fast. Not sure if this should be "
        "a full project plan or just a set of recommendations -- use your judgment on "
        "the best format and produce it."
    ),
}


def run_case(name: str, request_text: str):
    print(f"\n{'=' * 70}\nTEST CASE: {name}\nREQUEST: {request_text}\n{'=' * 70}")
    resp = requests.post(f"{BASE_URL}/agent", json={"request": request_text})
    if resp.status_code != 200:
        print(f"FAILED ({resp.status_code}): {resp.text}")
        return
    data = resp.json()
    print(f"\nDocument type: {data['document_type']}")
    print(f"Message: {data['message']}")
    print(f"\nAgent-generated plan:")
    for step in data["plan"]:
        tag = "[tool]" if step.get("needs_tool") else "[no tool]"
        print(f"  {step['step']}. {tag} {step['name']}: {step['description']}")
    print(f"\nAssumptions made:")
    for a in data["assumptions"]:
        print(f"  - {a}")
    print(f"\nTool calls made:")
    for entry in data["tool_log"]:
        print(f"  step {entry['step']}: {entry.get('tool_called')} -> {entry.get('result')}")
    print(f"\nSelf-check: {json.dumps(data['self_check'], indent=2)}")

    download_url = BASE_URL + data["download_url"]
    file_resp = requests.get(download_url)
    local_name = f"{name}.docx"
    with open(local_name, "wb") as f:
        f.write(file_resp.content)
    print(f"\nDownloaded -> {local_name}")


if __name__ == "__main__":
    for case_name, req_text in TEST_CASES.items():
        run_case(case_name, req_text)
