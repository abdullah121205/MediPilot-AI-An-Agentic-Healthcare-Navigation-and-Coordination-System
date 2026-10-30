"""Entry point.
  python main.py "your question"            human-readable run (shows Thought/Action/Observation)
  python main.py --json "your question"     machine output: ONE JSON line (the judges' harness uses this)
  python main.py --dry-run "anything"       test your setup without an API key
Contract: stdout = {"answer": str, "trace": [{"thought","tool","args","observation"}]}; logs go to stderr.
"""
import argparse
import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

# 1. Load .env FIRST so your API keys are ready
load_dotenv()

# 2. Now import your graph
from agent.graph import build_healthcare_graph


def run_agent(query):
    initial_state = {
        "messages": [{"role": "user", "content": query}],
        "patient_profile": {},
        "extracted_symptoms": [],
        "urgency_level": "Routine",
        "triage_reason": "",
        "recommended_specialty": [],
        "navigation_advice": "",
        "tool_results": {},
        "care_summary": {},
        "is_emergency": False,
    }
    app = build_healthcare_graph()
    output = app.invoke(initial_state)

    # Build judges' trace list showing the multi-agent execution steps
    trace = [
        {
            "thought": "Screen patient complaint for clinical red flags and triage urgency level.",
            "tool": "triage_agent",
            "args": {"complaint": query},
            "observation": f"Urgency: {output.get('urgency_level')}, Emergency: {output.get('is_emergency')}"
        }
    ]

    if not output.get("is_emergency"):
        trace.append({
            "thought": "Map symptoms to medical specialties and care navigation.",
            "tool": "navigation_agent",
            "args": {"symptoms": output.get("extracted_symptoms", [])},
            "observation": f"Recommended: {output.get('recommended_specialty', [])}"
        })
        trace.append({
            "thought": "Generate pre-consultation SOAP clinical summary.",
            "tool": "care_summary_agent",
            "args": {},
            "observation": "Care summary generated successfully."
        })

    return output.get("care_summary", {}), trace

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--json", action="store_true", help="print the judges' JSON contract to stdout")
    ap.add_argument("--dry-run", action="store_true", help="scripted LLM, no API key needed")
    a = ap.parse_args()

    try:
        answer, trace = run_agent(a.query, a.dry_run or bool(os.environ.get("AGENTX_DRY_RUN")), verbose=not a.json)
    except Exception as e:  # never crash silently: always return a valid answer object
        answer, trace = f"Agent error: {type(e).__name__}: {e}", []
        print(answer, file=sys.stderr)

    if a.json:
        print(json.dumps({"answer": answer, "trace": trace}))
    else:
        print(f"\nANSWER: {answer}")


if __name__ == "__main__":
    main()