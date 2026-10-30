from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Annotated
import operator


class PatientProfile(TypedDict, total=False):
    age: Optional[int]
    gender: Optional[str]
    medical_history: List[str]
    current_medications: List[str]
    allergies: List[str]


class AgentState(TypedDict):
    # Core conversation state
    messages: Annotated[List[Dict[str, str]], operator.add]
    patient_profile: PatientProfile

    # Triage Agent outputs
    extracted_symptoms: List[str]
    urgency_level: str  # "Routine" | "Urgent" | "Emergency"
    triage_reason: str
    is_emergency: bool

    # Navigation Agent outputs
    recommended_specialty: List[str]
    navigation_advice: str
    tool_results: Dict[str, Any]

    # Care Summary Agent outputs
    care_summary: Dict[str, Any]