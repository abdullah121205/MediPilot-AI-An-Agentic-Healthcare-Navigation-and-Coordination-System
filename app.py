import streamlit as st
import json
from dotenv import load_dotenv

load_dotenv()

from agent.graph import build_healthcare_graph

st.set_page_config(
    page_title="MediPilot AI - Clinical Navigation",
    page_icon="🩺",
    layout="wide"
)

st.title("🩺 MediPilot AI")
st.markdown("#### *Agentic Healthcare Navigation & Clinical Care Coordination*")
st.divider()

# Sidebar: Patient Profile & Quick Demo Presets
with st.sidebar:
    st.header("👤 Patient Profile")
    age = st.number_input("Age", min_value=1, max_value=120, value=34, key="patient_age_input")
    gender = st.selectbox("Gender", ["Female", "Male", "Other"], key="patient_gender_select")
    med_history = st.text_area("Medical History / Allergies", "No known allergies. Mild seasonal asthma.", key="patient_history_area")
    
    st.divider()
    st.subheader("⚡ Quick Demo Presets")
    preset = st.radio(
        "Load test scenario:",
        [
            "Custom Query",
            "🚨 Emergency: Chest Pain & Arm Numbness",
            "🦴 Routine: Twisted Knee & Swelling",
            "🧴 Routine: Persistent Skin Rash"
        ]
    )

preset_queries = {
    "🚨 Emergency: Chest Pain & Arm Numbness": "I have severe crushing chest pain, difficulty breathing, and my left arm is numb.",
    "🦴 Routine: Twisted Knee & Swelling": "I twisted my right knee playing soccer yesterday. It popped and is now swollen and painful to bear weight.",
    "🧴 Routine: Persistent Skin Rash": "I have a red, itchy rash spreading across both of my elbows for the past four days."
}

# Preserve text cleanly
if "user_text" not in st.session_state:
    st.session_state["user_text"] = ""

if preset in preset_queries:
    st.session_state["user_text"] = preset_queries[preset]
elif preset == "Custom Query" and st.session_state["user_text"] in preset_queries.values():
    st.session_state["user_text"] = ""

# Main Input Section
st.subheader("💬 Describe Your Medical Complaint")
user_query = st.text_area(
    "Enter your symptoms, duration, and how you feel:",
    value=st.session_state["user_text"],
    height=110,
    placeholder="e.g., I have had a continuous headache and fever for the past 2 days..."
)

submit_btn = st.button("🚀 Analyze & Navigate", type="primary")

if submit_btn and user_query.strip():
    with st.spinner("🤖 MediPilot Multi-Agent Graph is processing (Triage → Navigation → Care Summary)..."):
        try:
            initial_state = {
                "messages": [{"role": "user", "content": user_query.strip()}],
                "patient_profile": {
                    "age": age,
                    "gender": gender,
                    "medical_history": [med_history]
                },
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
            result = app.invoke(initial_state)

            st.write("---")
            is_emergency = result.get("is_emergency", False) or str(result.get("urgency_level", "")).lower() == "emergency"
            summary = result.get("care_summary", {})

            if is_emergency:
                st.error("### 🚨 CLINICAL RED FLAG DETECTED - EMERGENCY")
                st.markdown(f"**Action Required:** {summary.get('recommended_action', 'Please call 911 immediately.')}")
                st.info(f"**Clinical Rationale:** {summary.get('clinical_rationale', result.get('triage_reason', 'Acute distress.'))}")
            else:
                st.success("### ✅ Triage Assessment: Routine / Safe for Outpatient Care")

            tab1, tab2, tab3 = st.tabs(["📋 Pre-Consultation Summary", "🩺 Specialty Navigation", "🔍 Agent Graph Trace (Judges View)"])

            with tab1:
                st.subheader("Structured Clinical Note (For Receiving Physician)")
                st.markdown(f"**Chief Complaint:** {summary.get('chief_complaint', user_query)}")
                st.markdown(f"**History of Present Illness (HPI):** {summary.get('history_of_present_illness', 'Detailed in intake.')}")
                st.markdown(f"**Triage Urgency Level:** `{summary.get('triage_level', result.get('urgency_level', 'Routine'))}`")
                st.markdown(f"**Recommended Specialty:** `{summary.get('suggested_specialty', result.get('recommended_specialty', ['General Practice']))}`")
                st.markdown(f"**Actionable Next Steps:** {summary.get('recommended_next_steps', 'Consult with a medical provider.')}")

            with tab2:
                st.subheader("Specialty & Facility Routing")
                specs = result.get("recommended_specialty", ["General Practice"])
                st.markdown(f"**Primary Specialty:** {', '.join(specs) if isinstance(specs, list) else specs}")
                st.markdown(f"**Navigation Advice:** {result.get('navigation_advice', 'Consult a qualified doctor.')}")

            with tab3:
                st.subheader("Multi-Agent Execution State (Raw Output)")
                st.json(result)

        except Exception as e:
            st.error(f"Error during agent execution: {e}")

elif submit_btn:
    st.warning("Please enter a medical complaint first.")