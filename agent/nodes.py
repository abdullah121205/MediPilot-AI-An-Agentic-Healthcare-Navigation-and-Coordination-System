import json
import re
import importlib
from typing import Dict, Any, List

from agent.state import AgentState
from agent.prompts import TRIAGE_PROMPT, NAVIGATION_PROMPT, CARE_SUMMARY_PROMPT
from agent.llm import LLM


def _parse_json(text: str) -> dict:
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


def _get_member3_tools() -> Dict[str, Any]:
    """Safely loads healthcare tools from tools/ without accidentally re-importing app.py."""
    tools = {}
    try:
        from tools import build_tools
        tools.update(build_tools())
    except Exception:
        pass
    try:
        import tools.healthcare_tools as h_tools
        if hasattr(h_tools, "get_tools"):
            tools.update(h_tools.get_tools())
    except Exception:
        pass
    return tools


def _check_allergy_contraindications(profile: dict, complaint: str) -> List[str]:
    """Automated clinical safety rule: flags drug allergy risks."""
    warnings = []
    allergies = [str(a).lower() for a in profile.get("allergies", []) + profile.get("medical_history", [])]
    text = complaint.lower()

    if any("nsaid" in a or "aspirin" in a or "ibuprofen" in a for a in allergies):
        if any(w in text for w in ["pain", "swelling", "knee", "joint", "headache", "fever"]):
            warnings.append("⚠️ CONTRAINDICATION: Patient reports NSAID/Aspirin allergy. Avoid prescribing Ibuprofen/Naproxen.")

    if any("penicillin" in a or "amoxicillin" in a for a in allergies):
        warnings.append("⚠️ ALLERGY ALERT: Documented Penicillin allergy. Avoid beta-lactam antibiotics.")

    return warnings


from dotenv import load_dotenv
load_dotenv()

try:
    llm = LLM()
except Exception:
    llm = None


def triage_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    patient_query = messages[-1]["content"] if messages else ""
    profile = state.get("patient_profile", {})

    user_content = f"Patient Complaint: {patient_query}\nPatient Profile: {json.dumps(profile)}"
    try:
        reply = llm.generate(TRIAGE_PROMPT, [{"role": "user", "content": user_content}])
        data = _parse_json(reply)
    except Exception:
        data = {}

    urgency = str(data.get("urgency_level") or "Routine")
    esi = int(data.get("esi_level") or (2 if urgency.lower() == "emergency" else 4))
    is_emergency = bool(data.get("is_emergency")) or (esi in [1, 2]) or (urgency.lower() == "emergency")

    return {
        "urgency_level": urgency,
        "esi_level": esi,
        "is_emergency": is_emergency,
        "extracted_symptoms": data.get("extracted_symptoms") or [patient_query],
        "triage_reason": data.get("reason") or f"Triage complete. Assigned ESI Level {esi}."
    }


def emergency_halt_node(state: AgentState) -> dict:
    esi = state.get("esi_level", 2)
    reason = state.get("triage_reason") or "Critical life-threatening red flags detected."

    emergency_note = {
        "alert": "🚨 EMERGENCY MEDICAL ALERT - IMMEDIATE INTERVENTION REQUIRED 🚨",
        "status": "HALTED_FOR_SAFETY",
        "triage_level": "Emergency",
        "esi_level": esi,
        "detected_symptoms": state.get("extracted_symptoms") or [],
        "clinical_rationale": reason,
        "recommended_action": (
            "Call 911 or proceed immediately to the nearest Emergency Department. "
            "Do not schedule standard outpatient navigation."
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
        f"ESI Level: {state.get('esi_level', 4)}\n"
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

    # Query Member 3's tools if available
    tools = _get_member3_tools()
    tool_results = {}
    if "search_clinics" in tools:
        try:
            tool_results["clinics"] = tools["search_clinics"].execute(specialty=specs[0])
        except Exception as e:
            tool_results["error"] = str(e)

    return {
        "recommended_specialty": specs,
        "navigation_advice": data.get("navigation_advice") or "Consult a medical specialist.",
        "tool_results": tool_results
    }


def care_summary_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    query = messages[-1]["content"] if messages else ""
    profile = state.get("patient_profile", {})

    specs = state.get("recommended_specialty") or ["General Practice"]
    if isinstance(specs, str):
        specs = [specs]
    primary_spec = specs[0] if specs else "General Practice"

    # Automated safety check
    safety_warnings = _check_allergy_contraindications(profile, query)

    user_content = (
        f"Original Complaint: {query}\n"
        f"Extracted Symptoms: {state.get('extracted_symptoms', [])}\n"
        f"ESI Level: {state.get('esi_level', 4)}\n"
        f"Specialties: {specs}\n"
        f"Known Profile & Allergies: {json.dumps(profile)}"
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
            "esi_level": state.get("esi_level", 4),
            "suggested_specialty": primary_spec,
            "clinical_safety_warnings": safety_warnings,
            "recommended_next_steps": state.get("navigation_advice") or "Follow up with a specialist."
        }
    else:
        # Merge safety warnings
        existing = summary.get("clinical_safety_warnings", [])
        if isinstance(existing, list):
            summary["clinical_safety_warnings"] = list(set(existing + safety_warnings))

    return {
        "care_summary": summary,
        "clinical_warnings": safety_warnings
    }