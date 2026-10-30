import json
import re
from typing import Dict, Any

from agent.state import AgentState
from agent.prompts import TRIAGE_PROMPT, NAVIGATION_PROMPT, CARE_SUMMARY_PROMPT
from agent.llm import LLM


def _parse_json(text: str) -> dict:
    """Helper to extract clean JSON even if the model outputs markdown backticks or extra text."""
    if not text:
        return {}
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


import importlib

def _get_member3_tools() -> Dict[str, Any]:
    """Dynamically load Member 3's tools without triggering VS Code import warnings."""
    tools = {}
    try:
        # Dynamic import so VS Code doesn't complain when the folder is missing
        m3_tools = importlib.import_module("app.tools")
        if hasattr(m3_tools, "get_tools"):
            tools.update(m3_tools.get_tools())
    except (ImportError, ModuleNotFoundError):
        pass

    # Fallback to local tools/ directory
    try:
        from tools import build_tools
        tools.update(build_tools())
    except Exception:
        pass

    return tools


llm = LLM()


def triage_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    patient_query = messages[-1]["content"] if messages else ""
    profile = state.get("patient_profile", {})

    user_content = f"Patient Complaint: {patient_query}\nKnown Profile: {json.dumps(profile)}"
    try:
        reply = llm.generate(TRIAGE_PROMPT, [{"role": "user", "content": user_content}])
        data = _parse_json(reply)
    except Exception:
        data = {}

    urgency = str(data.get("urgency_level") or "Routine")
    is_emergency = bool(data.get("is_emergency")) or (urgency.lower() == "emergency")

    return {
        "urgency_level": urgency,
        "is_emergency": is_emergency,
        "extracted_symptoms": data.get("extracted_symptoms") or [patient_query],
        "triage_reason": data.get("reason") or "Triage clinical assessment completed."
    }


def emergency_halt_node(state: AgentState) -> dict:
    symptoms = ", ".join(state.get("extracted_symptoms") or ["Acute distress"])
    reason = state.get("triage_reason") or "Life-threatening symptoms detected."

    emergency_note = {
        "alert": "🚨 EMERGENCY MEDICAL ALERT - IMMEDIATE INTERVENTION REQUIRED 🚨",
        "status": "HALTED_FOR_SAFETY",
        "triage_level": "Emergency",
        "detected_symptoms": state.get("extracted_symptoms") or [],
        "clinical_rationale": reason,
        "recommended_action": (
            "Please call 911 or proceed immediately to the nearest Emergency Department. "
            "Do not wait for a regular clinic appointment."
        )
    }

    return {
        "care_summary": emergency_note,
        "recommended_specialty": ["Emergency Medicine / Trauma Care"]
    }


def navigation_node(state: AgentState) -> dict:
    symptoms = state.get("extracted_symptoms", [])
    user_content = (
        f"Symptoms: {symptoms}\n"
        f"Triage Level: {state.get('urgency_level')}\n"
        f"Patient Profile: {json.dumps(state.get('patient_profile', {}))}"
    )

    try:
        reply = llm.generate(NAVIGATION_PROMPT, [{"role": "user", "content": user_content}])
        data = _parse_json(reply)
    except Exception:
        data = {}

    specs = data.get("recommended_specialty") or ["General Practice"]
    if isinstance(specs, str):
        specs = [specs]

    return {
        "recommended_specialty": specs,
        "navigation_advice": data.get("navigation_advice") or "Consult a healthcare provider.",
        "tool_results": {"tools_active": list(_get_member3_tools().keys())}
    }


def care_summary_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    query = messages[-1]["content"] if messages else ""

    specs = state.get("recommended_specialty") or ["General Practice"]
    if isinstance(specs, str):
        specs = [specs]
    primary_spec = specs[0] if specs else "General Practice"

    user_content = (
        f"Original Complaint: {query}\n"
        f"Extracted Symptoms: {state.get('extracted_symptoms', [])}\n"
        f"Triage Level: {state.get('urgency_level', 'Routine')}\n"
        f"Suggested Specialties: {specs}\n"
        f"Navigation Advice: {state.get('navigation_advice', '')}\n"
        f"Patient History: {json.dumps(state.get('patient_profile', {}))}"
    )

    try:
        reply = llm.generate(CARE_SUMMARY_PROMPT, [{"role": "user", "content": user_content}])
        summary = _parse_json(reply)
    except Exception:
        summary = {}

    if not summary or not isinstance(summary, dict):
        summary = {
            "chief_complaint": query,
            "history_of_present_illness": f"Patient presents with: {state.get('extracted_symptoms', [query])}",
            "triage_level": state.get("urgency_level", "Routine"),
            "suggested_specialty": primary_spec,
            "recommended_next_steps": state.get("navigation_advice") or "Follow up with a specialist."
        }

    return {"care_summary": summary}