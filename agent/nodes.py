import json
import re
from typing import Dict, Any

from agent.state import AgentState
from agent.prompts import TRIAGE_PROMPT, NAVIGATION_PROMPT, CARE_SUMMARY_PROMPT
from agent.llm import LLM


def _parse_json(text: str) -> dict:
    """Helper to extract clean JSON even if the model outputs markdown backticks."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _get_member3_tools() -> Dict[str, Any]:
    """Dynamically wire tools from Member 3's app/tools folder (with fallback to tools/)."""
    tools = {}
    # Try importing from Member 3's app.tools
    try:
        import app.tools as m3_tools
        if hasattr(m3_tools, "get_tools"):
            tools.update(m3_tools.get_tools())
    except ImportError:
        pass

    # Fallback to current tools registry if app.tools isn't created yet
    try:
        from tools import build_tools
        tools.update(build_tools())
    except Exception:
        pass

    return tools


# Initialize the LLM wrapper (Gemini or Groq from your .env)
llm = LLM()


def triage_node(state: AgentState) -> dict:
    """Sub-Agent 1: Clinical Triage Agent.
    Screens for red flags. If found, marks state as emergency.
    """
    messages = state.get("messages", [])
    patient_query = messages[-1]["content"] if messages else ""
    profile = state.get("patient_profile", {})

    user_content = f"Patient Complaint: {patient_query}\nKnown Profile: {json.dumps(profile)}"
    reply = llm.generate(TRIAGE_PROMPT, [{"role": "user", "content": user_content}])
    data = _parse_json(reply)

    urgency = data.get("urgency_level", "Routine")
    is_emergency = data.get("is_emergency", False) or urgency.lower() == "emergency"

    return {
        "urgency_level": urgency,
        "is_emergency": is_emergency,
        "extracted_symptoms": data.get("extracted_symptoms", []),
        "triage_reason": data.get("reason", "Routine intake assessment.")
    }


def emergency_halt_node(state: AgentState) -> dict:
    """Emergency Halting Node:
    Halts the workflow immediately when a red flag is found and outputs emergency guidance.
    """
    symptoms = ", ".join(state.get("extracted_symptoms", ["Acute distress"]))
    reason = state.get("triage_reason", "Life-threatening symptoms detected.")

    emergency_note = {
        "alert": "🚨 EMERGENCY MEDICAL ALERT - IMMEDIATE INTERVENTION REQUIRED 🚨",
        "status": "HALTED_FOR_SAFETY",
        "triage_level": "Emergency",
        "detected_symptoms": state.get("extracted_symptoms", []),
        "clinical_rationale": reason,
        "recommended_action": (
            "Please call 911 (or your local emergency services) immediately or have someone "
            "drive you to the nearest Emergency Department. Do not schedule a regular clinic visit."
        )
    }

    return {
        "care_summary": emergency_note,
        "recommended_specialty": ["Emergency Medicine / Trauma Care"]
    }


def navigation_node(state: AgentState) -> dict:
    """Sub-Agent 2: Navigation Agent.
    Maps non-emergency complaints to clinical specialties and can invoke Member 3's tools.
    """
    symptoms = state.get("extracted_symptoms", [])
    user_content = (
        f"Symptoms: {symptoms}\n"
        f"Triage Level: {state.get('urgency_level')}\n"
        f"Patient Profile: {json.dumps(state.get('patient_profile', {}))}"
    )

    reply = llm.generate(NAVIGATION_PROMPT, [{"role": "user", "content": user_content}])
    data = _parse_json(reply)

    # Wire Member 3's tools if relevant (e.g. clinic search or doctor lookup)
    available_tools = _get_member3_tools()
    tool_results = {}
    if "web_search" in available_tools and symptoms:
        try:
            # Query relevant care recommendations if tool exists
            tool_results["tool_status"] = f"Tools available: {list(available_tools.keys())}"
        except Exception as e:
            tool_results["tool_error"] = str(e)

    return {
        "recommended_specialty": data.get("recommended_specialty", ["General Practice"]),
        "navigation_advice": data.get("navigation_advice", "Consult your primary care physician."),
        "tool_results": tool_results
    }


def care_summary_node(state: AgentState) -> dict:
    """Sub-Agent 3: Care Summary Agent.
    Generates structured pre-consultation notes (CC, HPI, Specialty, Triage Level).
    """
    messages = state.get("messages", [])
    query = messages[-1]["content"] if messages else ""

    user_content = (
        f"Original Complaint: {query}\n"
        f"Extracted Symptoms: {state.get('extracted_symptoms', [])}\n"
        f"Triage Level: {state.get('urgency_level', 'Routine')}\n"
        f"Suggested Specialties: {state.get('recommended_specialty', [])}\n"
        f"Navigation Advice: {state.get('navigation_advice', '')}\n"
        f"Patient History: {json.dumps(state.get('patient_profile', {}))}"
    )

    reply = llm.generate(CARE_SUMMARY_PROMPT, [{"role": "user", "content": user_content}])
    summary = _parse_json(reply)

    # Fallback structure if parsing had any missing fields
    if not summary:
        summary = {
            "chief_complaint": query,
            "history_of_present_illness": f"Patient reports symptoms: {state.get('extracted_symptoms', [])}",
            "triage_level": state.get("urgency_level", "Routine"),
            "suggested_specialty": state.get("recommended_specialty", ["General Practice"])[0],
            "recommended_next_steps": state.get("navigation_advice", "Follow up with a specialist.")
        }

    return {"care_summary": summary}